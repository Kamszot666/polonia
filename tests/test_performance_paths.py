"""Testy zabezpieczające optymalizacje wydajności pipeline'u.

Wąskim gardłem przebiegu na pełnej bazie (372 podmioty) nie była sieć, tylko:
1) tworzenie nowego detektora NER (spaCy + GLiNER ładowane z dysku) dla każdej pobranej strony,
2) uruchamianie rozpoznawania osób na każdym zagnieżdżonym bloku DOM strony,
3) ponawianie z backoffem żądań do nieistniejących domen i uruchamianie Playwrighta dla PDF-ów.

Te testy pilnują, żeby żadna z tych ścieżek nie wróciła po zmianach.
"""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.extract.contact_relation_extractor import (
    HeuristicPersonNameDetector,
    extract_contact_candidates,
    get_person_name_detector,
)
from app.fetch.http_client import FetchResult, HttpFetcher, needs_browser_rendering
from app.parse.html_parser import DomBlock
from config import Settings, settings


class _CountingDetector:
    """Zlicza, na ilu blokach faktycznie uruchomiono rozpoznawanie osób."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def detect(self, text: str, organization_name: str | None = None) -> list[str]:
        self.calls.append(text)
        return HeuristicPersonNameDetector().detect(text, organization_name)


def test_ner_detector_is_shared_between_calls():
    """Detektor NER trzyma załadowane modele, więc musi być jeden na proces - inaczej
    spaCy i GLiNER wczytują się od nowa dla każdej podstrony każdej organizacji."""
    ner_settings = replace(settings, ner_enabled=True)

    first = get_person_name_detector(ner_settings)
    second = get_person_name_detector(ner_settings)

    assert first is second


def test_heuristic_detector_does_not_need_sharing():
    heuristic_settings = replace(settings, ner_enabled=False)
    assert isinstance(get_person_name_detector(heuristic_settings), HeuristicPersonNameDetector)


def test_blocks_without_email_or_phone_skip_person_detection():
    """Blok bez e-maila i telefonu daje maksymalnie 0.40 pewności (0.25 osoba + 0.15 stanowisko),
    czyli poniżej contact_person_confidence_threshold - rozpoznawanie osób w nim to koszt bez
    wpływu na wynik."""
    blocks = [
        DomBlock(selector_path="p[0]", html="", text="Prezes zarządu Jan Kowalski wita na stronie."),
        DomBlock(selector_path="p[1]", html="", text="Kontakt: Anna Nowak, anna@example.pl"),
    ]
    detector = _CountingDetector()

    extract_contact_candidates(blocks, source_url="https://example.pl", person_detector=detector)

    assert detector.calls == ["Kontakt: Anna Nowak, anna@example.pl"]


def test_person_detection_runs_everywhere_when_signal_check_disabled():
    blocks = [
        DomBlock(selector_path="p[0]", html="", text="Prezes zarządu Jan Kowalski wita na stronie."),
        DomBlock(selector_path="p[1]", html="", text="Kontakt: Anna Nowak, anna@example.pl"),
    ]
    detector = _CountingDetector()

    extract_contact_candidates(
        blocks, source_url="https://example.pl",
        settings=replace(settings, ner_require_contact_signal=False), person_detector=detector,
    )

    assert len(detector.calls) == 2


def test_repeated_block_text_is_analyzed_once():
    """Selektory bloków są zagnieżdżone (div > p), więc ten sam tekst wraca po kilka razy."""
    text = "Kontakt: Anna Nowak, anna@example.pl"
    blocks = [
        DomBlock(selector_path="div[0]", html="", text=text),
        DomBlock(selector_path="p[1]", html="", text=text),
    ]
    detector = _CountingDetector()

    candidates = extract_contact_candidates(
        blocks, source_url="https://example.pl", person_detector=detector,
    )

    assert len(detector.calls) == 1
    assert len({candidate.dom_block_selector for candidate in candidates}) == 1


def test_permanent_failure_does_not_trigger_browser():
    """Playwright na PDF-ie, stronie 404 czy martwej domenie to kilkanaście sekund na pewny
    brak wyniku."""
    pdf_result = FetchResult(url="https://example.pl/statut.pdf", html=None, status_code=200,
                              from_cache=False, error="nie-HTML content-type: application/pdf",
                              permanent_failure=True)
    assert needs_browser_rendering(pdf_result) is False


def test_transient_failure_still_triggers_browser():
    timeout_result = FetchResult(url="https://example.pl/", html=None, status_code=None,
                                  from_cache=False, error="timeout")
    assert needs_browser_rendering(timeout_result) is True


@pytest.fixture
def fetcher(tmp_path):
    return HttpFetcher(Settings(cache_dir=tmp_path / "cache"))


async def test_unreachable_host_is_not_retried(fetcher):
    """Nieistniejąca domena nie zacznie odpowiadać po 1,5 s przerwy, a w bazie organizacji
    polonijnych sporo adresów WWW jest już nieaktywnych."""
    fetcher._client.get = AsyncMock(side_effect=httpx.ConnectError("nazwa nie została rozwiązana"))

    result = await fetcher.fetch("https://nieistniejaca-domena.example/")

    assert fetcher._client.get.await_count == 1
    assert result.permanent_failure
    await fetcher.aclose()


async def test_permanent_failure_is_cached_across_fetches(fetcher):
    fetcher._client.get = AsyncMock(side_effect=httpx.ConnectError("nazwa nie została rozwiązana"))

    await fetcher.fetch("https://nieistniejaca-domena.example/")
    second = await fetcher.fetch("https://nieistniejaca-domena.example/")

    assert fetcher._client.get.await_count == 1  # drugie wywołanie odczytane z cache
    assert second.from_cache
    await fetcher.aclose()


async def test_transient_failure_is_retried(fetcher):
    settings_without_waiting = Settings(cache_dir=fetcher._settings.cache_dir, backoff_base_seconds=0.0)
    fetcher._settings = settings_without_waiting
    fetcher._client.get = AsyncMock(side_effect=httpx.ReadTimeout("za wolno"))

    result = await fetcher.fetch("https://example.pl/")

    assert fetcher._client.get.await_count == settings_without_waiting.max_retries
    assert not result.permanent_failure
    await fetcher.aclose()


async def test_forbidden_response_is_not_retried_but_still_reaches_browser(fetcher):
    """Zweryfikowane realnie: swiatnatak.pl, ltn.lomza.pl i krzyzowa.org.pl odpowiadały 403.
    Odmowa nie zmieni się po odczekaniu, ale przeglądarka bywa wpuszczana tam, gdzie httpx nie."""
    response = MagicMock(status_code=403)
    fetcher._client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError("403", request=MagicMock(), response=response)
    )

    result = await fetcher.fetch("https://example.pl/")

    assert fetcher._client.get.await_count == 1
    assert not result.permanent_failure          # fallback na przeglądarkę ma sens
    assert needs_browser_rendering(result) is True
    await fetcher.aclose()


def test_requests_carry_browser_headers():
    """Sam prawidłowy User-Agent nie wystarcza - brak typowych nagłówków przeglądarki
    też bywa sygnałem dla filtrów antybotowych."""
    headers = HttpFetcher(Settings())._client.headers

    assert "Chrome" in headers["User-Agent"]
    assert "text/html" in headers["Accept"]
    assert headers["Accept-Language"].startswith("pl-PL")
