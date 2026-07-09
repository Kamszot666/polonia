"""Centralna konfiguracja projektu. Wszystkie strojenie pipeline'u ma źródło tutaj."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Sieć
    user_agent: str = (
        "Mozilla/5.0 (compatible; PoloniaContactBot/0.1; "
        "+https://github.com/kamszot666/polonia)"
    )
    request_timeout_seconds: float = 15.0
    max_concurrency: int = 5
    max_retries: int = 3
    backoff_base_seconds: float = 1.5

    # Playwright uruchamiany tylko gdy httpx nie da wystarczających danych
    playwright_timeout_ms: int = 20_000
    min_text_length_for_static_page: int = 400

    # Cache
    cache_dir: Path = Path(".cache/polonia_scraper")
    cache_expire_seconds: int = 60 * 60 * 24 * 30  # 30 dni

    # Wyszukiwarka
    search_query_template: str = "{name} kontakt"
    search_max_results: int = 8

    # Podstrony, które warto przeskanować
    subpage_keywords: tuple[str, ...] = (
        "kontakt", "contact", "o-nas", "o nas", "about",
        "zarzad", "zarząd", "board", "wladze", "władze",
        "fundacja", "stowarzyszenie", "dane-kontaktowe",
        "zespol", "zespół", "team", "pracownicy", "staff",
        "rada", "biuro", "sekretariat",
    )
    max_subpages_per_site: int = 8

    # Bloki DOM traktowane jako jednostka analizy w contact_relation_extractor
    dom_block_selectors: tuple[str, ...] = (
        "section", "article", "div", "li", "tr", "p", "address",
    )

    # Frazy obniżające wiarygodność bloku (stopka, RODO, cookies, wykonawca strony)
    low_trust_phrases: tuple[str, ...] = (
        "polityka prywatności", "polityka cookies", "wszystkie prawa zastrzeżone",
        "wykonanie strony", "projekt i wykonanie", "realizacja", "hosting",
        "cookie", "rodo", "regulamin", "copyright",
    )

    # Progi decyzyjne
    contact_person_confidence_threshold: float = 0.55
    same_block_bonus: float = 0.25
    max_dom_distance_for_bonus: int = 3
    max_text_distance_chars_for_bonus: int = 250

    # Checkpoint / storage
    checkpoint_db_path: Path = Path("data/checkpoint.sqlite3")
    output_xlsx_path: Path = Path("data/output/polonia_organizacje.xlsx")

    # Walidacja
    verify_mx_records: bool = True
    dns_resolver_timeout_seconds: float = 5.0

    # NER / NLP (używane przez contact_relation_extractor w kolejnym etapie rozbudowy)
    spacy_model_name: str = "pl_core_news_lg"
    gliner_model_name: str = "urchade/gliner_multi-v2.1"
    sentence_transformer_model_name: str = "sdadas/st-polish-paraphrase-from-distilroberta"
    ner_enabled: bool = False  # włączyć po zainstalowaniu i pobraniu modeli spaCy/GLiNER
    semantic_scoring_enabled: bool = False  # włączyć po zainstalowaniu modelu sentence-transformers
    semantic_score_weight: float = 0.15

    # OCR
    ocr_languages: tuple[str, ...] = ("pl", "en")


settings = Settings()
