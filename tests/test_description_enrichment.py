"""Testy wzbogacania 'Krótkiej charakterystyki podmiotu' (config.enrich_short_descriptions) -
zgłoszone przez użytkownika jako zbyt ubogie, gdy pochodzą wyłącznie z pliku wejściowego."""

from dataclasses import replace

from main import OrganizationPipeline
from app.models.schemas import FieldValue, Organization, SourceType
from config import settings


def _pipeline(custom_settings=None):
    return OrganizationPipeline(
        custom_settings or settings, http_fetcher=None, browser_fetcher=None, searcher=None, krs_client=None,
    )


def test_fills_empty_description():
    org = Organization(input_name="Test")
    pipeline = _pipeline()

    pipeline._apply_description(org, meta_description="Krótki opis ze strony.", text="", url="https://example.pl")

    assert org.description.value == "Krótki opis ze strony."
    assert org.description.source_type == SourceType.META_TAG


def test_enriches_short_existing_description():
    org = Organization(
        input_name="Test",
        description=FieldValue(value="Oferent w konkursach MSZ.", source_type=SourceType.MANUAL_INPUT,
                                confidence=1.0),
    )
    pipeline = _pipeline()

    pipeline._apply_description(
        org, meta_description="Fundacja działa od 2010 roku i prowadzi szkołę sobotnią dla dzieci polonijnych.",
        text="", url="https://example.pl",
    )

    assert "Oferent w konkursach MSZ." in org.description.value
    assert "szkołę sobotnią" in org.description.value


def test_does_not_touch_already_rich_description():
    long_description = "x" * 250
    org = Organization(
        input_name="Test",
        description=FieldValue(value=long_description, source_type=SourceType.MANUAL_INPUT, confidence=1.0),
    )
    pipeline = _pipeline()

    pipeline._apply_description(org, meta_description="Coś zupełnie nowego.", text="", url="https://example.pl")

    assert org.description.value == long_description


def test_does_not_duplicate_same_content():
    org = Organization(
        input_name="Test",
        description=FieldValue(value="Fundacja pomaga Polonii za granicą.", source_type=SourceType.MANUAL_INPUT,
                                confidence=1.0),
    )
    pipeline = _pipeline()

    pipeline._apply_description(
        org, meta_description="Fundacja pomaga Polonii za granicą.", text="", url="https://example.pl",
    )

    assert org.description.value == "Fundacja pomaga Polonii za granicą."


def test_respects_enrich_flag_disabled():
    disabled_settings = replace(settings, enrich_short_descriptions=False)
    org = Organization(
        input_name="Test",
        description=FieldValue(value="Krótko.", source_type=SourceType.MANUAL_INPUT, confidence=1.0),
    )
    pipeline = _pipeline(disabled_settings)

    pipeline._apply_description(org, meta_description="Dużo więcej szczegółów o organizacji.", text="",
                                 url="https://example.pl")

    assert org.description.value == "Krótko."
