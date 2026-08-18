"""Ustalanie rubryk „Branża / Typ" i „Kategoria", gdy nie ma ich ani w pliku wejściowym,
ani w API KRS.

Branża bierze się z formy prawnej czytelnej wprost z nazwy własnej („Fundacja …",
„Towarzystwo …"). Kategoria - z obszaru działania rozpoznanego po słowach kluczowych
w nazwie i opisie podmiotu.

Obie listy słów siedzą w `config.Settings`, żeby dało się je dopasować do nazewnictwa
używanego w konkretnej bazie bez ruszania kodu. Rozpoznanie po słowach kluczowych bywa
zgrubne, więc pewność jest odpowiednio niższa niż dla danych z KRS - a rubryka już
wypełniona nigdy nie jest nadpisywana.
"""

from __future__ import annotations

from config import Settings, settings


def detect_organization_type(name: str, settings: Settings = settings) -> str | None:
    """Forma prawna podmiotu z jego nazwy własnej („Fundacja Pomoc Polakom na Wschodzie")."""
    lowered = name.lower()
    for label, keywords in settings.organization_type_keywords:
        if any(keyword in lowered for keyword in keywords):
            return label
    return None


def detect_category(name: str, description: str = "", settings: Settings = settings) -> str | None:
    """Obszar działania podmiotu. Nazwa waży więcej niż opis - jest krótsza i celniejsza,
    a opis ze strony bywa mieszanką aktualności i menu."""
    for source in (name, description):
        if not source:
            continue
        lowered = source.lower()
        for label, keywords in settings.organization_category_keywords:
            if any(keyword in lowered for keyword in keywords):
                return label
    return None
