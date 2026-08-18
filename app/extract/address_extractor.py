"""Wykrywanie adresu siedziby w treści strony.

Kotwicą jest kod pocztowy (`00-467`) - w polskich adresach występuje praktycznie zawsze,
a dwucyfrowy prefiks z myślnikiem prawie nie zdarza się przypadkiem w innym kontekście.
Od niego idziemy w lewo po nazwę ulicy z numerem i w prawo po miejscowość.

Format potwierdzony na żywej stronie pol.org.pl: „Adres ul. Jazdów 10A, 00-467 Warszawa".
"""

from __future__ import annotations

import regex as re

_POSTAL_CODE = r"\d{2}-\d{3}"

# Skróty otwierające nazwę ulicy. „Adres:" bywa doklejone przed nimi i nie należy do adresu.
_STREET_PREFIX = r"(?:ul\.|ulica|al\.|aleja|aleje|pl\.|plac|os\.|osiedle|rondo|skwer)"

_ADDRESS_PATTERN = re.compile(
    rf"(?P<street>{_STREET_PREFIX}\s*[^,;|\n]{{2,60}}?)"
    rf"\s*,?\s+(?P<postal>{_POSTAL_CODE})\s+(?P<city>[A-ZŁŚŻŹĆŃÓĄĘ][\p{{L}}-]+(?:\s+[A-ZŁŚŻŹĆŃÓĄĘ][\p{{L}}-]+)?)",
    re.IGNORECASE | re.UNICODE,
)
# Wariant bez ulicy - część podmiotów podaje wyłącznie kod pocztowy i miejscowość.
_POSTAL_ONLY_PATTERN = re.compile(
    rf"(?P<postal>{_POSTAL_CODE})\s+(?P<city>[A-ZŁŚŻŹĆŃÓĄĘ][\p{{L}}-]+(?:\s+[A-ZŁŚŻŹĆŃÓĄĘ][\p{{L}}-]+)?)",
    re.UNICODE,
)

_MULTIPLE_SPACES = re.compile(r"\s+")

# Nazwy miast bywają dwuczłonowe („Nowy Sącz", „Zielona Góra"), więc wzorzec dopuszcza drugie
# słowo z wielkiej litery - a wtedy łapie też etykietę stojącą zaraz za adresem
# (zweryfikowane realnie: „00-467 Warszawa E-mail" na pol.org.pl).
_NOT_CITY_WORDS = {
    "e-mail", "email", "mail", "tel", "tel.", "telefon", "fax", "faks", "kontakt", "adres",
    "krs", "nip", "regon", "konto", "godziny", "biuro", "strona", "www", "dane", "numer",
    "siedziba", "sekretariat", "nr", "telefony",
}
# Etykiety doklejane przed adresem w treści strony.
_LEADING_LABEL = re.compile(
    r"^(?:adres|siedziba|adres siedziby|adres korespondencyjny|kontakt)\s*[:\-]?\s*", re.IGNORECASE
)


def find_address(text: str) -> str | None:
    """Zwraca pierwszy pełny adres (ulica, kod, miasto) albo sam kod z miastem, jeśli innego nie ma."""
    match = _ADDRESS_PATTERN.search(text)
    if match is not None:
        street = _clean_street(match.group("street"))
        city = _clean_city(match.group("city"))
        if street and city:
            return f"{street}, {match.group('postal')} {city}"

    fallback = _POSTAL_ONLY_PATTERN.search(text)
    if fallback is not None:
        city = _clean_city(fallback.group("city"))
        if city:
            return f"{fallback.group('postal')} {city}"
    return None


def _clean_city(raw: str) -> str | None:
    words = _MULTIPLE_SPACES.sub(" ", raw).strip().split()
    while len(words) > 1 and words[-1].lower().strip(".,;:") in _NOT_CITY_WORDS:
        words.pop()
    if not words or words[0].lower().strip(".,;:") in _NOT_CITY_WORDS:
        return None
    return " ".join(words)


def _clean_street(raw: str) -> str | None:
    street = _MULTIPLE_SPACES.sub(" ", raw).strip(" ,;-")
    street = _LEADING_LABEL.sub("", street).strip(" ,;-")
    # Bez numeru budynku to nie jest adres, tylko wzmianka o ulicy.
    if not re.search(r"\d", street):
        return None
    return street
