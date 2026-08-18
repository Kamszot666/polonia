"""Walidacja pól przed zapisem do Excela: e-mail (składnia + MX), URL, status kompletności rekordu."""

from __future__ import annotations

import dns.resolver
from email_validator import EmailNotValidError, validate_email

from app.logging.logger import logger
from app.models.schemas import FieldValue, Organization, OrganizationStatus
from config import Settings, settings

_mx_cache: dict[str, bool] = {}


def has_mx_record(domain: str, settings: Settings = settings) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = settings.dns_resolver_timeout_seconds
        resolver.lifetime = settings.dns_resolver_timeout_seconds
        resolver.resolve(domain, "MX")
        result = True
    except Exception as exc:
        logger.debug(f"Brak rekordu MX dla domeny {domain!r}: {exc}")
        result = False
    _mx_cache[domain] = result
    return result


def validate_email_field(field: FieldValue, settings: Settings = settings) -> FieldValue:
    """Rubryka e-mail może zawierać kilka adresów rozdzielonych separatorem - każdy jest
    sprawdzany osobno, a niepoprawne wypadają, zamiast unieważniać całą wartość."""
    if field.is_empty:
        return field

    separator = settings.contact_list_separator
    normalized: list[str] = []
    without_mx = False
    for candidate in (part.strip() for part in field.value.split(separator.strip() or ",")):
        if not candidate:
            continue
        try:
            result = validate_email(candidate, check_deliverability=False)
        except EmailNotValidError as exc:
            logger.warning(f"Niepoprawny e-mail odrzucony: {candidate!r} ({exc})")
            continue
        # Porównanie bez względu na wielkość liter: email_validator normalizuje tylko domenę
        # (część lokalna formalnie bywa wrażliwa na wielkość), ale żaden realny dostawca poczty
        # nie rozróżnia "Biuro@" od "biuro@", a w arkuszu to byłby duplikat.
        if any(result.normalized.lower() == present.lower() for present in normalized):
            continue
        if settings.verify_mx_records and not has_mx_record(result.domain, settings):
            without_mx = True
        normalized.append(result.normalized)

    if not normalized:
        return FieldValue()
    if without_mx:
        logger.warning(f"Domena bez rekordu MX, obniżam pewność: {field.value!r}")
        field.confidence = min(field.confidence, 0.3)

    field.value = separator.join(normalized)
    return field


def validate_url_field(field: FieldValue) -> FieldValue:
    if field.is_empty:
        return field
    value = field.value.strip()
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    field.value = value
    return field


def validate_organization(org: Organization, settings: Settings = settings) -> Organization:
    org.email = validate_email_field(org.email, settings)
    org.website = validate_url_field(org.website)
    org.contact_person.email = validate_email_field(org.contact_person.email, settings)

    has_org_contact = not (org.email.is_empty and org.phone.is_empty and org.website.is_empty)
    has_person_contact = not (org.contact_person.email.is_empty and org.contact_person.phone.is_empty)

    if has_org_contact and has_person_contact:
        org.status = OrganizationStatus.DONE
    elif has_org_contact or has_person_contact:
        org.status = OrganizationStatus.PARTIAL
    else:
        org.status = OrganizationStatus.FAILED

    return org
