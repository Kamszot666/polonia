# CLAUDE.md

Wskazówki dla Claude Code (claude.ai/code) przy pracy nad tym repozytorium.

## Czym jest ten projekt

Pipeline budujący bazę danych kontaktowych organizacji wspierających Polonię, mających
siedzibę w Polsce. Na wejściu lista nazw podmiotów albo pełny arkusz bazy do uzupełnienia,
na wyjściu plik Excel z danymi kontaktowymi. Kod i komentarze są po polsku — zachowaj tę
konwencję.

Kluczowa zasada: **pipeline uzupełnia braki, nie nadpisuje**. Pola już wypełnione (np. dane
wprowadzone wcześniej ręcznie i wczytane z pliku wejściowego) zostają nietknięte; dokładane
jest tylko to, czego brakuje. Jedyny wyjątek to wzbogacanie zbyt ubogich opisów
(`enrich_short_descriptions`), które dokleja treść do istniejącej, nie zastępując jej.

## Komendy

```bash
pip install -e ".[dev]"              # zależności
python -m spacy download pl_core_news_lg   # wymagane przy ner_enabled=True
python -m pytest -q                  # testy (asyncio_mode=auto, nie trzeba markerów)
ruff check .                         # lint
python main.py --input plik.xlsx --verbose   # pełny przebieg
```

Nie ma pliku requirements.txt — zależności są w `pyproject.toml`. Wymagany Python >= 3.14.

## Architektura

`main.py` orkiestruje przepływ dla każdego podmiotu:

```
KRS API -> wyszukiwarka -> pobranie stron -> parsowanie -> ekstrakcja -> walidacja -> Excel
```

Moduły w `app/` odpowiadają kolejnym etapom:

- `fetch/http_client.py` — httpx z cache na dysku, ponawianiem i limitem równoległości.
  `needs_browser_rendering` decyduje, czy sięgnąć po przeglądarkę.
- `fetch/browser_client.py` — Playwright **wyłącznie** jako fallback dla stron wymagających
  JavaScriptu. Nie używaj go domyślnie, jest kosztowny.
- `search/ddgs_search.py` — szukanie oficjalnej strony. Backend `html_duckduckgo` jest jedynym
  sprawdzonym; wymusza odstęp między zapytaniami, bo wyszukiwarka blokuje serie zapytań.
- `parse/html_parser.py` — `dom_blocks()` tnie stronę na bloki (section/div/li/tr/p/address),
  które są jednostką analizy dla ekstraktora kontaktów. Bloki są **zagnieżdżone**, więc ten sam
  tekst powtarza się w wielu z nich.
- `extract/contact_relation_extractor.py` — serce projektu: przypisuje e-mail i telefon do
  konkretnej osoby na podstawie współwystępowania w tym samym bloku DOM.
- `validate/validators.py` — walidacja e-maili (składnia + rekordy MX) i ustalanie statusu
  rekordu (done / partial / failed).
- `extract/social_media_extractor.py` — profile z linków na stronie, gdy schema.org `sameAs`
  nie istnieje. Odfiltrowuje przyciski „udostępnij" (`facebook.com/sharer`), zostawia jeden
  profil na serwis i tylko sześć dozwolonych serwisów.
- `extract/registry_extractor.py` — KRS/NIP/REGON z treści strony (regex + sumy kontrolne).
- `extract/address_extractor.py` — adres siedziby; kotwicą jest kod pocztowy, bo w polskich
  adresach występuje praktycznie zawsze.
- `extract/profile_classifier.py` — „Branża / Typ" z formy prawnej w nazwie i „Kategoria"
  z obszaru działania. Słowniki obu leżą w `config.py`, żeby dało się je dopasować do
  nazewnictwa konkretnej bazy bez ruszania kodu.
- `checkpoint/checkpoint_store.py` — SQLite; przebieg można przerwać i wznowić, ukończone
  podmioty nie są przetwarzane ponownie.
- `export/excel_exporter.py` — zapis do arkusza o ustalonym schemacie kolumn.
- `export/excel_formatter.py` — czyszczenie i formatowanie arkusza według standardu obróbki
  arkuszy. Zawsze pisze do **nowego** pliku (`_sformatowany`), nigdy nie nadpisuje wejścia,
  i dokłada arkusz „Raport zmian" z tym, co zostało usunięte. Dostępny też jako
  `scripts/format_workbook.py` dla dowolnego arkusza spoza pipeline'u.

`config.py` zawiera **całe** strojenie pipeline'u w jednej zamrożonej dataclass `Settings`.
Nie rozsiewaj stałych po modułach — dodaj pole tutaj. `Settings` jest hashowalna i bywa
używana jako klucz (współdzielenie modeli NER).

## Modele danych

`app/models/schemas.py`. Każde pole kontaktowe to `FieldValue` niosące wartość **wraz ze
źródłem i pewnością** (`source_url`, `source_type`, `evidence`, `confidence`) — to wymóg
projektu, nie ozdobnik. Nowe pola dodawaj w tej samej konwencji.

## Kilka kontaktów w jednej rubryce

Rubryki telefonu, e-maila i mediów społecznościowych mieszczą po kilka wartości rozdzielonych
`contact_list_separator`. Konsekwencje, o których łatwo zapomnieć:

- `validate_email_field` musi sprawdzać **każdy adres osobno** — jeden błędny nie może
  unieważnić całej rubryki.
- O tym, które trzy adresy zostają, decyduje `rank_emails`. Adresy z obcych domen odpadają,
  gdy podmiot ma choć jeden adres na własnej domenie — strony wymieniają sponsorów wraz z ich
  adresami (`fundacja@kghm.pl` na pol.org.pl) i bez tego zajmowały wolne miejsca.
- Kolejność telefonów bierze się z częstości występowania: numer centrali powtarza się
  na stronie najczęściej.
- Wartość z pliku wejściowego zostaje pierwsza i nietknięta — nowe są dopisywane za nią.

## Skąd biorą się pozostałe rubryki

Kolejność ma znaczenie i jest zamierzona: strona → numer KRS → API KRS → adres, województwo,
NIP, branża. Numer wyłuskany z treści strony otwiera drogę do rejestru, a stamtąd biorą się
rubryki, których na stronie zwykle nie ma wcale — dlatego `_needs_krs_lookup` sprawdzany jest
**po** crawlu, nie tylko przed nim.

Województwo ustalane jest **wyłącznie z adresu**. Szukanie nazwy województwa w całym tekście
strony dawało wyniki wprost błędne (Wspólnota Polska z Krakowskiego Przedmieścia w Warszawie
dostawała „śląskie" od wzmianki w artykule).

## Rozpoznawanie osób

Detekcja nazwisk ma wymienialny interfejs `PersonNameDetector`:

- `HeuristicPersonNameDetector` — regex na parach wielkich liter. Działa bez modeli, ale na
  realnych danych mylił fragmenty nazw organizacji i teksty przycisków z osobami
  („Konto Fundacji", „Facebooka Wesprzyj"). Używany w testach, żeby nie wymagały modeli.
- `NerPersonNameDetector` — spaCy + GLiNER, domyślny przy `ner_enabled=True`.

**Detektor NER musi być współdzielony w obrębie procesu** (`get_person_name_detector`).
Tworzenie go per stronę oznacza ładowanie spaCy i GLiNER z dysku za każdym razem — to była
najdroższa operacja w całym pipeline.

Próg `contact_person_confidence_threshold` (0.55) sprawia, że blok bez e-maila i telefonu
nigdy nie da przyjętego kandydata (maksimum 0.25 za osobę + 0.15 za stanowisko). Dlatego
`ner_require_contact_signal` pomija takie bloki — to oszczędność czasu bez wpływu na wynik.
Jeśli zmieniasz wagi w `_score_candidate`, zweryfikuj, czy to założenie nadal obowiązuje.

## Wydajność

Wąskim gardłem jest CPU (modele NER), nie sieć. Przy zmianach pilnuj, żeby:

- modele ładowały się raz na proces,
- rozpoznawanie osób szło przez `asyncio.to_thread` — w pętli zdarzeń blokuje pobieranie
  stron dla wszystkich pozostałych podmiotów naraz,
- powtórzony tekst bloków nie był analizowany wielokrotnie.

`tests/test_performance_paths.py` pilnuje tych ścieżek — jeśli zaczną padać, coś wróciło do
wolnej wersji.

## Testy

Fixtures w `tests/fixtures/` to **prawdziwe fragmenty HTML** ze stron organizacji polonijnych
(pol.org.pl, wid.org.pl, wspolnotapolska.org.pl). Testy na nich potwierdzają, że selektory
trafiają w realną strukturę stron, a nie w wymyślone dane. Dodając obsługę nowego przypadku,
dołóż fragment prawdziwej strony zamiast pisać syntetyczny HTML.

Testy wołające `extract_contact_candidates` powinny jawnie podawać
`person_detector=HeuristicPersonNameDetector()`, inaczej wymagają pobranych modeli NER.

## Konwencje

- Komentarz w kodzie wyjaśnia **dlaczego**, najlepiej z odniesieniem do realnie zaobserwowanego
  przypadku („zweryfikowane realnie: …"). Nie opisuj tego, co widać w kodzie.
- Lepiej zostawić pole puste niż wpisać zgadywaną wartość — błędne dane kontaktowe są gorsze
  niż ich brak.
