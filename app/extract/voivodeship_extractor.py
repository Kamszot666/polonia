"""Wykrywanie województwa na podstawie adresu.

Sama nazwa województwa pada w adresie rzadko - realne adresy ze stron organizacji mają
postać „ul. Jazdów 10A, 00-467 Warszawa", więc bez mapy miast rubryka zostawała pusta
praktycznie zawsze. Mapa obejmuje miasta wojewódzkie i większe ośrodki, w których siedzibę
mają organizacje z bazy; miasto nierozpoznane zostawia pustą wartość zamiast zgadywać.
"""

from __future__ import annotations

import regex as re

_VOIVODESHIPS = (
    "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie",
    "małopolskie", "mazowieckie", "opolskie", "podkarpackie", "podlaskie",
    "pomorskie", "śląskie", "świętokrzyskie", "warmińsko-mazurskie",
    "wielkopolskie", "zachodniopomorskie",
)

_CITY_TO_VOIVODESHIP = {
    # mazowieckie
    "warszawa": "mazowieckie", "radom": "mazowieckie", "płock": "mazowieckie",
    "siedlce": "mazowieckie", "pruszków": "mazowieckie", "ostrołęka": "mazowieckie",
    "legionowo": "mazowieckie", "otwock": "mazowieckie", "ciechanów": "mazowieckie",
    # małopolskie
    "kraków": "małopolskie", "tarnów": "małopolskie", "nowy sącz": "małopolskie",
    "oświęcim": "małopolskie", "zakopane": "małopolskie", "wadowice": "małopolskie",
    # dolnośląskie
    "wrocław": "dolnośląskie", "wałbrzych": "dolnośląskie", "legnica": "dolnośląskie",
    "jelenia góra": "dolnośląskie", "lubin": "dolnośląskie", "głogów": "dolnośląskie",
    # wielkopolskie
    "poznań": "wielkopolskie", "kalisz": "wielkopolskie", "konin": "wielkopolskie",
    "piła": "wielkopolskie", "gniezno": "wielkopolskie", "leszno": "wielkopolskie",
    # śląskie
    "katowice": "śląskie", "częstochowa": "śląskie", "gliwice": "śląskie",
    "zabrze": "śląskie", "bytom": "śląskie", "sosnowiec": "śląskie", "rybnik": "śląskie",
    "bielsko-biała": "śląskie", "tychy": "śląskie", "chorzów": "śląskie",
    "cieszyn": "śląskie", "racibórz": "śląskie",
    # pomorskie
    "gdańsk": "pomorskie", "gdynia": "pomorskie", "sopot": "pomorskie",
    "słupsk": "pomorskie", "tczew": "pomorskie", "starogard gdański": "pomorskie",
    # zachodniopomorskie
    "szczecin": "zachodniopomorskie", "koszalin": "zachodniopomorskie",
    "stargard": "zachodniopomorskie", "kołobrzeg": "zachodniopomorskie",
    "świnoujście": "zachodniopomorskie",
    # lubelskie
    "lublin": "lubelskie", "chełm": "lubelskie", "zamość": "lubelskie",
    "biała podlaska": "lubelskie", "puławy": "lubelskie",
    # podlaskie
    "białystok": "podlaskie", "łomża": "podlaskie", "suwałki": "podlaskie",
    "augustów": "podlaskie", "sejny": "podlaskie", "bielsk podlaski": "podlaskie",
    # łódzkie
    "łódź": "łódzkie", "piotrków trybunalski": "łódzkie", "pabianice": "łódzkie",
    "tomaszów mazowiecki": "łódzkie", "sieradz": "łódzkie", "skierniewice": "łódzkie",
    # podkarpackie
    "rzeszów": "podkarpackie", "przemyśl": "podkarpackie", "stalowa wola": "podkarpackie",
    "krosno": "podkarpackie", "mielec": "podkarpackie", "sanok": "podkarpackie",
    "jarosław": "podkarpackie",
    # kujawsko-pomorskie
    "bydgoszcz": "kujawsko-pomorskie", "toruń": "kujawsko-pomorskie",
    "włocławek": "kujawsko-pomorskie", "grudziądz": "kujawsko-pomorskie",
    "inowrocław": "kujawsko-pomorskie",
    # warmińsko-mazurskie
    "olsztyn": "warmińsko-mazurskie", "elbląg": "warmińsko-mazurskie",
    "ełk": "warmińsko-mazurskie", "giżycko": "warmińsko-mazurskie",
    "ostróda": "warmińsko-mazurskie",
    # lubuskie
    "zielona góra": "lubuskie", "gorzów wielkopolski": "lubuskie", "nowa sól": "lubuskie",
    "żary": "lubuskie",
    # opolskie
    "opole": "opolskie", "kędzierzyn-koźle": "opolskie", "nysa": "opolskie",
    "brzeg": "opolskie", "kluczbork": "opolskie",
    # świętokrzyskie
    "kielce": "świętokrzyskie", "ostrowiec świętokrzyski": "świętokrzyskie",
    "starachowice": "świętokrzyskie", "skarżysko-kamienna": "świętokrzyskie",
    "sandomierz": "świętokrzyskie",
}

# Dłuższe nazwy najpierw - inaczej "Nowa Sól" dopasowałoby się przez "sól"... a przede
# wszystkim "Zielona Góra" musi wygrać z ewentualnym "Góra".
_CITY_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(city) for city in sorted(_CITY_TO_VOIVODESHIP, key=len, reverse=True)) + r")\b",
    re.IGNORECASE | re.UNICODE,
)


def detect_voivodeship(text: str) -> str | None:
    lowered = text.lower()
    for voivodeship in _VOIVODESHIPS:
        if voivodeship in lowered:
            return voivodeship
    match = _CITY_PATTERN.search(lowered)
    if match is not None:
        return _CITY_TO_VOIVODESHIP[match.group(1)]
    return None
