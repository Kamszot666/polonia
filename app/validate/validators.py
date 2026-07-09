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
    if field.is_empty:
        return field
    try:
        result = validate_email(field.value, check_deliverability=False)
    except EmailNotValidError as exc:
        logger.warning(f"Niepoprawny e-mail odrzucony: {field.value!r} ({exc})")
        return FieldValue()

    if settings.verify_mx_records and not has_mx_record(result.domain, settings):
        logger.warning(f"Domena bez rekordu MX, obniżam pewność: {field.value!r}")
        field.confidence = min(field.confidence, 0.3)

    field.value = result.normalized
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
