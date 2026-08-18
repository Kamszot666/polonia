"""Centralna konfiguracja projektu. Wszystkie strojenie pipeline'u ma źródło tutaj."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Playwright pip może oczekiwać innej rewizji Chromium niż ta pre-zainstalowana w obrazie
# (PLAYWRIGHT_BROWSERS_PATH) - jeśli plik binarny istnieje, wskazujemy go bezpośrednio
# zamiast pozwalać Playwrightowi na próbę pobrania własnej wersji.
_PREINSTALLED_CHROMIUM = Path("/opt/pw-browsers/chromium")


@dataclass(frozen=True)
class Settings:
    # Sieć
    user_agent: str = (
        "Mozilla/5.0 (compatible; PoloniaContactBot/0.1; "
        "+https://github.com/kamszot666/polonia)"
    )
    request_timeout_seconds: float = 15.0
    max_concurrency: int = 8
    max_retries: int = 3
    backoff_base_seconds: float = 1.5
    # Podstrony jednego serwisu pobierane równolegle (zamiast jedna po drugiej) - i tak
    # obowiązuje globalny limit max_concurrency w HttpFetcher, więc nie zwiększa to obciążenia
    # serwerów ponad ustalony próg, a usuwa martwy czas czekania na każdą stronę po kolei.
    parallel_subpage_fetch: bool = True

    # Playwright uruchamiany tylko gdy httpx nie da wystarczających danych
    playwright_timeout_ms: int = 20_000
    playwright_executable_path: str | None = (
        str(_PREINSTALLED_CHROMIUM) if _PREINSTALLED_CHROMIUM.exists() else None
    )
    # "networkidle" potrafi czekać do pełnego timeoutu na stronach z ciągłym ruchem w tle
    # (czaty, analityka, reklamy). "domcontentloaded" + krótkie dociążenie daje ten sam HTML
    # kilkanaście sekund szybciej.
    browser_wait_until: str = "domcontentloaded"
    browser_settle_ms: int = 1_200
    min_text_length_for_static_page: int = 400

    # Cache
    cache_dir: Path = Path(".cache/polonia_scraper")
    cache_expire_seconds: int = 60 * 60 * 24 * 30  # 30 dni
    # Nieudane pobrania też są zapamiętywane (krócej) - bez tego każdy kolejny przebieg
    # ponawia pełną serię prób z backoffem dla tych samych martwych adresów.
    failed_fetch_cache_seconds: int = 60 * 60 * 6

    # Wyszukiwarka
    search_query_template: str = "{name} kontakt"
    search_max_results: int = 8
    search_min_interval_seconds: float = 4.0  # odstęp między zapytaniami - wyszukiwarka bywa czuła na burst
    search_max_retries: int = 3

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

    # NER / NLP - wymaga wcześniejszego: pip install spacy gliner oraz
    # "python -m spacy download pl_core_news_lg" (main.py sprawdza to na starcie i przerywa
    # z czytelnym komunikatem, jeśli model nie jest zainstalowany, zamiast wywalać się na
    # każdej organizacji z osobna).
    spacy_model_name: str = "pl_core_news_lg"
    gliner_model_name: str = "urchade/gliner_multi-v2.1"
    sentence_transformer_model_name: str = "sdadas/st-polish-paraphrase-from-distilroberta"
    ner_enabled: bool = True
    semantic_scoring_enabled: bool = False  # włączyć po zainstalowaniu modelu sentence-transformers
    # HeuristicPersonNameDetector (bez NER) myliła fragmenty nazwy własnej organizacji, zwroty
    # z przycisków ("Wesprzyj nas na Facebooku") i odmienione przez przypadki słowa
    # instytucjonalne z prawdziwymi osobami - zweryfikowane na realnych danych użytkownika
    # (np. "Konto Fundacji", "Facebooka Wesprzyj" jako rzekome "osoby kontaktowe"). Z
    # ner_enabled=True (spaCy+GLiNER) rozpoznawanie osób jest wystarczająco wiarygodne, by
    # włączyć automatyczne przypisywanie osoby kontaktowej.
    automatic_contact_person_enabled: bool = True
    # Próg dopasowania (RapidFuzz) między już znanym nazwiskiem osoby kontaktowej a kandydatem
    # znalezionym na stronie - używany do dołączenia telefonu/e-maila do ZNANEJ osoby zamiast
    # zgadywania z przypadkowego, niepowiązanego kandydata.
    contact_person_name_match_threshold: float = 80.0
    semantic_score_weight: float = 0.15

    # Wydajność NER. Modele (spaCy + GLiNER) są ładowane raz na proces i współdzielone; bez
    # tego każda strona każdej organizacji ładowała je od nowa z dysku.
    # ner_require_contact_signal: uruchamiaj rozpoznawanie osób tylko w blokach DOM, w których
    # jest e-mail lub telefon. Blok z samym nazwiskiem i tak nigdy nie przekroczy progu
    # contact_person_confidence_threshold (0.25 za osobę + max 0.15 za stanowisko = 0.40),
    # więc jest to wyłącznie oszczędność czasu, bez wpływu na wynik.
    ner_require_contact_signal: bool = True
    # GLiNER i tak przycina wejście do swojego okna kontekstu (stąd ostrzeżenia o truncation) -
    # przycinamy wcześniej, żeby nie płacić za tokenizację odrzucanego tekstu.
    ner_max_text_chars: int = 2_000
    ner_cache_size: int = 4_096

    # Wzbogacanie "Krótkiej charakterystyki podmiotu" - domyślnie pipeline tylko wypełnia puste
    # pole; z tą flagą dokleja też dodatkowy opis znaleziony na stronie do istniejącego, jeśli
    # ten jest ubogi (krótszy niż description_enrich_min_length), zamiast zostawiać go bez zmian.
    enrich_short_descriptions: bool = True
    description_enrich_min_length: int = 200
    description_max_length: int = 600

    # OCR
    ocr_languages: tuple[str, ...] = ("pl", "en")


settings = Settings()
