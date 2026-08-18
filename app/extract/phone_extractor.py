"""Wykrywanie i walidacja numerów telefonu przez phonenumbers."""

from __future__ import annotations

from collections import Counter

import phonenumbers

# Numery, pod które faktycznie da się zadzwonić do organizacji. Bez tego filtra
# phonenumbers przyjmował jako "poprawne" ciągi cyfr ze strony (np. numery kont, daty),
# klasyfikując je jako pager czy numer premium - zweryfikowane realnie na pol.org.pl, gdzie
# do rubryki telefonów trafiał sześciocyfrowy "+48649333".
_CALLABLE_NUMBER_TYPES = frozenset({
    phonenumbers.PhoneNumberType.FIXED_LINE,
    phonenumbers.PhoneNumberType.MOBILE,
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    phonenumbers.PhoneNumberType.TOLL_FREE,
    phonenumbers.PhoneNumberType.VOIP,
})


def find_phones(text: str, region: str = "PL") -> list[str]:
    return list(count_phone_occurrences(text, region))


def is_callable_number(number: phonenumbers.PhoneNumber) -> bool:
    return (
        phonenumbers.is_valid_number(number)
        and phonenumbers.number_type(number) in _CALLABLE_NUMBER_TYPES
    )


def count_phone_occurrences(text: str, region: str = "PL") -> Counter[str]:
    """Liczy wystąpienia każdego numeru - na stronach zespołowych główny numer
    centrali zwykle powtarza się w każdym wierszu, więc częstość jest sygnałem,
    który numer jest "głównym" (zweryfikowane na żywej stronie pol.org.pl)."""
    counts: Counter[str] = Counter()
    for match in phonenumbers.PhoneNumberMatcher(text, region):
        if is_callable_number(match.number):
            formatted = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
            counts[formatted] += 1
    return counts
