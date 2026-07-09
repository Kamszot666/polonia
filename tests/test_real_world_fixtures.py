"""Testy na prawdziwych fragmentach HTML pobranych z realnych stron organizacji polonijnych
(pol.org.pl, wid.org.pl, wspolnotapolska.org.pl - zob. tests/fixtures/). Cel: potwierdzić, że
generyczne selektory (section/article/div/li/tr/p/address) i ekstraktory faktycznie trafiają
w prawdziwą strukturę stron, a nie tylko w wymyślone dane syntetyczne.
"""

from pathlib import Path

from app.extract.contact_relation_extractor import extract_contact_candidates, select_best_candidate
from app.extract.email_extractor import find_emails_in_html
from app.parse.html_parser import PageParser

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (_FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_pol_org_pl_team_table_rows_yield_high_confidence_candidate():
    """Realna tabela zespołu (<tr><td>...) - selektor 'tr' z instrukcji musi wyłuskać
    osobę, stanowisko, e-mail i telefon z tego samego wiersza."""
    html = _load_fixture("pol_org_pl_zespol_fragment.html")
    parser = PageParser(html, base_url="https://pol.org.pl/zespol-fundacji/")

    blocks = parser.dom_blocks()
    assert any(block.selector_path.startswith("tr[") for block in blocks)

    candidates = extract_contact_candidates(blocks, source_url="https://pol.org.pl/zespol-fundacji/")
    best = select_best_candidate(candidates)

    assert best is not None
    assert best.person_name == "Magdalena Juszczyk"
    assert best.email == "m.juszczyk@pol.org.pl"
    assert best.phone == "+48226285557"


def test_wid_org_pl_cloudflare_obfuscated_email_is_decoded():
    """Prawdziwy adres e-mail na wid.org.pl jest ukryty przez Cloudflare email-obfuscation
    (data-cfemail) i niewidoczny w zwykłym tekście strony - musi zostać zdekodowany z HTML."""
    html = _load_fixture("wid_org_pl_kontakt_fragment.html")
    parser = PageParser(html, base_url="https://wid.org.pl/kontakt/")

    assert "fundacja@wid.org.pl" not in parser.full_text()  # niewidoczne w czystym tekście
    assert find_emails_in_html(html) == ["fundacja@wid.org.pl"]


def test_pol_org_pl_og_description_contains_condensed_contact_data():
    """og:description (Yoast SEO) bywa bogatszy niż treść <body> - musi być odczytany."""
    html = _load_fixture("pol_org_pl_kontakt_meta_fragment.html")
    parser = PageParser(html, base_url="https://pol.org.pl/kontakt/")

    meta = parser.meta_description()
    assert "biuro@pol.org.pl" in meta
    assert "Jazdów 10A" in meta


def test_wspolnotapolska_board_block_without_email_gets_low_confidence():
    """Realna strona władz Wspólnoty Polskiej trzyma nazwisko i stanowisko w bloku DOM
    bez e-maila/telefonu w tym samym miejscu - system nie powinien pewnie przypisać kontaktu
    bez dowodu współwystępowania (pkt 10 modułu contact_relation_extractor)."""
    html = _load_fixture("wspolnotapolska_org_pl_wladze_fragment.html")
    parser = PageParser(html, base_url="https://wspolnotapolska.org.pl/stowarzyszenie/wladze.php")

    candidates = extract_contact_candidates(
        parser.dom_blocks(), source_url="https://wspolnotapolska.org.pl/stowarzyszenie/wladze.php"
    )
    best = select_best_candidate(candidates)

    assert best is None  # brak e-maila/telefonu w bloku -> poniżej progu pewności
