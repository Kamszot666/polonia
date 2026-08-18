"""Testy wyłuskiwania profili społecznościowych z linków na stronie.

Fragmenty HTML odwzorowują to, co realnie stoi w stopkach stron organizacji polonijnych:
ikonki serwisów obok przycisków „udostępnij", które prowadzą pod adresy tego samego
serwisu, ale nie są profilem podmiotu.
"""

from app.extract.social_media_extractor import (
    clean_social_url,
    find_social_media_links,
    platform_of,
)


def test_finds_profiles_of_allowed_services():
    html = """
    <footer>
      <a href="https://www.facebook.com/FundacjaWID">Facebook</a>
      <a href="https://www.instagram.com/FundacjaWiD/">Instagram</a>
      <a href="https://www.youtube.com/@fundacjawid">YouTube</a>
      <a href="https://twitter.com/FundacjaWiD">X</a>
      <a href="https://www.linkedin.com/company/fundacja-wid">LinkedIn</a>
      <a href="https://www.tiktok.com/@fundacjawid">TikTok</a>
    </footer>
    """
    links = find_social_media_links(html, "https://wid.org.pl/kontakt/")

    assert links == [
        "https://facebook.com/FundacjaWID",
        "https://linkedin.com/company/fundacja-wid",
        "https://instagram.com/FundacjaWiD",
        "https://youtube.com/@fundacjawid",
        "https://twitter.com/FundacjaWiD",
        "https://tiktok.com/@fundacjawid",
    ]


def test_ignores_services_outside_the_allowed_list():
    html = '<a href="https://vk.com/podmiot">VK</a><a href="https://pinterest.com/podmiot">Pinterest</a>'
    assert find_social_media_links(html, "https://example.pl") == []


def test_ignores_share_buttons():
    """Zweryfikowane realnie: przycisk „Podziel się na Facebooku" prowadzi do
    facebook.com/sharer/sharer.php?u=... i bez filtra trafiał do arkusza jako profil."""
    html = """
    <a href="https://www.facebook.com/sharer/sharer.php?u=https://example.pl">Udostępnij</a>
    <a href="https://twitter.com/intent/tweet?url=https://example.pl">Tweetnij</a>
    """
    assert find_social_media_links(html, "https://example.pl") == []


def test_ignores_bare_service_homepage():
    html = '<a href="https://www.facebook.com/">Jesteśmy na Facebooku</a>'
    assert find_social_media_links(html, "https://example.pl") == []


def test_keeps_only_one_profile_per_service():
    html = """
    <a href="https://facebook.com/pierwszy">FB</a>
    <a href="https://facebook.com/drugi">FB w stopce</a>
    """
    assert find_social_media_links(html, "https://example.pl") == ["https://facebook.com/pierwszy"]


def test_resolves_relative_links_against_base_url():
    html = '<a href="//www.facebook.com/podmiot">FB</a>'
    assert find_social_media_links(html, "https://example.pl") == ["https://facebook.com/podmiot"]


def test_clean_social_url_removes_tracking_and_trailing_slash():
    cleaned = clean_social_url("https://www.instagram.com/podmiot/?utm_source=strona&igsh=abc")
    assert cleaned == "https://instagram.com/podmiot"


def test_clean_social_url_keeps_facebook_profile_id():
    """Starsze strony na Facebooku mają nazwę wyłącznie w parametrze zapytania."""
    cleaned = clean_social_url("https://www.facebook.com/profile.php?id=100064&utm_medium=x")
    assert cleaned == "https://facebook.com/profile.php?id=100064"


def test_platform_of_recognizes_x_under_both_domains():
    assert platform_of("https://twitter.com/podmiot") == "X"
    assert platform_of("https://x.com/podmiot") == "X"
    assert platform_of("https://example.pl") is None
