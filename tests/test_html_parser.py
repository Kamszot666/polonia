"""Testy na realnych przypadkach ze zgłoszenia użytkownika: linki do PDF/JPG na stronach
organizacji trafiały do kolejki crawlowania i wywalały parser (UnicodeDecodeError)."""

from app.parse.html_parser import PageParser


def test_find_subpage_links_skips_pdf_link():
    html = """
    <html><body>
      <a href="/wp-content/uploads/2026/01/Wejdz-pdf-v2.pdf">Kontakt do zarządu</a>
      <a href="/kontakt/">Kontakt</a>
    </body></html>
    """
    parser = PageParser(html, base_url="https://fundacjaimperio.pl/")
    links = parser.find_subpage_links()

    assert not any(link.endswith(".pdf") for link in links)
    assert any("kontakt" in link for link in links)


def test_find_subpage_links_skips_image_link():
    html = """
    <html><body>
      <a href="/wp-content/uploads/2022/12/zesp%C3%B3%C5%82-Budmo-2.jpg">Zarząd - zdjęcie</a>
    </body></html>
    """
    parser = PageParser(html, base_url="https://ypsilonart.org.pl/")
    links = parser.find_subpage_links()

    assert links == []


def test_find_subpage_links_ignores_query_string_when_checking_extension():
    html = '<html><body><a href="/kontakt.pdf?utm_source=x">Kontakt</a></body></html>'
    parser = PageParser(html, base_url="https://example.pl/")
    assert parser.find_subpage_links() == []
