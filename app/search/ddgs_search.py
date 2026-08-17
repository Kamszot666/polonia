"""Wyszukiwanie oficjalnej strony podmiotu przez DuckDuckGo (kroki 2-3 algorytmu z instrukcji).

Backend "html_duckduckgo" (klasyczny, bezJS-owy interfejs DDG) jest jedynym, który
zwrócił poprawne wyniki w tym środowisku - domyślny backend dawał "No results found",
a bing/brave/yahoo kończyły się resetem połączenia (zweryfikowane empirycznie).
Zachowujemy fallback na domyślny backend, gdyby ten akurat przestał działać gdzie
indziej.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import tldextract
from rapidfuzz import fuzz

from app.logging.logger import logger
from config import Settings, settings

try:
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException
except ImportError:  # starsza nazwa pakietu
    from duckduckgo_search import DDGS
    from duckduckgo_search.exceptions import DuckDuckGoSearchException as DDGSException

_PREFERRED_BACKENDS = ("html_duckduckgo", None)

# Katalogi/agregatory KRS i wizytówek firmowych - potwierdzone realnie jako źródło błędnych
# "stron WWW" (agregator zamiast oficjalnej strony podmiotu) przy uruchomieniu na pełnym
# pliku użytkownika (372 organizacje).
_SOCIAL_AND_DIRECTORY_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "wikipedia.org", "wikipedia.pl",
    "ngo.pl", "rejestr.io", "rejestr.ngo", "aleo.com", "panoramafirm.pl", "olx.pl", "gowork.pl",
    "cylex-polska.pl", "dnb.com", "bizraport.pl", "okredo.com", "krs-pobierz.pl",
    "egospodarka.pl", "owg.pl", "pb.pl", "registries.io", "firmania.pl", "infoveriti.pl",
    "imsig.pl", "pkt.pl", "krs-online.com.pl", "rejestrkrs.pl", "vrejestr.pl", "gov.pl",
    "biaman.pl", "localgymsandfitness.com", "fanimani.pl",
    # Artefakty samej wyszukiwarki (np. URL przekierowania) czasem przeciekają do wyników.
    "startpage.com", "mojeek.com", "brave.com", "bing.com", "yandex.com",
}


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DdgsOfficialSiteSearch:
    """Wyszukuje najbardziej prawdopodobną oficjalną stronę podmiotu.

    Wymusza minimalny odstęp między zapytaniami (config.search_min_interval_seconds) -
    wyszukiwarka zaczyna zwracać błędy połączenia po serii szybkich zapytań pod rząd
    (zweryfikowane empirycznie), więc współbieżne przetwarzanie wielu podmiotów nie
    powinno odpytywać jej równolegle."""

    def __init__(self, settings: Settings = settings) -> None:
        self._settings = settings
        self._rate_limit_lock = asyncio.Lock()
        self._last_call_at = 0.0

    async def find_official_site(self, organization_name: str) -> SearchResult | None:
        query = self._settings.search_query_template.format(name=organization_name)
        await self._respect_rate_limit()
        results = await asyncio.to_thread(self._search_sync, query)
        if not results:
            logger.warning(f"Brak wyników wyszukiwania dla: {organization_name!r}")
            return None
        return self._pick_best(organization_name, results)

    async def _respect_rate_limit(self) -> None:
        async with self._rate_limit_lock:
            now = asyncio.get_event_loop().time()
            wait = self._settings.search_min_interval_seconds - (now - self._last_call_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call_at = asyncio.get_event_loop().time()

    def _search_sync(self, query: str) -> list[SearchResult]:
        last_error: Exception | None = None
        for backend in _PREFERRED_BACKENDS:
            kwargs = {"max_results": self._settings.search_max_results, "region": "pl-pl"}
            if backend is not None:
                kwargs["backend"] = backend
            for attempt in range(1, self._settings.search_max_retries + 1):
                try:
                    with DDGS(timeout=20) as ddgs:
                        raw = ddgs.text(query, **kwargs)
                    return [
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("href") or item.get("url", ""),
                            snippet=item.get("body", ""),
                        )
                        for item in raw
                        if item.get("href") or item.get("url")
                    ]
                except DDGSException as exc:
                    logger.debug(f"Backend {backend!r} próba {attempt} nieudana dla {query!r}: {exc}")
                    last_error = exc
                    if attempt < self._settings.search_max_retries:
                        time.sleep(self._settings.backoff_base_seconds * attempt)
        logger.warning(f"Wszystkie backendy wyszukiwania zawiodły dla {query!r}: {last_error}")
        return []

    def _pick_best(self, organization_name: str, results: list[SearchResult]) -> SearchResult | None:
        candidates = [r for r in results if not self._is_excluded_result(r.url)]
        if not candidates:
            # Zweryfikowane realnie: podstawianie wykluczonego wyniku (katalog firm, PDF,
            # Wikipedia) jako "strony WWW" bywa aktywnie mylące (np. strona rejestru KRS
            # zamiast oficjalnej strony podmiotu) - lepiej zostawić brak niż zgadywać źle.
            logger.debug(f"Wszystkie wyniki dla {organization_name!r} to katalogi/agregatory - brak kandydata")
            return None

        def score(result: SearchResult) -> float:
            title_score = fuzz.token_set_ratio(organization_name, result.title)
            domain_bonus = 10.0 if self._domain_contains_org_hint(organization_name, result.url) else 0.0
            return title_score + domain_bonus

        best = max(candidates, key=score)
        logger.debug(f"Wybrana strona dla {organization_name!r}: {best.url}")
        return best

    @staticmethod
    def _is_excluded_result(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            # Zweryfikowane realnie: wyszukiwarka czasem zwraca własny link przekierowania
            # (np. "/clev?event=StartpageResultClick&...") zamiast prawdziwego adresu strony -
            # próba użycia go jako "strony WWW" wywalała się przy budowaniu żądania httpx.
            return True
        if url.lower().split("?")[0].endswith((".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx")):
            return True
        extracted = tldextract.extract(url)
        registered_domain = f"{extracted.domain}.{extracted.suffix}".lower()
        return registered_domain in _SOCIAL_AND_DIRECTORY_DOMAINS

    @staticmethod
    def _domain_contains_org_hint(organization_name: str, url: str) -> bool:
        extracted = tldextract.extract(url)
        domain = extracted.domain.lower()
        name_tokens = [token.lower() for token in organization_name.split() if len(token) > 3]
        return any(token in domain for token in name_tokens)
