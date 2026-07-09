"""Zapis wyników do Excela przez openpyxl (pkt 11 algorytmu).

Układ i nazwy kolumn 1-15 oraz konwencja wypełniania braków ("brak" / "nie ustalono"
zamiast pustej komórki) odpowiadają dostarczonej „Procedurze tworzenia bazy danych
w Excelu”. Kolumny 16-17 (Status, Źródła i pewność) to rozszerzenie wymagane przez
instrukcję Polonia (pkt 9: każde pole musi mieć przypisane źródło i confidence) -
procedura ogólna ich nie przewiduje, ale nie jest z nimi sprzeczna.

"Kategoria" i "Branża / Typ" nie są automatycznie wykrywane - algorytm z instrukcji
Polonia nie definiuje, jak je wyprowadzić z danych organizacji wspierających Polonię,
więc kolumny istnieją (zgodność ze schematem formatki), ale zawsze "brak" do ręcznego
uzupełnienia.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.logging.logger import logger
from app.models.schemas import FieldValue, Organization
from config import Settings, settings

_BRAK = "brak"
_NIE_USTALONO = "nie ustalono"

_HEADERS = (
    "Lp.", "Kategoria", "Branża / Typ", "Nazwa", "Adres korespondencyjny", "Województwo",
    "Numer telefonu", "Adres e-mail", "Strona WWW", "Profil w mediach społecznościowych",
    "Osoba kontaktowa", "Numer telefonu do osoby kontaktowej", "Adres e-mail do osoby kontaktowej",
    "Data pozyskania informacji", "Krótka charakterystyka podmiotu",
    "Status", "Źródła i pewność",
)


def export_to_excel(organizations: list[Organization], settings: Settings = settings) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Organizacje"
    sheet.append(_HEADERS)

    for index, org in enumerate(organizations, start=1):
        sheet.append(_organization_to_row(index, org))

    _autosize_columns(sheet)

    settings.output_xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(settings.output_xlsx_path)
    logger.info(f"Zapisano {len(organizations)} rekordów do {settings.output_xlsx_path}")
    return settings.output_xlsx_path


def _organization_to_row(lp: int, org: Organization) -> list[str]:
    person = org.contact_person
    return [
        lp,
        _BRAK,  # Kategoria - nie wykrywane automatycznie, patrz docstring modułu
        _BRAK,  # Branża / Typ - jw.
        _value_or(org.name, _BRAK),
        _value_or(org.address, _BRAK),
        _value_or(org.voivodeship, _BRAK),
        _value_or(org.phone, _BRAK),
        _value_or(org.email, _BRAK),
        _value_or(org.website, _BRAK),
        _value_or(org.social_media, _BRAK),
        _value_or(person.name, _NIE_USTALONO),
        _value_or(person.phone, _BRAK),
        _value_or(person.email, _BRAK),
        org.date_acquired or _BRAK,
        _value_or(org.description, _BRAK),
        org.status.value,
        _summarize_sources(org),
    ]


def _value_or(field: FieldValue, fallback: str) -> str:
    return field.value if not field.is_empty else fallback


def _summarize_sources(org: Organization) -> str:
    labeled_fields: list[tuple[str, FieldValue]] = [
        ("nazwa", org.name), ("adres", org.address), ("województwo", org.voivodeship),
        ("telefon", org.phone), ("e-mail", org.email), ("WWW", org.website),
        ("media społ.", org.social_media),
        ("osoba", org.contact_person.name), ("stanowisko", org.contact_person.position),
        ("telefon osoby", org.contact_person.phone), ("e-mail osoby", org.contact_person.email),
        ("opis", org.description),
    ]
    parts = []
    for label, field in labeled_fields:
        if field.is_empty:
            continue
        source = field.source_type.value if field.source_type else "?"
        url = field.source_url or "?"
        parts.append(f"{label}: {source} @ {url} (conf={field.confidence:.2f})")
    return "; ".join(parts)


def _autosize_columns(sheet: Worksheet, max_width: int = 60) -> None:
    for index in range(1, len(_HEADERS) + 1):
        column_letter = get_column_letter(index)
        max_length = max(
            (len(str(cell.value)) for cell in sheet[column_letter] if cell.value is not None),
            default=10,
        )
        sheet.column_dimensions[column_letter].width = min(max_length + 2, max_width)
