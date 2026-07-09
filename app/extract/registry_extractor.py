"""Wykrywanie numerów KRS/NIP/REGON w treści strony (regex + suma kontrolna).

Format potwierdzony na żywej stronie pol.org.pl (meta og:description): "KRS 0000130056
NIP 5262149912 Regon 010100610". Sumy kontrolne NIP i REGON zweryfikowane na tych
właśnie realnych, znanych numerach.
"""

from __future__ import annotations

import regex as re

_KRS_PATTERN = re.compile(r"\bKRS[:\s]*?(\d{10})\b", re.IGNORECASE)
_NIP_PATTERN = re.compile(r"\bNIP[:\s]*?(\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}|\d{10})\b", re.IGNORECASE)
_REGON_PATTERN = re.compile(r"\bREGON[:\s]*?(\d{9}(?:\d{5})?)\b", re.IGNORECASE)

_NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
_REGON9_WEIGHTS = (8, 9, 2, 3, 4, 5, 6, 7)
_REGON14_WEIGHTS = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)


def find_krs_numbers(text: str) -> list[str]:
    return sorted({match.group(1) for match in _KRS_PATTERN.finditer(text)})


def find_nip_numbers(text: str) -> list[str]:
    candidates = {re.sub(r"[-\s]", "", match.group(1)) for match in _NIP_PATTERN.finditer(text)}
    return sorted(nip for nip in candidates if is_valid_nip(nip))


def find_regon_numbers(text: str) -> list[str]:
    candidates = {match.group(1) for match in _REGON_PATTERN.finditer(text)}
    return sorted(regon for regon in candidates if is_valid_regon(regon))


def is_valid_nip(nip: str) -> bool:
    if len(nip) != 10 or not nip.isdigit():
        return False
    checksum = sum(int(digit) * weight for digit, weight in zip(nip, _NIP_WEIGHTS)) % 11
    return checksum != 10 and checksum == int(nip[9])


def is_valid_regon(regon: str) -> bool:
    if len(regon) == 9 and regon.isdigit():
        return _checksum_matches(regon, _REGON9_WEIGHTS, check_index=8)
    if len(regon) == 14 and regon.isdigit():
        return is_valid_regon(regon[:9]) and _checksum_matches(regon, _REGON14_WEIGHTS, check_index=13)
    return False


def _checksum_matches(digits: str, weights: tuple[int, ...], check_index: int) -> bool:
    checksum = sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 11
    checksum = 0 if checksum == 10 else checksum
    return checksum == int(digits[check_index])
