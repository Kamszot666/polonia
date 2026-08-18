"""Wykrywanie profili organizacji w mediach społecznościowych z linków na stronie.

Schema.org `sameAs` jest źródłem pewniejszym, ale ma je mniejszość stron organizacji
polonijnych - w praktyce profile są dostępne wyłącznie jako ikonki w nagłówku albo stopce
strony kontaktowej, i stamtąd trzeba je wyłuskać.

Zgodnie z wytycznymi użytkownika zostawiamy wyłącznie sześć serwisów (Facebook, LinkedIn,
Instagram, YouTube, X, TikTok) i najwyżej jeden profil na serwis.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

import tldextract
from selectolax.parser import HTMLParser

# Kolejność ma znaczenie - tak profile trafiają do arkusza.
_PLATFORMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Facebook", ("facebook.com", "fb.com", "fb.me")),
    ("LinkedIn", ("linkedin.com", "lnkd.in")),
    ("Instagram", ("instagram.com",)),
    ("YouTube", ("youtube.com", "youtu.be")),
    ("X", ("x.com", "twitter.com")),
    ("TikTok", ("tiktok.com",)),
)

# Ścieżki przycisków „udostępnij", nie profili organizacji. Zweryfikowane realnie: przycisk
# „Podziel się na Facebooku" prowadzi do facebook.com/sharer/sharer.php?u=... i bez tego
# filtra trafiał do arkusza jako rzekomy profil podmiotu.
_SHARE_PATH_MARKERS = (
    "/sharer", "/share", "/intent/", "/dialog/", "/plugins/", "/widgets/",
    "/login", "/signup", "/home", "/help", "/policies", "/privacy", "/terms",
    "/recover", "/hashtag", "/search", "/watch", "/results", "/tr/",
)

# Parametry śledzące - te same linki różnią się nimi i bez czyszczenia dublują się w arkuszu.
_TRACKING_PARAM_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "_ga")
# Parametry widoku, nie identyfikujące profilu (np. youtube.com/channel/UC...?view_as=subscriber).
_NOISE_PARAMS = {"view_as", "hl", "lang", "locale", "sub_confirmation", "app", "igsh", "mibextid"}


def find_social_media_links(html: str, base_url: str) -> list[str]:
    """Zwraca po jednym adresie profilu na serwis, w kolejności z _PLATFORMS."""
    tree = HTMLParser(html)
    best_per_platform: dict[str, str] = {}

    for anchor in tree.css("a[href]"):
        href = (anchor.attributes.get("href") or "").strip()
        if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(base_url, href)
        platform = _match_platform(absolute)
        if platform is None or platform in best_per_platform:
            continue
        if _is_share_or_system_link(absolute):
            continue
        cleaned = clean_social_url(absolute)
        if _is_bare_service_homepage(cleaned):
            # Sam "facebook.com" bez nazwy profilu (link do serwisu, nie do podmiotu).
            continue
        best_per_platform[platform] = cleaned

    return [best_per_platform[name] for name, _ in _PLATFORMS if name in best_per_platform]


def clean_social_url(url: str) -> str:
    """Usuwa parametry śledzące, fragment i końcowy ukośnik (pkt „Strony WWW" wytycznych)."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or ""
    if path.lower().endswith("profile.php"):
        # Starsze profile na Facebooku mają nazwę wyłącznie w parametrze (profile.php?id=...),
        # więc akurat tam zapytania nie można wyciąć.
        kept_params = [part for part in parsed.query.split("&") if part.lower().startswith("id=")]
    else:
        kept_params = [
            part
            for part in parsed.query.split("&")
            if part and not part.split("=", 1)[0].lower().startswith(_TRACKING_PARAM_PREFIXES)
            and part.split("=", 1)[0].lower() not in _NOISE_PARAMS
        ]
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc.startswith("m.") or netloc.startswith("pl-pl."):
        netloc = netloc.split(".", 1)[1]
    return urlunparse((scheme, netloc, path, "", "&".join(kept_params), ""))


def platform_of(url: str) -> str | None:
    return _match_platform(url)


def _match_platform(url: str) -> str | None:
    extracted = tldextract.extract(url)
    registered_domain = f"{extracted.domain}.{extracted.suffix}".lower()
    for name, domains in _PLATFORMS:
        if registered_domain in domains:
            return name
    return None


def _is_share_or_system_link(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(marker in path for marker in _SHARE_PATH_MARKERS)


def _is_bare_service_homepage(url: str) -> bool:
    return urlparse(url).path.strip("/") == ""
