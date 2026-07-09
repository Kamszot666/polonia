from pathlib import Path

import openpyxl

from app.storage.input_reader import is_full_schema_workbook, read_organizations_from_workbook

_HEADER = (
    "Lp.", "Kategoria", "Branża / Typ", "Nazwa", "Adres korespondencyjny", "Województwo",
    "Numer telefonu", "Adres e-mail", "Strona WWW", "Profil w mediach społecznościowych",
    "Osoba kontaktowa", "Numer telefonu do osoby kontaktowej", "Adres e-mail do osoby kontaktowej",
    "Data pozyskania informacji", "Krótka charakterystyka podmiotu", "URL źródła", "KRS", "REGON", "NIP",
)


def _write_workbook(path: Path, rows: list[tuple]) -> None:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(_HEADER)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def test_is_full_schema_workbook_detects_real_header(tmp_path: Path):
    path = tmp_path / "baza.xlsx"
    _write_workbook(path, [])
    assert is_full_schema_workbook(path)


def test_is_full_schema_workbook_rejects_simple_name_list(tmp_path: Path):
    path = tmp_path / "lista.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(("nazwa",))
    workbook.save(path)
    assert not is_full_schema_workbook(path)


def test_read_organizations_from_workbook_splits_name_and_position(tmp_path: Path):
    path = tmp_path / "baza.xlsx"
    _write_workbook(path, [
        (
            None, "organizacja pozarządowa", "brak", "FUNDACJA TESTOWA", "ul. Testowa 1, 00-001 Warszawa",
            "mazowieckie", "22 123 45 67", "biuro@fundacja-testowa.pl", "https://fundacja-testowa.pl",
            "brak", "Jan Kowalski (Prezes)", "brak", "brak", "01.01.2026", "Krótki opis.",
            "https://example.gov.pl/wyniki", "0000123456", "brak", "1234567890",
        ),
    ])

    organizations = read_organizations_from_workbook(path)
    assert len(organizations) == 1

    org = organizations[0]
    assert org.input_name == "FUNDACJA TESTOWA"
    assert org.name.value == "FUNDACJA TESTOWA"
    assert org.name.confidence == 1.0
    assert org.address.value == "ul. Testowa 1, 00-001 Warszawa"
    assert org.krs.value == "0000123456"
    assert org.regon.is_empty  # "brak" -> pole puste do uzupełnienia
    assert org.contact_person.name.value == "Jan Kowalski"
    assert org.contact_person.position.value == "Prezes"
    assert org.origin_source_url == "https://example.gov.pl/wyniki"


def test_read_organizations_from_workbook_handles_missing_contact_person(tmp_path: Path):
    path = tmp_path / "baza.xlsx"
    _write_workbook(path, [
        (
            None, "organizacja pozarządowa", "brak", "FUNDACJA BEZ OSOBY", "brak", "brak", "brak", "brak",
            "brak", "brak", "nie ustalono", "brak", "brak", "01.01.2026", "brak", "brak", "brak", "brak", "brak",
        ),
    ])

    org = read_organizations_from_workbook(path)[0]
    assert org.contact_person.name.is_empty
    assert org.contact_person.position.is_empty
    assert org.category == "organizacja pozarządowa"
