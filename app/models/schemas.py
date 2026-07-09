"""Modele danych. Każde pole kontaktowe niesie ze sobą źródło i pewność (wymóg z instrukcji, pkt 9)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SourceType(StrEnum):
    SCHEMA_ORG = "schema.org"
    REGEX = "regex"
    CONTACT_PAGE = "contact_page"
    FOOTER = "footer"
    OCR = "ocr"
    NER = "ner"
    SEARCH_RESULT = "search_result"
    PAGE_TEXT = "page_text"
    META_TAG = "meta_tag"


class OrganizationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(slots=True)
class FieldValue:
    """Wartość pola wraz z pochodzeniem i pewnością. `value=None` oznacza brak danych."""

    value: str | None = None
    source_url: str | None = None
    source_type: SourceType | None = None
    evidence: str | None = None
    confidence: float = 0.0

    @property
    def is_empty(self) -> bool:
        return self.value is None or self.value.strip() == ""

    def better_than(self, other: FieldValue) -> bool:
        if other.is_empty:
            return not self.is_empty
        return not self.is_empty and self.confidence > other.confidence


@dataclass(slots=True)
class ContactCandidate:
    """Kandydat na osobę kontaktową, wynik pracy contact_relation_extractor przed wyborem najlepszego."""

    person_name: str | None = None
    position: str | None = None
    email: str | None = None
    phone: str | None = None
    confidence: float = 0.0
    source_url: str = ""
    evidence: str = ""
    dom_block_selector: str = ""


@dataclass(slots=True)
class ContactPerson:
    name: FieldValue = field(default_factory=FieldValue)
    position: FieldValue = field(default_factory=FieldValue)
    email: FieldValue = field(default_factory=FieldValue)
    phone: FieldValue = field(default_factory=FieldValue)


@dataclass(slots=True)
class Organization:
    """Jeden rekord docelowej bazy - odpowiada wierszowi w Excelu."""

    input_name: str
    name: FieldValue = field(default_factory=FieldValue)
    address: FieldValue = field(default_factory=FieldValue)
    voivodeship: FieldValue = field(default_factory=FieldValue)
    phone: FieldValue = field(default_factory=FieldValue)
    email: FieldValue = field(default_factory=FieldValue)
    website: FieldValue = field(default_factory=FieldValue)
    social_media: FieldValue = field(default_factory=FieldValue)
    contact_person: ContactPerson = field(default_factory=ContactPerson)
    description: FieldValue = field(default_factory=FieldValue)
    status: OrganizationStatus = OrganizationStatus.PENDING
    error: str | None = None
    date_acquired: str | None = None  # format DD.MM.RRRR, zgodnie z procedurą budowy bazy w Excelu
