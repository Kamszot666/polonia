from dataclasses import replace

from app.models.schemas import FieldValue, OrganizationStatus, SourceType
from app.models.schemas import Organization
from app.validate import validators
from app.validate.validators import validate_email_field, validate_organization, validate_url_field
from config import settings


def test_validate_email_field_rejects_malformed_address():
    field = FieldValue(value="not-an-email", confidence=0.6)
    result = validate_email_field(field)
    assert result.is_empty


def test_validate_email_field_passes_through_empty():
    field = FieldValue(value=None)
    assert validate_email_field(field) is field


def test_validate_email_field_validates_each_address_of_a_list():
    """Rubryka może zawierać kilka adresów - jeden błędny nie może unieważnić pozostałych."""
    field = FieldValue(value="biuro@example.pl, zly@@adres, sekretariat@example.pl", confidence=0.8)
    result = validate_email_field(field, replace(settings, verify_mx_records=False))
    assert result.value == "biuro@example.pl, sekretariat@example.pl"


def test_validate_email_field_deduplicates_addresses():
    field = FieldValue(value="biuro@example.pl, Biuro@Example.pl", confidence=0.8)
    result = validate_email_field(field, replace(settings, verify_mx_records=False))
    assert result.value == "biuro@example.pl"


def test_validate_url_field_adds_scheme():
    field = FieldValue(value="example.pl")
    result = validate_url_field(field)
    assert result.value == "https://example.pl"


def test_validate_url_field_keeps_existing_scheme():
    field = FieldValue(value="http://example.pl")
    result = validate_url_field(field)
    assert result.value == "http://example.pl"


def test_validate_organization_marks_failed_when_no_contact_data():
    org = Organization(input_name="Testowa Fundacja")
    result = validate_organization(org)
    assert result.status == OrganizationStatus.FAILED


def test_validate_organization_marks_partial_with_only_website():
    org = Organization(input_name="Testowa Fundacja")
    org.website = FieldValue(value="https://example.pl", source_type=SourceType.SEARCH_RESULT, confidence=0.5)
    result = validate_organization(org)
    assert result.status == OrganizationStatus.PARTIAL


def test_mx_check_falls_back_to_public_dns_when_local_resolver_times_out(monkeypatch):
    """Zweryfikowane realnie u użytkownika: router jako serwer DNS gubił zapytania i nawet
    gmail.com wychodził jako domena "bez rekordu MX"."""
    validators._mx_cache.clear()
    attempts: list[list[str] | None] = []

    def fake_query(domain, nameservers, _settings):
        attempts.append(nameservers)
        return None if nameservers is None else True

    monkeypatch.setattr(validators, "_query_mx", fake_query)

    assert validators.has_mx_record("gmail.com") is True
    assert attempts[0] is None                     # najpierw resolwer systemowy
    assert attempts[1] == [settings.dns_fallback_servers[0]]  # potem zapasowy


def test_mx_check_assumes_records_exist_when_every_resolver_is_silent(monkeypatch):
    """Awaria sieci nie jest dowodem, że adres jest zły - lepiej nie obniżać pewności."""
    validators._mx_cache.clear()
    monkeypatch.setattr(validators, "_query_mx", lambda domain, nameservers, _s: None)

    assert validators.has_mx_record("gmail.com") is True
    assert "gmail.com" not in validators._mx_cache  # chwilowa awaria nie idzie do cache


def test_mx_check_trusts_definitive_negative_answer(monkeypatch):
    """Odpowiedź "ta domena nie ma MX" jest wiążąca - nie pytamy serwerów zapasowych."""
    validators._mx_cache.clear()
    attempts: list[list[str] | None] = []

    def fake_query(domain, nameservers, _settings):
        attempts.append(nameservers)
        return False

    monkeypatch.setattr(validators, "_query_mx", fake_query)

    assert validators.has_mx_record("bez-poczty.example") is False
    assert attempts == [None]
