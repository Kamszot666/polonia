from dataclasses import replace

from app.models.schemas import FieldValue, OrganizationStatus, SourceType
from app.models.schemas import Organization
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
