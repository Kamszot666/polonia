"""Wyszukiwanie oficjalnej strony podmiotu przez DuckDuckGo (kroki 2-3 algorytmu z instrukcji)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import tldextract
from rapidfuzz import fuzz

from app.logging.logger import logger
from config import Settings, settings

try:
    from ddgs import DDGS
except ImportError:  # starsza nazwa pakietu, wciąż szeroko używana
    from duckduckgo_search import DDGS

_SOCIAL_AND_DIRECTORY_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "wikipedia.org", "wikipedia.pl",
    "ngo.pl", "rejestr.io", "aleo.com", "panoramafirm.pl", "olx.pl", "gowork.pl",
}


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class DdgsOfficialSiteSearch:
    """Wyszukuje najbardziej prawdopodobną oficjalną stronę podmiotu."""

    def __init__(self, settings: Settings = settings) -> None:
        self._settings = settings

    async def find_official_site(self, organization_name: str) -> SearchResult | None:
        query = self._settings.search_query_template.format(name=organization_name)
        results = await asyncio.to_thread(self._search_sync, query)
        if not results:
            logger.warning(f"Brak wyników wyszukiwania dla: {organization_name!r}")
            return None
        return self._pick_best(organization_name, results)

    def _search_sync(self, query: str) -> list[SearchResult]:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=self._settings.search_max_results, region="pl-pl")
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("href") or item.get("url", ""),
                snippet=item.get("body", ""),
            )
            for item in raw
            if item.get("href") or item.get("url")
        ]

    def _pick_best(self, organization_name: str, results: list[SearchResult]) -> SearchResult | None:
        candidates = [r for r in results if not self._is_excluded_domain(r.url)]
        if not candidates:
            # Lepszy słaby kandydat (np. profil na ngo.pl) niż całkowity brak danych.
            candidates = results

        def score(result: SearchResult) -> float:
            title_score = fuzz.token_set_ratio(organization_name, result.title)
            domain_bonus = 10.0 if self._domain_contains_org_hint(organization_name, result.url) else 0.0
            return title_score + domain_bonus

        best = max(candidates, key=score)
        logger.debug(f"Wybrana strona dla {organization_name!r}: {best.url}")
        return best

    @staticmethod
    def _is_excluded_domain(url: str) -> bool:
        extracted = tldextract.extract(url)
        registered_domain = f"{extracted.domain}.{extracted.suffix}".lower()
        return registered_domain in _SOCIAL_AND_DIRECTORY_DOMAINS

    @staticmethod
    def _domain_contains_org_hint(organization_name: str, url: str) -> bool:
        extracted = tldextract.extract(url)
        domain = extracted.domain.lower()
        name_tokens = [token.lower() for token in organization_name.split() if len(token) > 3]
        return any(token in domain for token in name_tokens)
