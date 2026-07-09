"""Punkt wejścia: orkiestracja pełnego pipeline'u pozyskiwania danych kontaktowych (pkt 1-11 algorytmu)."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

import httpx

from app.checkpoint.checkpoint_store import CheckpointStore
from app.export.excel_exporter import export_to_excel
from app.extract.contact_relation_extractor import (
    ContactCandidate,
    extract_contact_candidates,
    select_best_candidate,
)
from app.extract.email_extractor import find_emails, find_emails_in_html, score_email
from app.extract.krs_registry import fetch_krs_record
from app.extract.phone_extractor import count_phone_occurrences
from app.extract.schema_extractor import extract_schema_data
from app.extract.voivodeship_extractor import detect_voivodeship
from app.fetch.browser_client import BrowserFetcher
from app.fetch.http_client import HttpFetcher, needs_browser_rendering
from app.logging.logger import configure_logging, logger
from app.models.schemas import ContactPerson, FieldValue, Organization, OrganizationStatus, SourceType
from app.parse.html_parser import PageParser
from app.parse.text_fallback import extract_clean_text
from app.search.ddgs_search import DdgsOfficialSiteSearch
from app.storage.input_reader import (
    is_full_schema_workbook,
    read_organization_names,
    read_organizations_from_workbook,
)
from app.validate.validators import validate_organization
from config import Settings, settings


def _needs_web_crawl(org: Organization) -> bool:
    fields = (
        org.email, org.phone, org.social_media, org.description,
        org.contact_person.name, org.contact_person.email, org.contact_person.phone,
    )
    return any(field.is_empty for field in fields)


def _needs_krs_lookup(org: Organization) -> bool:
    return not org.krs.is_empty and any(
        field.is_empty for field in (org.address, org.voivodeship, org.nip, org.industry)
    )


class OrganizationPipeline:
    """Uzupełnia braki w rekordzie podmiotu: KRS API -> search -> fetch -> parse -> extract ->
    validate (pkt 2-10 algorytmu). Pola już wypełnione (np. z pliku wejściowego) nie są
    nadpisywane - pipeline dokłada tylko to, czego brakuje."""

    def __init__(
        self,
        settings: Settings,
        http_fetcher: HttpFetcher,
        browser_fetcher: BrowserFetcher,
        searcher: DdgsOfficialSiteSearch,
        krs_client: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._http = http_fetcher
        self._browser = browser_fetcher
        self._searcher = searcher
        self._krs_client = krs_client

    async def process(self, org: Organization) -> Organization:
        org.status = OrganizationStatus.IN_PROGRESS
        try:
            if _needs_krs_lookup(org):
                await self._apply_krs_registry(org)

            if _needs_web_crawl(org):
                if org.website.is_empty:
                    search_result = await self._searcher.find_official_site(org.input_name)
                    if search_result is not None:
                        org.website = FieldValue(
                            value=search_result.url, source_url=search_result.url,
                            source_type=SourceType.SEARCH_RESULT, evidence=search_result.title, confidence=0.5,
                        )
                if not org.website.is_empty:
                    await self._crawl_site(org, org.website.value)

            org = validate_organization(org, self._settings)
        except Exception as exc:
            logger.exception(f"Błąd przetwarzania {org.input_name!r}")
            org.status = OrganizationStatus.FAILED
            org.error = str(exc)
        org.date_acquired = datetime.now().strftime("%d.%m.%Y")
        return org

    async def _apply_krs_registry(self, org: Organization) -> None:
        record = await fetch_krs_record(org.krs.value, self._krs_client)
        if record is None:
            return
        if org.name.is_empty and not record.name.is_empty:
            org.name = record.name
        if org.address.is_empty and not record.address.is_empty:
            org.address = record.address
        if org.voivodeship.is_empty and not record.voivodeship.is_empty:
            org.voivodeship = record.voivodeship
        if org.nip.is_empty and not record.nip.is_empty:
            org.nip = record.nip
        if org.industry.is_empty and not record.industry.is_empty:
            org.industry = record.industry

    async def _crawl_site(self, org: Organization, start_url: str) -> None:
        to_visit = [start_url]
        visited: set[str] = set()
        all_candidates: list[ContactCandidate] = []

        while to_visit and len(visited) <= self._settings.max_subpages_per_site:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            html = await self._fetch_page(url)
            if html is None:
                continue

            parser = PageParser(html, url, self._settings)

            if url == start_url:
                self._apply_schema_data(org, html, url)
                to_visit.extend(link for link in parser.find_subpage_links() if link not in visited)

            self._apply_text_fields(org, parser, html, url)
            all_candidates.extend(extract_contact_candidates(parser.dom_blocks(), url, self._settings))

        best_candidate = select_best_candidate(all_candidates, self._settings)
        if best_candidate is not None:
            org.contact_person = self._candidate_to_contact_person(best_candidate)

    async def _fetch_page(self, url: str) -> str | None:
        result = await self._http.fetch(url)
        if needs_browser_rendering(result, self._settings):
            logger.debug(f"Uruchamiam Playwright dla {url} (heurystyka JS)")
            browser_result = await self._browser.fetch(url)
            if browser_result.ok:
                return browser_result.html
        return result.html

    def _apply_schema_data(self, org: Organization, html: str, url: str) -> None:
        schema = extract_schema_data(html, url)
        if org.name.is_empty and not schema.name.is_empty:
            org.name = schema.name
        if org.phone.is_empty and not schema.telephone.is_empty:
            org.phone = schema.telephone
        if org.email.is_empty and not schema.email.is_empty:
            org.email = schema.email
        if org.address.is_empty and not schema.address.is_empty:
            org.address = schema.address
        if schema.same_as and org.social_media.is_empty:
            org.social_media = FieldValue(
                value=", ".join(schema.same_as), source_url=url,
                source_type=SourceType.SCHEMA_ORG, evidence="schema.org:sameAs", confidence=0.85,
            )

    def _apply_text_fields(self, org: Organization, parser: PageParser, html: str, url: str) -> None:
        text = parser.full_text()
        if len(text) < self._settings.min_text_length_for_static_page:
            text = extract_clean_text(html, url) or text
        meta_description = parser.meta_description()
        # og:description (Yoast SEO) bywa niedostępny w body.text() (żyje w <head>), a często zawiera
        # skondensowane dane kontaktowe - potwierdzone na pol.org.pl. Doklejamy do puli tekstu do analizy.
        combined_text = f"{meta_description}\n{text}" if meta_description else text

        if org.email.is_empty:
            # Regex na tekście nie wystarcza - część adresów jest zasłonięta przez Cloudflare
            # email-obfuscation (data-cfemail), niewidoczna w body.text() (potwierdzone na wid.org.pl).
            email_candidates = list(dict.fromkeys(find_emails(combined_text) + find_emails_in_html(html)))
            if email_candidates:
                best_email = max(email_candidates, key=score_email)
                org.email = FieldValue(value=best_email, source_url=url, source_type=SourceType.REGEX,
                                        evidence=combined_text[:200], confidence=score_email(best_email))
        if org.phone.is_empty:
            # Numer centrali zwykle powtarza się najczęściej (np. w każdym wierszu tabeli zespołu
            # na pol.org.pl), więc najczęstszy numer jest lepszym sygnałem niż pierwszy napotkany.
            phone_counts = count_phone_occurrences(combined_text)
            if phone_counts:
                main_phone, _ = phone_counts.most_common(1)[0]
                org.phone = FieldValue(value=main_phone, source_url=url, source_type=SourceType.REGEX,
                                        evidence=combined_text[:200], confidence=0.6)
        if org.voivodeship.is_empty:
            voivodeship = detect_voivodeship(org.address.value or combined_text)
            if voivodeship:
                org.voivodeship = FieldValue(value=voivodeship, source_url=url,
                                              source_type=SourceType.PAGE_TEXT, evidence=combined_text[:200],
                                              confidence=0.5)
        if org.description.is_empty:
            if meta_description:
                org.description = FieldValue(value=meta_description[:300], source_url=url,
                                              source_type=SourceType.META_TAG, evidence=meta_description,
                                              confidence=0.7)
            elif text.strip():
                org.description = FieldValue(value=text.strip()[:300], source_url=url,
                                              source_type=SourceType.PAGE_TEXT, evidence=text[:200], confidence=0.4)

    @staticmethod
    def _candidate_to_contact_person(candidate: ContactCandidate) -> ContactPerson:
        def field(value: str | None) -> FieldValue:
            if value is None:
                return FieldValue()
            return FieldValue(value=value, source_url=candidate.source_url, source_type=SourceType.CONTACT_PAGE,
                               evidence=candidate.evidence, confidence=candidate.confidence)

        return ContactPerson(
            name=field(candidate.person_name), position=field(candidate.position),
            email=field(candidate.email), phone=field(candidate.phone),
        )


def _load_seed_organizations(input_path: Path) -> list[Organization]:
    if input_path.suffix.lower() in {".xlsx", ".xlsm"} and is_full_schema_workbook(input_path):
        organizations = read_organizations_from_workbook(input_path)
        logger.info(f"Wykryto pełny schemat bazy - wczytano {len(organizations)} organizacji do uzupełnienia")
        return organizations
    names = read_organization_names(input_path)
    logger.info(f"Wczytano {len(names)} nazw organizacji (lista bez wcześniejszych danych)")
    return [Organization(input_name=name) for name in names]


async def run(input_path: Path, settings: Settings = settings) -> Path:
    seed_organizations = _load_seed_organizations(input_path)
    checkpoint = CheckpointStore(settings)
    pending = [org for org in seed_organizations if not checkpoint.is_done(org.input_name)]
    logger.info(f"Do przetworzenia: {len(pending)} (reszta odczytana z checkpointu)")

    http_fetcher = HttpFetcher(settings)
    browser_fetcher = BrowserFetcher(settings)
    searcher = DdgsOfficialSiteSearch(settings)
    krs_client = httpx.AsyncClient(headers={"User-Agent": settings.user_agent})
    pipeline = OrganizationPipeline(settings, http_fetcher, browser_fetcher, searcher, krs_client)
    semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def process_one(seed_org: Organization) -> None:
        async with semaphore:
            org = await pipeline.process(seed_org)
            checkpoint.save(org)
            logger.info(f"{org.input_name}: status={org.status.value}")

    try:
        await asyncio.gather(*(process_one(org) for org in pending))
    finally:
        await http_fetcher.aclose()
        await browser_fetcher.stop()
        await krs_client.aclose()

    all_results = checkpoint.load_all()
    checkpoint.close()
    return export_to_excel(all_results, settings)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Budowa bazy kontaktów organizacji wspierających Polonię")
    parser.add_argument("--input", type=Path, required=True, help="Plik CSV/XLSX z nazwami organizacji")
    parser.add_argument("--verbose", action="store_true", help="Szczegółowe logowanie")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    configure_logging(verbose=args.verbose)
    output_path = asyncio.run(run(args.input, settings))
    logger.info(f"Gotowe. Wynik: {output_path}")


if __name__ == "__main__":
    main()
