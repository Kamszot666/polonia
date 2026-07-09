"""Odczyt listy nazw organizacji z pliku wejściowego (CSV lub Excel) - krok 1 algorytmu."""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

from app.logging.logger import logger

_NAME_COLUMN_CANDIDATES = {"nazwa", "name", "nazwa organizacji", "nazwa podmiotu"}


def read_organization_names(input_path: Path) -> list[str]:
    suffix = input_path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return _read_from_excel(input_path)
    if suffix == ".csv":
        return _read_from_csv(input_path)
    raise ValueError(f"Nieobsługiwany format pliku wejściowego: {suffix}")


def _read_from_excel(path: Path) -> list[str]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    rows = sheet.iter_rows(values_only=True)
    header = next(rows, None)
    name_column_index = _find_name_column_index(header)

    names = [
        str(row[name_column_index]).strip()
        for row in rows
        if name_column_index < len(row) and row[name_column_index]
    ]
    workbook.close()
    return _deduplicate(names)


def _read_from_csv(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        name_column_index = _find_name_column_index(header)
        names = [
            row[name_column_index].strip()
            for row in reader
            if len(row) > name_column_index and row[name_column_index].strip()
        ]
    return _deduplicate(names)


def _find_name_column_index(header: tuple | list | None) -> int:
    if header:
        for index, cell in enumerate(header):
            if cell and str(cell).strip().lower() in _NAME_COLUMN_CANDIDATES:
                return index
    logger.warning("Nie znaleziono nagłówka z nazwą organizacji - używam pierwszej kolumny")
    return 0


def _deduplicate(names: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for name in names:
        seen.setdefault(name, None)
    return list(seen)
