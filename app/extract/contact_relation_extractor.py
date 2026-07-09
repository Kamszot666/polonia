"""Przypisywanie e-maila i telefonu do konkretnej osoby kontaktowej.

Wersja bazowa: regex + RapidFuzz + odległość strukturalna/tekstowa w obrębie bloku DOM.
Detekcja osób ma wymienialny interfejs (`PersonNameDetector`) - `HeuristicPersonNameDetector`
działa od razu, `NerPersonNameDetector` (spaCy + GLiNER) to gotowy punkt integracji, włączany
przez `config.settings.ner_enabled` po zainstalowaniu modeli. Podobnie `SemanticIntentScorer`
(sentence-transformers) jest gotowy, ale wyłączony domyślnie (`semantic_scoring_enabled`).
"""

from __future__ import annotations

from typing import Protocol

import regex as re
from rapidfuzz import fuzz

from app.extract.email_extractor import find_emails, find_emails_in_html, score_email
from app.extract.phone_extractor import find_phones
from app.logging.logger import logger
from app.models.schemas import ContactCandidate
from app.parse.html_parser import DomBlock
from config import Settings, settings

_POSITION_KEYWORDS = (
    "prezes zarządu", "wiceprezes zarządu", "prezes", "wiceprezes",
    "dyrektor", "koordynator", "sekretarz", "skarbnik",
    "przewodniczący", "przewodnicząca", "członek zarządu",
    "rzecznik prasowy", "kierownik biura", "prezes fundacji",
)
_POSITION_MATCH_THRESHOLD = 0.75

_NAME_PATTERN = re.compile(
    r"\b([A-ZŚŻŹĆŃÓŁĄĘ][a-ząćęłńóśźż]+(?:-[A-ZŚŻŹĆŃÓŁĄĘ][a-ząćęłńóśźż]+)?)"
    r"\s+([A-ZŚŻŹĆŃÓŁĄĘ][a-ząćęłńóśźż]+(?:-[A-ZŚŻŹĆŃÓŁĄĘ][a-ząćęłńóśźż]+)?)\b"
)
_NAME_FALSE_POSITIVES = {
    "Polska Rzeczpospolita", "Rzeczpospolita Polska", "Unia Europejska",
    "Krajowy Rejestr", "Polityka Prywatności", "Wszystkie Prawa",
}

_INTENT_REFERENCE_SENTENCES = (
    "osoba kontaktowa w organizacji",
    "kontakt w sprawie współpracy",
    "koordynator projektu",
    "sekretariat organizacji",
    "zarząd fundacji lub stowarzyszenia",
    "biuro organizacji",
    "kontakt dla mediów",
)


class PersonNameDetector(Protocol):
    def detect(self, text: str) -> list[str]: ...


class HeuristicPersonNameDetector:
    """Wykrywa pary Imię+Nazwisko po wielkich literach. Prosty fallback do czasu integracji NER."""

    def detect(self, text: str) -> list[str]:
        found: dict[str, None] = {}
        for match in _NAME_PATTERN.finditer(text):
            candidate = f"{match.group(1)} {match.group(2)}"
            if candidate not in _NAME_FALSE_POSITIVES:
                found[candidate] = None
        return list(found)


class NerPersonNameDetector:
    """spaCy (NER) + GLiNER (zero-shot) - punkt integracji NLP. Wymaga config.ner_enabled=True
    oraz pobranych modeli (config.spacy_model_name, config.gliner_model_name)."""

    _SPACY_PERSON_LABELS = {"persName", "PER", "PERSON"}

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._spacy_nlp = None
        self._gliner_model = None

    def _ensure_models_loaded(self) -> None:
        if self._spacy_nlp is None:
            import spacy

            self._spacy_nlp = spacy.load(self._settings.spacy_model_name)
        if self._gliner_model is None:
            from gliner import GLiNER

            self._gliner_model = GLiNER.from_pretrained(self._settings.gliner_model_name)

    def detect(self, text: str) -> list[str]:
        self._ensure_models_loaded()
        found: dict[str, None] = {}

        for ent in self._spacy_nlp(text).ents:
            if ent.label_ in self._SPACY_PERSON_LABELS:
                found[ent.text.strip()] = None

        for entity in self._gliner_model.predict_entities(
            text, labels=["osoba kontaktowa", "członek zarządu", "koordynator"]
        ):
            found[entity["text"].strip()] = None

        return list(found)


def get_person_name_detector(settings: Settings = settings) -> PersonNameDetector:
    if settings.ner_enabled:
        return NerPersonNameDetector(settings)
    return HeuristicPersonNameDetector()


class SemanticIntentScorer:
    """sentence-transformers - ocena podobieństwa bloku do intencji kontaktowej. Wyłączone domyślnie."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._model = None
        self._reference_embeddings = None

    def _ensure_loaded(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._settings.sentence_transformer_model_name)
            self._reference_embeddings = self._model.encode(
                list(_INTENT_REFERENCE_SENTENCES), normalize_embeddings=True
            )

    def score(self, text: str) -> float:
        self._ensure_loaded()
        from sentence_transformers.util import cos_sim

        embedding = self._model.encode(text, normalize_embeddings=True)
        return float(cos_sim(embedding, self._reference_embeddings).max())


def extract_contact_candidates(
    blocks: list[DomBlock],
    source_url: str,
    settings: Settings = settings,
    person_detector: PersonNameDetector | None = None,
    semantic_scorer: SemanticIntentScorer | None = None,
) -> list[ContactCandidate]:
    detector = person_detector or get_person_name_detector(settings)
    candidates: list[ContactCandidate] = []

    for block in blocks:
        text = block.text
        emails = list(dict.fromkeys(find_emails(text) + find_emails_in_html(block.html)))
        phones = find_phones(text)
        persons = detector.detect(text)
        position, position_ratio = _best_position_match(text)

        if not (emails or phones or persons or position):
            continue

        trust_penalty = _low_trust_penalty(text, settings)
        semantic_bonus = 0.0
        if settings.semantic_scoring_enabled and semantic_scorer is not None:
            semantic_bonus = settings.semantic_score_weight * semantic_scorer.score(text)

        for person in persons or [None]:
            for email in emails or [None]:
                for phone in phones or [None]:
                    if person is None and email is None and phone is None:
                        continue
                    base_score = _score_candidate(
                        person=person, position=position, position_ratio=position_ratio,
                        email=email, phone=phone, settings=settings,
                    )
                    confidence = max(0.0, min(1.0, base_score + semantic_bonus - trust_penalty))
                    candidates.append(
                        ContactCandidate(
                            person_name=person,
                            position=position,
                            email=email,
                            phone=phone,
                            confidence=confidence,
                            source_url=source_url,
                            evidence=text[:300],
                            dom_block_selector=block.selector_path,
                        )
                    )

    candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
    return candidates


def select_best_candidate(
    candidates: list[ContactCandidate], settings: Settings = settings
) -> ContactCandidate | None:
    if not candidates:
        return None
    best = candidates[0]
    if best.confidence < settings.contact_person_confidence_threshold:
        logger.debug(f"Najlepszy kandydat ({best.confidence:.2f}) poniżej progu - odrzucony")
        return None
    return best


def _score_candidate(
    *, person: str | None, position: str | None, position_ratio: float,
    email: str | None, phone: str | None, settings: Settings,
) -> float:
    score = 0.0
    if person:
        score += 0.25
    if position:
        score += 0.15 * position_ratio
    if email:
        score += 0.30 * score_email(email)
    if phone:
        score += 0.20
    if person and (email or phone):
        score += settings.same_block_bonus
    return score


def _best_position_match(text: str) -> tuple[str | None, float]:
    lowered = text.lower()
    best_keyword: str | None = None
    best_ratio = 0.0
    for keyword in _POSITION_KEYWORDS:
        ratio = fuzz.partial_ratio(keyword, lowered) / 100.0
        if ratio > best_ratio:
            best_ratio = ratio
            best_keyword = keyword
    if best_ratio >= _POSITION_MATCH_THRESHOLD:
        return best_keyword, best_ratio
    return None, 0.0


def _low_trust_penalty(text: str, settings: Settings) -> float:
    lowered = text.lower()
    hits = sum(1 for phrase in settings.low_trust_phrases if phrase in lowered)
    return min(0.6, hits * 0.3)
