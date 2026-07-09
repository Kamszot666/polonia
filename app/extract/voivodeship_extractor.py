"""Wykrywanie województwa na podstawie adresu lub treści strony."""

from __future__ import annotations

_VOIVODESHIPS = (
    "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie",
    "małopolskie", "mazowieckie", "opolskie", "podkarpackie", "podlaskie",
    "pomorskie", "śląskie", "świętokrzyskie", "warmińsko-mazurskie",
    "wielkopolskie", "zachodniopomorskie",
)


def detect_voivodeship(text: str) -> str | None:
    lowered = text.lower()
    for voivodeship in _VOIVODESHIPS:
        if voivodeship in lowered:
            return voivodeship
    return None
