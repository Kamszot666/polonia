"""Czyści i formatuje arkusz Excel według standardu obróbki arkuszy.

Robi to samo, co pipeline robi automatycznie ze swoim wynikiem, ale na dowolnym pliku -
np. na bazie uzupełnianej wcześniej ręcznie. Oryginał nie jest nadpisywany.

Użycie: python scripts/format_workbook.py <plik_wejsciowy.xlsx> [plik_wyjsciowy.xlsx]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.export.excel_formatter import format_workbook  # noqa: E402
from config import settings  # noqa: E402


def main() -> None:
    if len(sys.argv) not in (2, 3):
        print("Użycie: python scripts/format_workbook.py <plik_wejsciowy.xlsx> [plik_wyjsciowy.xlsx]")
        raise SystemExit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Nie znaleziono pliku: {input_path}")
        raise SystemExit(1)

    if len(sys.argv) == 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = input_path.with_name(
            f"{input_path.stem}{settings.formatted_output_suffix}{input_path.suffix}"
        )
    if output_path.resolve() == input_path.resolve():
        print("Plik wyjściowy musi być inny niż wejściowy - oryginał nie jest nadpisywany.")
        raise SystemExit(1)

    report = format_workbook(input_path, output_path, settings)

    print(f"Zapisano: {output_path}")
    print("\nRaport zmian:")
    for label, value in report.as_lines():
        print(f"  {label}: {value}")
    if report.notes:
        print("\nSzczegóły:")
        for note in report.notes:
            print(f"  - {note}")


if __name__ == "__main__":
    main()
