"""Wykrywanie i walidacja numerów telefonu przez phonenumbers."""

from __future__ import annotations

from collections import Counter

import phonenumbers


def find_phones(text: str, region: str = "PL") -> list[str]:
    return list(count_phone_occurrences(text, region))


def count_phone_occurrences(text: str, region: str = "PL") -> Counter[str]:
    """Liczy wystąpienia każdego numeru - na stronach zespołowych główny numer
    centrali zwykle powtarza się w każdym wierszu, więc częstość jest sygnałem,
    który numer jest "głównym" (zweryfikowane na żywej stronie pol.org.pl)."""
    counts: Counter[str] = Counter()
    for match in phonenumbers.PhoneNumberMatcher(text, region):
        if phonenumbers.is_valid_number(match.number):
            formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
            counts[formatted] += 1
    return counts
