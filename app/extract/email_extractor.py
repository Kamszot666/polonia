"""Wykrywanie i walidacja składniowa adresów e-mail.

Oprócz zwykłego regexu na tekście, dekoduje adresy zasłonięte przez Cloudflare
email-obfuscation (`data-cfemail`) - potwierdzone na żywej stronie wid.org.pl,
gdzie prawdziwy adres jest niewidoczny w czystym tekście strony (widoczny tylko
placeholder "[email protected]"), a ukryty w atrybucie jako string XOR-owany
jednobajtowym kluczem zapisanym jako pierwsze dwa znaki.
"""

from __future__ import annotations

import regex as re
from email_validator import EmailNotValidError, validate_email

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_CF_EMAIL_PATTERN = re.compile(r'data-cfemail="([a-f0-9]+)"')

_LOW_VALUE_LOCAL_PARTS = {"noreply", "no-reply", "webmaster", "admin", "postmaster"}
_HIGH_VALUE_LOCAL_PARTS = {"kontakt", "contact", "biuro", "sekretariat", "info", "fundacja", "recepcja"}


def find_emails(text: str) -> list[str]:
    candidates = {match.group(0).strip(".,;:") for match in _EMAIL_PATTERN.finditer(text)}
    valid: list[str] = []
    for candidate in candidates:
        try:
            result = validate_email(candidate, check_deliverability=False)
        except EmailNotValidError:
            continue
        valid.append(result.normalized)
    return sorted(valid)


def find_emails_in_html(html: str) -> list[str]:
    """Dekoduje adresy zasłonięte przez Cloudflare email-obfuscation, niewidoczne w zwykłym tekście."""
    decoded = (_decode_cloudflare_email(match) for match in _CF_EMAIL_PATTERN.findall(html))
    return sorted({email for email in decoded if email})


def _decode_cloudflare_email(encoded: str) -> str | None:
    if len(encoded) < 4:
        return None
    try:
        key = int(encoded[:2], 16)
        decoded = "".join(chr(int(encoded[i:i + 2], 16) ^ key) for i in range(2, len(encoded), 2))
    except ValueError:
        return None
    return decoded if "@" in decoded else None


def score_email(email: str) -> float:
    """Zwraca bazowy confidence dla adresu, zanim doda się bonus z bliskości DOM/tekstu."""
    local_part = email.split("@", 1)[0].lower()
    if local_part in _LOW_VALUE_LOCAL_PARTS:
        return 0.3
    if local_part in _HIGH_VALUE_LOCAL_PARTS:
        return 0.8
    return 0.6
