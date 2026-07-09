"""Testy na realnych zrzutach odpowiedzi oficjalnego API KRS (api-krs.ms.gov.pl),
zapisanych w tests/fixtures/ - potwierdzają parsowanie bez konieczności pytania
żywego API w każdym przebiegu testów."""

import json
from pathlib import Path

from app.extract.krs_registry import _parse_odpis

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_parse_odpis_with_industry_data():
    """KRS 0000130056 (Fundacja Pomoc Polakom na Wschodzie), rejestr P - prowadzi
    działalność gospodarczą, więc ma wypełniony przeważający przedmiot działalności."""
    payload = _load_fixture("krs_api_0000130056_rejestrP.json")
    record = _parse_odpis(payload, source_url="https://api-krs.ms.gov.pl/test")

    assert record is not None
    assert record.name.value == 'FUNDACJA "POMOC POLAKOM NA WSCHODZIE" IM. JANA OLSZEWSKIEGO'
    assert record.nip.value == "5262149912"
    assert "JAZDÓW 10A" in record.address.value
    assert record.voivodeship.value == "mazowieckie"
    assert record.industry.value == "WYDAWANIE KSIĄŻEK"
    assert record.nip.source_url == "https://api-krs.ms.gov.pl/test"
    assert record.nip.confidence == 0.95


def test_parse_odpis_without_industry_data():
    """KRS 0000010057 (Towarzystwo Naukowe KUL), rejestr S - stowarzyszenie bez
    działalności gospodarczej, dział 3 z przedmiotem działalności nieobecny."""
    payload = _load_fixture("krs_api_0000010057_rejestrS.json")
    record = _parse_odpis(payload, source_url="https://api-krs.ms.gov.pl/test")

    assert record is not None
    assert record.nip.value == "7120104964"
    assert "SPOKOJNA" in record.address.value
    assert record.voivodeship.value == "lubelskie"
    assert record.industry.is_empty


def test_parse_odpis_returns_none_for_malformed_payload():
    assert _parse_odpis({}, source_url="https://example.com") is None
