from app.extract.contact_relation_extractor import (
    HeuristicPersonNameDetector,
    extract_contact_candidates,
    find_candidate_matching_name,
    select_best_candidate,
)
from app.models.schemas import ContactCandidate
from app.parse.html_parser import DomBlock


def test_heuristic_person_name_detector_finds_capitalized_pairs():
    detector = HeuristicPersonNameDetector()
    names = detector.detect("Prezes zarządu: Jan Kowalski, e-mail: jan.kowalski@example.pl")
    assert "Jan Kowalski" in names


def test_heuristic_person_name_detector_rejects_institutional_word_pairs():
    """Zaobserwowane realnie: heurystyka łapała fragmenty nazwy własnej organizacji
    ("Oświata Polska", "Katalogi Biblioteki") jako rzekome osoby."""
    detector = HeuristicPersonNameDetector()
    assert detector.detect("Fundacja Oświata Polska za Granicą wspiera szkoły.") == []
    assert detector.detect("Katalogi Biblioteki dostępne online.") == []
    # "Dom Polonii" samo w sobie jest odrzucane (słowo instytucjonalne "dom"), ale patron
    # budynku ("Andrzeja Stelmachowskiego") to naprawdę istniejąca postać historyczna -
    # heurystyka słusznie go wykrywa jako parę imię+nazwisko, mimo że to nie jest bieżący
    # kontakt. Tego rozróżnienia nie da się zrobić bez NER/kontekstu.
    names = detector.detect("Dom Polonii im. Andrzeja Stelmachowskiego")
    assert "Dom Polonii" not in names


def test_heuristic_person_name_detector_rejects_organization_name_tokens():
    detector = HeuristicPersonNameDetector()
    names = detector.detect(
        "Towarzystwo Naukowe informuje: sekretarz Jan Kowalski",
        organization_name='Towarzystwo Naukowe Katolickiego Uniwersytetu Lubelskiego',
    )
    assert names == ["Jan Kowalski"]


def test_extract_contact_candidates_prefers_same_block():
    blocks = [
        DomBlock(
            selector_path="div[0]",
            html="",
            text="Koordynator projektu Anna Nowak, e-mail: anna.nowak@fundacja.pl, tel. 22 556 90 02",
        ),
        DomBlock(selector_path="div[1]", html="", text="Wszystkie prawa zastrzeżone. Polityka prywatności."),
    ]
    candidates = extract_contact_candidates(
        blocks, source_url="https://example.pl", person_detector=HeuristicPersonNameDetector(),
    )
    best = select_best_candidate(candidates)

    assert best is not None
    assert best.person_name == "Anna Nowak"
    assert best.email == "anna.nowak@fundacja.pl"


def test_extract_contact_candidates_penalizes_footer_block():
    blocks = [
        DomBlock(
            selector_path="footer[0]",
            html="",
            text="Kontakt: webmaster@example.pl. Polityka prywatności i cookies. Wszystkie prawa zastrzeżone.",
        ),
    ]
    candidates = extract_contact_candidates(
        blocks, source_url="https://example.pl", person_detector=HeuristicPersonNameDetector(),
    )
    assert select_best_candidate(candidates) is None


def _candidate(person_name: str, email: str | None = None, phone: str | None = None) -> ContactCandidate:
    return ContactCandidate(person_name=person_name, email=email, phone=phone, confidence=0.9,
                             source_url="https://example.pl", evidence="", dom_block_selector="")


def test_find_candidate_matching_name_finds_same_person_despite_case():
    candidates = [
        _candidate("Anna Kowalska-Nowak", email="prezes@example.pl"),
        _candidate("Jan Inny", email="jan@example.pl"),
    ]
    match = find_candidate_matching_name(candidates, "anna kowalska-nowak")
    assert match is not None
    assert match.email == "prezes@example.pl"


def test_find_candidate_matching_name_returns_none_when_no_similar_person():
    candidates = [_candidate("Zupełnie Inna Osoba", email="ktos@example.pl")]
    assert find_candidate_matching_name(candidates, "Rafał Cierniak") is None


def test_find_candidate_matching_name_returns_none_for_empty_candidates():
    assert find_candidate_matching_name([], "Rafał Cierniak") is None
