"""Checkpoint w SQLite - status per-organizacja i możliwość wznowienia pracy po przerwaniu."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from app.logging.logger import logger
from app.models.schemas import ContactPerson, FieldValue, Organization, OrganizationStatus, SourceType
from config import Settings, settings

_TERMINAL_STATUSES = {
    OrganizationStatus.DONE.value,
    OrganizationStatus.PARTIAL.value,
    OrganizationStatus.FAILED.value,
}


class CheckpointStore:
    def __init__(self, settings: Settings = settings) -> None:
        self._settings = settings
        settings.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(settings.checkpoint_db_path)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                input_name TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        self._connection.commit()

    def get_status(self, input_name: str) -> str | None:
        cursor = self._connection.execute(
            "SELECT status FROM organizations WHERE input_name = ?", (input_name,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def is_done(self, input_name: str) -> bool:
        return self.get_status(input_name) in _TERMINAL_STATUSES

    def save(self, org: Organization) -> None:
        payload = json.dumps(asdict(org), ensure_ascii=False)
        self._connection.execute(
            """
            INSERT INTO organizations (input_name, status, data_json, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(input_name) DO UPDATE SET
                status = excluded.status,
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
            """,
            (org.input_name, org.status.value, payload),
        )
        self._connection.commit()
        logger.debug(f"Checkpoint zapisany dla {org.input_name!r} ze statusem {org.status.value}")

    def load_all(self) -> list[Organization]:
        cursor = self._connection.execute("SELECT data_json FROM organizations")
        return [_organization_from_dict(json.loads(row[0])) for row in cursor.fetchall()]

    def close(self) -> None:
        self._connection.close()


def _field_value_from_dict(data: dict) -> FieldValue:
    source_type = data.get("source_type")
    return FieldValue(
        value=data.get("value"),
        source_url=data.get("source_url"),
        source_type=SourceType(source_type) if source_type else None,
        evidence=data.get("evidence"),
        confidence=data.get("confidence", 0.0),
    )


def _organization_from_dict(data: dict) -> Organization:
    contact_person_data = data["contact_person"]
    contact_person = ContactPerson(
        name=_field_value_from_dict(contact_person_data["name"]),
        position=_field_value_from_dict(contact_person_data["position"]),
        email=_field_value_from_dict(contact_person_data["email"]),
        phone=_field_value_from_dict(contact_person_data["phone"]),
    )
    return Organization(
        input_name=data["input_name"],
        name=_field_value_from_dict(data["name"]),
        address=_field_value_from_dict(data["address"]),
        voivodeship=_field_value_from_dict(data["voivodeship"]),
        phone=_field_value_from_dict(data["phone"]),
        email=_field_value_from_dict(data["email"]),
        website=_field_value_from_dict(data["website"]),
        social_media=_field_value_from_dict(data["social_media"]),
        contact_person=contact_person,
        description=_field_value_from_dict(data["description"]),
        krs=_field_value_from_dict(data.get("krs", {})),
        regon=_field_value_from_dict(data.get("regon", {})),
        nip=_field_value_from_dict(data.get("nip", {})),
        category=data.get("category"),
        industry=_field_value_from_dict(data.get("industry", {})),
        origin_source_url=data.get("origin_source_url"),
        status=OrganizationStatus(data["status"]),
        error=data.get("error"),
        date_acquired=data.get("date_acquired"),
    )
