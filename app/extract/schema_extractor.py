"""Odczyt Schema.org / JSON-LD / Microdata / RDFa przez extruct - najbardziej wiarygodne źródło danych."""

from __future__ import annotations

from dataclasses import dataclass

import extruct
from w3lib.html import get_base_url

from app.models.schemas import FieldValue, SourceType

_SCHEMA_CONFIDENCE = 0.9
_ORG_TYPES = {"Organization", "NGO", "LocalBusiness", "Corporation", "GovernmentOrganization"}


@dataclass(slots=True)
class SchemaContactData:
    name: FieldValue
    telephone: FieldValue
    email: FieldValue
    address: FieldValue
    same_as: list[str]


def extract_schema_data(html: str, url: str) -> SchemaContactData:
    base_url = get_base_url(html, url)
    try:
        data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld", "microdata", "rdfa"])
    except Exception:
        data = {}

    org_records = _flatten_organization_records(data)

    return SchemaContactData(
        name=_first_field(org_records, "name", url),
        telephone=_first_field(org_records, "telephone", url),
        email=_first_field(org_records, "email", url),
        address=_first_address_field(org_records, url),
        same_as=_collect_same_as(org_records),
    )


def _flatten_organization_records(data: dict) -> list[dict]:
    records: list[dict] = []
    for syntax_records in data.values():
        _collect_matching(syntax_records, records)
    return records


def _collect_matching(node: object, out: list[dict]) -> None:
    if isinstance(node, dict):
        record_type = node.get("@type")
        type_names = record_type if isinstance(record_type, list) else [record_type]
        if any(name in _ORG_TYPES for name in type_names if name):
            out.append(node)
        for value in node.values():
            _collect_matching(value, out)
    elif isinstance(node, list):
        for item in node:
            _collect_matching(item, out)


def _first_field(records: list[dict], key: str, url: str) -> FieldValue:
    for record in records:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return FieldValue(value=value.strip(), source_url=url, source_type=SourceType.SCHEMA_ORG,
                               evidence=f"schema.org:{key}", confidence=_SCHEMA_CONFIDENCE)
    return FieldValue()


def _first_address_field(records: list[dict], url: str) -> FieldValue:
    for record in records:
        address = record.get("address")
        if isinstance(address, dict):
            parts = [address.get("streetAddress"), address.get("postalCode"), address.get("addressLocality")]
            text = ", ".join(part for part in parts if part)
            if text:
                return FieldValue(value=text, source_url=url, source_type=SourceType.SCHEMA_ORG,
                                   evidence="schema.org:address", confidence=_SCHEMA_CONFIDENCE)
        elif isinstance(address, str) and address.strip():
            return FieldValue(value=address.strip(), source_url=url, source_type=SourceType.SCHEMA_ORG,
                               evidence="schema.org:address", confidence=_SCHEMA_CONFIDENCE)
    return FieldValue()


def _collect_same_as(records: list[dict]) -> list[str]:
    links: list[str] = []
    for record in records:
        same_as = record.get("sameAs")
        if isinstance(same_as, str):
            links.append(same_as)
        elif isinstance(same_as, list):
            links.extend(item for item in same_as if isinstance(item, str))
    return links
