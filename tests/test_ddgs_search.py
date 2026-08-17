"""Testy na realnym przypadku ze zgłoszenia użytkownika: wyszukiwarka (backend startpage
w łańcuchu fallback) zwróciła własny link przekierowania zamiast prawdziwego adresu strony,
co wywalało się przy próbie pobrania (ValueError: unknown url type)."""

from app.search.ddgs_search import DdgsOfficialSiteSearch

# Dokładny URL z logu błędów użytkownika (STOWARZYSZENIE POLONIA CONNECT).
_STARTPAGE_REDIRECT_ARTIFACT = (
    "/clev?event=StartpageResultClick&sc=a8mbuE7dQjZSWv5VlrXjKfN0YR93fD1WUtbFMcOCHwAOMQvfDfVbiFEoiTofjCZa"
    "83vmZtjzzaGzOGIpalZe1IHNNadTt9765&payload=%7B%22bdsSessionId%22:%22499998524cb84fef8306c79108254c76%22%7D"
)


def test_rejects_relative_search_engine_redirect_artifact():
    assert DdgsOfficialSiteSearch._is_excluded_result(_STARTPAGE_REDIRECT_ARTIFACT)


def test_accepts_well_formed_official_site():
    assert not DdgsOfficialSiteSearch._is_excluded_result("https://pol.org.pl/kontakt/")


def test_rejects_pdf_result():
    assert DdgsOfficialSiteSearch._is_excluded_result("https://example.pl/statut.pdf")


def test_rejects_directory_domain():
    assert DdgsOfficialSiteSearch._is_excluded_result(
        "https://www.dnb.com/business-directory/company-profiles.example.html"
    )


def test_rejects_url_without_scheme():
    assert DdgsOfficialSiteSearch._is_excluded_result("www.example.pl/kontakt")
