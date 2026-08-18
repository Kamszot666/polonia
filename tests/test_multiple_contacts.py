"""Testy zbierania kilku adresów e-mail i telefonów oraz profili społecznościowych.

Zgłoszenie użytkownika: strona kontaktowa podaje zwykle więcej niż jeden adres i numer
(sekretariat, biuro, dział projektów) - mają trafić do arkusza obok siebie, najwyżej po trzy
najbardziej wartościowe, a znaleziony profil społecznościowy ma uzupełnić pustą rubrykę.
"""

from collections import Counter
from dataclasses import replace

from main import OrganizationPipeline, _CrawlFindings
from app.extract.email_extractor import rank_emails
from app.models.schemas import FieldValue, Organization, SourceType
from config import settings


def _pipeline(custom_settings=None):
    return OrganizationPipeline(
        custom_settings or settings, http_fetcher=None, browser_fetcher=None, searcher=None,
        krs_client=None,
    )


def _findings(emails=(), phones=(), social=()) -> _CrawlFindings:
    findings = _CrawlFindings()
    findings.add_emails(list(emails), "https://example.pl/kontakt")
    findings.add_phones(Counter(phones), "https://example.pl/kontakt")
    findings.add_social_links(list(social), "https://example.pl/kontakt")
    return findings


def test_rank_emails_follows_priority_from_guidelines():
    emails = ["jan.kowalski@a.pl", "info@a.pl", "biuro@a.pl", "sekretariat@a.pl", "noreply@a.pl"]
    assert rank_emails(emails, 3) == ["sekretariat@a.pl", "biuro@a.pl", "info@a.pl"]


def test_rank_emails_drops_foreign_domains_when_own_domain_present():
    """Zweryfikowane realnie: strony organizacji wymieniają sponsorów wraz z ich adresami
    (fundacja@kghm.pl na pol.org.pl), które zajmowały wolne miejsca w rubryce."""
    emails = ["biuro@pol.org.pl", "fundacja@kghm.pl", "fundacja@pkobp.pl"]
    assert rank_emails(emails, 3, own_domain="pol.org.pl") == ["biuro@pol.org.pl"]


def test_rank_emails_keeps_foreign_domain_when_no_own_address_exists():
    emails = ["fundacja.polonia@gmail.com"]
    assert rank_emails(emails, 3, own_domain="polonia.pl") == ["fundacja.polonia@gmail.com"]


def test_additional_emails_are_appended_next_to_existing_one():
    org = Organization(input_name="Test")
    org.website = FieldValue(value="https://example.pl", confidence=1.0)
    org.email = FieldValue(value="biuro@example.pl", source_type=SourceType.MANUAL_INPUT, confidence=1.0)

    _pipeline()._apply_collected_contacts(
        org, _findings(emails=["biuro@example.pl", "sekretariat@example.pl", "info@example.pl"]),
    )

    assert org.email.value == "biuro@example.pl, sekretariat@example.pl, info@example.pl"


def test_existing_value_is_never_replaced_only_extended():
    org = Organization(input_name="Test")
    org.website = FieldValue(value="https://example.pl", confidence=1.0)
    org.email = FieldValue(value="stary@example.pl", source_type=SourceType.MANUAL_INPUT, confidence=1.0)

    _pipeline()._apply_collected_contacts(org, _findings(emails=["sekretariat@example.pl"]))

    assert org.email.value.startswith("stary@example.pl")
    assert org.email.source_type == SourceType.MANUAL_INPUT


def test_never_more_than_configured_number_of_emails():
    org = Organization(input_name="Test")
    org.website = FieldValue(value="https://example.pl", confidence=1.0)
    emails = [f"osoba{index}@example.pl" for index in range(10)]

    _pipeline()._apply_collected_contacts(org, _findings(emails=emails))

    assert len(org.email.value.split(", ")) == settings.max_emails_per_organization


def test_phones_are_ordered_by_frequency_and_capped():
    org = Organization(input_name="Test")
    # Numer centrali powtarza się na stronie najczęściej.
    phones = ["+48226285557"] * 5 + ["+48514777541"] * 2 + ["+48221234567"] + ["+48227654321"]

    _pipeline()._apply_collected_contacts(org, _findings(phones=phones))

    numbers = org.phone.value.split(", ")
    assert numbers[0] == "+48226285557"
    assert len(numbers) == settings.max_phones_per_organization


def test_social_media_fills_empty_column():
    org = Organization(input_name="Test")

    _pipeline()._apply_collected_contacts(
        org, _findings(social=["https://facebook.com/podmiot", "https://instagram.com/podmiot"]),
    )

    assert org.social_media.value == "https://facebook.com/podmiot, https://instagram.com/podmiot"


def test_social_media_does_not_overwrite_existing_entry():
    org = Organization(input_name="Test")
    org.social_media = FieldValue(value="https://facebook.com/wpisane-recznie",
                                   source_type=SourceType.MANUAL_INPUT, confidence=1.0)

    _pipeline()._apply_collected_contacts(org, _findings(social=["https://facebook.com/znalezione"]))

    assert org.social_media.value == "https://facebook.com/wpisane-recznie"


def test_findings_keep_one_profile_per_service_across_subpages():
    findings = _CrawlFindings()
    findings.add_social_links(["https://facebook.com/podmiot"], "https://example.pl")
    findings.add_social_links(["https://facebook.com/podmiot-inny-link"], "https://example.pl/kontakt")

    assert findings.social_links == ["https://facebook.com/podmiot"]


def test_collecting_can_be_disabled():
    disabled = replace(settings, collect_additional_contacts=False, collect_social_media_links=False)
    org = Organization(input_name="Test")
    org.email = FieldValue(value="biuro@example.pl", confidence=1.0)

    _pipeline(disabled)._apply_collected_contacts(
        org, _findings(emails=["sekretariat@example.pl"], social=["https://facebook.com/x"]),
    )

    assert org.email.value == "biuro@example.pl"
    assert org.social_media.is_empty
