"""Wykrywanie i walidacja składniowa adresów e-mail.

Oprócz zwykłego regexu na tekście, dekoduje adresy zasłonięte przez Cloudflare
email-obfuscation (`data-cfemail`) - potwierdzone na żywej stronie wid.org.pl,
gdzie prawdziwy adres jest niewidoczny w czystym tekście strony (widoczny tylko
placeholder "[email protected]"), a ukryty w atrybucie jako string XOR-owany
jednobajtowym kluczem zapisanym jako pierwsze dwa znaki.
"""

from __future__ import annotations

import regex as re
import tldextract
from email_validator import EmailNotValidError, validate_email

_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_CF_EMAIL_PATTERN = re.compile(r'data-cfemail="([a-f0-9]+)"')

_LOW_VALUE_LOCAL_PARTS = {"noreply", "no-reply", "webmaster", "admin", "postmaster"}
# Kolejność wprost z wytycznych użytkownika dotyczących obróbki arkuszy - decyduje, które
# adresy zostają, gdy strona podaje ich więcej niż mieści się w rubryce.
_PRIORITY_LOCAL_PARTS = (
    "sekretariat", "biuro", "kontakt", "office", "info", "firma", "administracja",
)
_HIGH_VALUE_LOCAL_PARTS = {"contact", "fundacja", "stowarzyszenie", "recepcja", "zarzad"}


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
    """Zwraca bazowy confidence dla adresu, zanim doda się bonus z bliskości DOM/tekstu.

    Adresy z listy priorytetowej są rozróżniane co do kolejności (sekretariat@ przed biuro@
    przed kontakt@ ...), bo przy więcej niż jednym trafieniu to ten wynik decyduje, który
    adres zostaje w arkuszu."""
    local_part = email.split("@", 1)[0].lower()
    if local_part in _LOW_VALUE_LOCAL_PARTS:
        return 0.3
    if local_part in _PRIORITY_LOCAL_PARTS:
        return 0.90 - 0.02 * _PRIORITY_LOCAL_PARTS.index(local_part)
    if local_part in _HIGH_VALUE_LOCAL_PARTS:
        return 0.7
    return 0.6


def rank_emails(emails: list[str], limit: int, own_domain: str | None = None) -> list[str]:
    """Zostawia najwyżej `limit` najbardziej wartościowych adresów, bez duplikatów.

    Gdy znana jest domena podmiotu i pada na niej choć jeden adres, adresy z obcych domen są
    odrzucane w całości. Zweryfikowane realnie: strony organizacji polonijnych wymieniają
    sponsorów i partnerów razem z ich adresami (fundacja@kghm.pl, fundacja@pkobp.pl na
    pol.org.pl), które bez tego filtra zajmowały wolne miejsca w rubryce."""
    unique = list(dict.fromkeys(email.lower() for email in emails))
    if own_domain:
        own = [email for email in unique if email.rsplit("@", 1)[-1].endswith(own_domain.lower())]
        if own:
            unique = own
    return sorted(unique, key=lambda email: (-score_email(email), email))[:limit]


def registered_domain(url_or_email: str) -> str | None:
    """Domena rejestrowana (bez subdomen) - do porównania adresu e-mail ze stroną podmiotu."""
    host = url_or_email.rsplit("@", 1)[-1]
    extracted = tldextract.extract(host)
    if not extracted.domain or not extracted.suffix:
        return None
    return f"{extracted.domain}.{extracted.suffix}".lower()
