"""Parsowanie strony przez selectolax: wykrywanie podstron i segmentacja na bloki DOM."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from app.fetch.url_utils import normalize_url
from config import Settings, settings


@dataclass(slots=True)
class DomBlock:
    selector_path: str
    html: str
    text: str


class PageParser:
    """Jedna instancja na jedną pobraną stronę."""

    def __init__(self, html: str, base_url: str, settings: Settings = settings) -> None:
        self._tree = HTMLParser(html)
        self._base_url = base_url
        self._settings = settings

    def find_subpage_links(self) -> list[str]:
        """Wykrywa linki do podstron typu Kontakt/Zarząd/O nas itd. (pkt 5 algorytmu)."""
        found: dict[str, None] = {}
        for anchor in self._tree.css("a[href]"):
            href = anchor.attributes.get("href")
            if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            text = (anchor.text() or "").strip().lower()
            haystack = f"{text} {href.lower()}"
            if any(keyword in haystack for keyword in self._settings.subpage_keywords):
                absolute_url = normalize_url(urljoin(self._base_url, href))
                found[absolute_url] = None
        return list(found)[: self._settings.max_subpages_per_site]

    def dom_blocks(self) -> list[DomBlock]:
        """Dzieli stronę na logiczne bloki DOM do analizy przez contact_relation_extractor (pkt 1 modułu)."""
        blocks: list[DomBlock] = []
        selector = ", ".join(self._settings.dom_block_selectors)
        for index, node in enumerate(self._tree.css(selector)):
            text = (node.text(separator=" ", deep=True) or "").strip()
            if not text:
                continue
            blocks.append(DomBlock(selector_path=f"{node.tag}[{index}]", html=node.html or "", text=text))
        return blocks

    def full_text(self) -> str:
        body = self._tree.body
        if body is not None:
            return (body.text(separator=" ", deep=True) or "").strip()
        return (self._tree.text() or "").strip()

    def meta_description(self) -> str:
        """og:description (Yoast SEO i podobne wtyczki) często zawiera skondensowane dane
        kontaktowe (adres, e-mail, telefon, KRS/NIP/REGON) - potwierdzone na pol.org.pl."""
        for selector in ('meta[property="og:description"]', 'meta[name="description"]'):
            node = self._tree.css_first(selector)
            if node is not None:
                content = node.attributes.get("content")
                if content:
                    return content.strip()
        return ""
