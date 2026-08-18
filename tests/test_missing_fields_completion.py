"""Testy uzupełniania pozostałych rubryk arkusza: numerów rejestrowych, adresu, województwa,
branży i kategorii.

Zgłoszenie użytkownika: jeśli KRS/REGON/NIP albo branża i kategoria dają się odczytać
ze stron, które pipeline i tak przeszukuje, mają trafić do pustych rubryk.
"""

from collections import Counter
from dataclasses import replace

from main import OrganizationPipeline, _CrawlFindings, _needs_web_crawl
from app.extract.profile_classifier import detect_category, detect_organization_type
from app.extract.voivodeship_extractor import detect_voivodeship
from app.models.schemas import FieldValue, Organization, SourceType
from config import settings


def _pipeline(custom_settings=None):
    return OrganizationPipeline(
        custom_settings or settings, http_fetcher=None, browser_fetcher=None, searcher=None,
        krs_client=None,
    )


def _findings(krs=(), nip=(), regon=(), address=None) -> _CrawlFindings:
    findings = _CrawlFindings()
    findings.krs_counts.update(krs)
    findings.nip_counts.update(nip)
    findings.regon_counts.update(regon)
    findings.registry_source_url = "https://example.pl/kontakt"
    findings.add_address(address, "https://example.pl/kontakt")
    return findings


def test_fills_registry_numbers_found_on_page():
    """Numery z realnej meta og:description Fundacji Pomoc Polakom na Wschodzie."""
    org = Organization(input_name="Test")

    _pipeline()._apply_registry_numbers(
        org, _findings(krs=["0000130056"], nip=["5262149912"], regon=["010100610"]),
    )

    assert org.krs.value == "0000130056"
    assert org.nip.value == "5262149912"
    assert org.regon.value == "010100610"
    assert org.nip.source_type == SourceType.REGEX


def test_does_not_overwrite_registry_numbers_from_input_file():
    org = Organization(input_name="Test")
    org.krs = FieldValue(value="0000000001", source_type=SourceType.MANUAL_INPUT, confidence=1.0)

    _pipeline()._apply_registry_numbers(org, _findings(krs=["0000130056"]))

    assert org.krs.value == "0000000001"


def test_picks_most_frequent_number_when_page_lists_partners():
    """Strony wymieniają numery sponsorów obok własnych - wygrywa ten powtarzający się częściej."""
    findings = _findings(krs=["0000130056", "0000130056", "0000999999"])
    org = Organization(input_name="Test")

    _pipeline()._apply_registry_numbers(org, findings)

    assert org.krs.value == "0000130056"


def test_registry_collection_can_be_disabled():
    org = Organization(input_name="Test")
    disabled = replace(settings, collect_registry_numbers=False)

    _pipeline(disabled)._apply_registry_numbers(org, _findings(krs=["0000130056"]))

    assert org.krs.is_empty


def test_fills_address_and_derives_voivodeship():
    org = Organization(input_name="Test")

    _pipeline()._apply_address(org, _findings(address="ul. Jazdów 10A, 00-467 Warszawa"))

    assert org.address.value == "ul. Jazdów 10A, 00-467 Warszawa"
    assert org.voivodeship.value == "mazowieckie"


def test_does_not_overwrite_address_from_input_file():
    org = Organization(input_name="Test")
    org.address = FieldValue(value="ul. Stara 1, 00-001 Warszawa", source_type=SourceType.MANUAL_INPUT,
                              confidence=1.0)

    _pipeline()._apply_address(org, _findings(address="ul. Nowa 2, 00-002 Warszawa"))

    assert org.address.value == "ul. Stara 1, 00-001 Warszawa"


def test_detects_organization_type_from_name():
    assert detect_organization_type("Fundacja Pomoc Polakom na Wschodzie") == "Fundacja"
    assert detect_organization_type("Towarzystwo Naukowe KUL") == "Towarzystwo"
    assert detect_organization_type("Stowarzyszenie Wspólnota Polska") == "Stowarzyszenie"
    assert detect_organization_type("Związek Sybiraków") == "Związek"
    assert detect_organization_type("Anonimowy Podmiot") is None


def test_detects_category_from_name_and_description():
    assert detect_category("Fundacja Pomocy Szkołom Polskim na Wschodzie") == "Oświata i edukacja"
    assert detect_category("Związek Sybiraków") == "Kombatanci i weterani"
    assert detect_category("Fundacja Anonimowa", "Prowadzimy chór i zespół pieśni ludowej.") == (
        "Kultura i dziedzictwo"
    )
    assert detect_category("Anonimowy Podmiot", "") is None


def test_pipeline_fills_type_and_category_when_empty():
    org = Organization(input_name="Fundacja Pomocy Szkołom Polskim na Wschodzie")

    _pipeline()._apply_profile_classification(org)

    assert org.industry.value == "Fundacja"
    assert org.category == "Oświata i edukacja"


def test_pipeline_does_not_overwrite_type_and_category_from_input_file():
    org = Organization(input_name="Fundacja Testowa")
    org.industry = FieldValue(value="Działalność organizacji członkowskich",
                               source_type=SourceType.KRS_API, confidence=0.85)
    org.category = "Wpisane ręcznie"

    _pipeline()._apply_profile_classification(org)

    assert org.industry.value == "Działalność organizacji członkowskich"
    assert org.category == "Wpisane ręcznie"


def test_missing_registry_numbers_trigger_crawl():
    """Podmiot z kompletem kontaktów, ale bez numerów rejestrowych, nadal wymaga przeszukania."""
    org = Organization(input_name="Test")
    complete = FieldValue(value="cokolwiek", source_type=SourceType.MANUAL_INPUT, confidence=1.0)
    org.email = org.phone = org.social_media = complete
    org.description = FieldValue(value="x" * 300, source_type=SourceType.MANUAL_INPUT, confidence=1.0)
    org.contact_person.name = org.contact_person.email = org.contact_person.phone = complete
    org.address = org.voivodeship = complete

    assert _needs_web_crawl(org) is True  # brakuje KRS/REGON/NIP

    org.krs = org.regon = org.nip = complete
    assert _needs_web_crawl(org) is False


def test_findings_keep_first_address_found():
    findings = _CrawlFindings()
    findings.add_address("ul. Pierwsza 1, 00-001 Warszawa", "https://example.pl")
    findings.add_address("ul. Druga 2, 00-002 Warszawa", "https://example.pl/kontakt")

    assert findings.address == "ul. Pierwsza 1, 00-001 Warszawa"


def test_registry_counter_ignores_empty_results():
    findings = _CrawlFindings()
    findings.add_registry_numbers([], [], [], "https://example.pl")

    assert findings.registry_source_url is None
    assert findings.krs_counts == Counter()


def test_voivodeship_is_derived_from_city_in_address():
    """Sama nazwa województwa pada w adresie rzadko - bez mapy miast rubryka zostawała pusta."""
    assert detect_voivodeship("ul. Jazdów 10A, 00-467 Warszawa") == "mazowieckie"
    assert detect_voivodeship("ul. Rynek 5, 33-300 Nowy Sącz") == "małopolskie"
    assert detect_voivodeship("ul. Główna 2, 65-001 Zielona Góra") == "lubuskie"
    assert detect_voivodeship("woj. podlaskie") == "podlaskie"


def test_voivodeship_stays_empty_for_unknown_city():
    """Lepiej zostawić puste niż zgadywać - błędne województwo jest gorsze niż jego brak."""
    assert detect_voivodeship("ul. Wiejska 1, 11-111 Nieznanowo") is None
