"""Klient oficjalnego, darmowego Otwartego API Krajowego Rejestru Sądowego.

Zweryfikowane na żywym endpoincie (api-krs.ms.gov.pl) dla realnych numerów KRS:
zwraca m.in. adres siedziby, NIP i przeważający przedmiot działalności (PKD), ale NIE
zwraca numeru REGON. Dane osób w składzie organu są w formacie JSON częściowo
zanonimizowane (np. "nazwiskoICzlon": "S******", PESEL z gwiazdkami) - dlatego ten
moduł nie próbuje wydobywać z niego osoby kontaktowej, tylko dane samego podmiotu.

Podmiot bywa zarejestrowany w rejestrze przedsiębiorców (P) i/lub stowarzyszeń (S);
próbujemy P (bogatszy - zawiera PKD) przed S (potwierdzone empirycznie na realnym
numerze KRS prowadzącym działalność gospodarczą).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.logging.logger import logger
from app.models.schemas import FieldValue, SourceType

_API_URL_TEMPLATE = "https://api-krs.ms.gov.pl/api/krs/OdpisAktualny/{krs}?rejestr={rejestr}&format=json"
_REGISTRY_CODES = ("P", "S")


@dataclass(slots=True)
class KrsRecord:
    name: FieldValue = field(default_factory=FieldValue)
    address: FieldValue = field(default_factory=FieldValue)
    voivodeship: FieldValue = field(default_factory=FieldValue)
    nip: FieldValue = field(default_factory=FieldValue)
    industry: FieldValue = field(default_factory=FieldValue)


async def fetch_krs_record(krs_number: str, client: httpx.AsyncClient) -> KrsRecord | None:
    for rejestr in _REGISTRY_CODES:
        source_url = _API_URL_TEMPLATE.format(krs=krs_number, rejestr=rejestr)
        try:
            response = await client.get(source_url, timeout=15.0)
            if response.status_code != 200:
                continue
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug(f"KRS API błąd dla {krs_number!r} (rejestr={rejestr}): {exc}")
            continue

        record = _parse_odpis(payload, source_url)
        if record is not None:
            return record
    return None


def _parse_odpis(payload: dict, source_url: str) -> KrsRecord | None:
    try:
        dane = payload["odpis"]["dane"]
        dzial1 = dane["dzial1"]
        dane_podmiotu = dzial1["danePodmiotu"]
    except (KeyError, TypeError):
        return None

    name = _field(dane_podmiotu.get("nazwa"), source_url, "dzial1.danePodmiotu.nazwa", 0.95)
    nip = _field(
        dane_podmiotu.get("identyfikatory", {}).get("nip"), source_url,
        "dzial1.danePodmiotu.identyfikatory.nip", 0.95,
    )

    siedziba_i_adres = dzial1.get("siedzibaIAdres", {})
    address = _build_address(siedziba_i_adres, source_url)
    voivodeship_raw = siedziba_i_adres.get("siedziba", {}).get("wojewodztwo")
    voivodeship = _field(
        voivodeship_raw.lower() if voivodeship_raw else None, source_url,
        "dzial1.siedzibaIAdres.siedziba.wojewodztwo", 0.9,
    )
    industry = _build_industry(dane.get("dzial3", {}), source_url)

    return KrsRecord(name=name, address=address, voivodeship=voivodeship, nip=nip, industry=industry)


def _field(value: str | None, source_url: str, evidence: str, confidence: float) -> FieldValue:
    if not value:
        return FieldValue()
    return FieldValue(value=value, source_url=source_url, source_type=SourceType.KRS_API,
                       evidence=evidence, confidence=confidence)


def _build_address(siedziba_i_adres: dict, source_url: str) -> FieldValue:
    adres = siedziba_i_adres.get("adres")
    if not adres:
        return FieldValue()
    street_part = " ".join(filter(None, [adres.get("ulica"), adres.get("nrDomu")])).strip()
    if adres.get("nrLokalu"):
        street_part = f"{street_part}/{adres['nrLokalu']}"
    city_part = " ".join(filter(None, [adres.get("kodPocztowy"), adres.get("miejscowosc")])).strip()
    text = ", ".join(filter(None, [street_part, city_part]))
    return _field(text or None, source_url, "dzial1.siedzibaIAdres.adres", 0.9)


def _normalize_case(text: str) -> str:
    """API KRS podaje przedmiot działalności wersalikami ("WYDAWANIE KSIĄŻEK") - w arkuszu
    wygląda to jak krzyk i psuje czytelność kolumny."""
    return text.capitalize() if text.isupper() else text


def _build_industry(dzial2: dict, source_url: str) -> FieldValue:
    przedmiot = dzial2.get("przedmiotDzialalnosci", {}).get("przedmiotPrzewazajacejDzialalnosci") or []
    descriptions = [_normalize_case(item["opis"]) for item in przedmiot if item.get("opis")]
    if not descriptions:
        return FieldValue()
    return _field(
        "; ".join(descriptions), source_url,
        "dzial2.przedmiotDzialalnosci.przedmiotPrzewazajacejDzialalnosci", 0.85,
    )
