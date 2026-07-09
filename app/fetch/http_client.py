"""Pobieranie stron przez httpx: cache, retry z backoffem, limit współbieżności."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
from diskcache import Cache

from app.logging.logger import logger
from config import Settings, settings

# Sygnały wskazujące, że strona jest renderowana przez JavaScript i httpx nie wystarczy.
_JS_APP_ROOT_MARKERS = ('id="root"', 'id="app"', 'id="__next"', "ng-version=")


@dataclass(slots=True)
class FetchResult:
    url: str
    html: str | None
    status_code: int | None
    from_cache: bool
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.html is not None


def needs_browser_rendering(result: FetchResult, settings: Settings = settings) -> bool:
    if not result.ok:
        return True
    html = result.html or ""
    if len(html) < settings.min_text_length_for_static_page:
        return True
    lowered = html.lower()
    return any(marker in lowered for marker in _JS_APP_ROOT_MARKERS)


class HttpFetcher:
    def __init__(self, settings: Settings = settings) -> None:
        self._settings = settings
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = Cache(str(settings.cache_dir))
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._client = httpx.AsyncClient(
            headers={"User-Agent": settings.user_agent},
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )

    async def fetch(self, url: str) -> FetchResult:
        cached_html = self._cache.get(url)
        if cached_html is not None:
            return FetchResult(url=url, html=cached_html, status_code=200, from_cache=True)

        async with self._semaphore:
            result = await self._fetch_with_retry(url)

        if result.ok:
            self._cache.set(url, result.html, expire=self._settings.cache_expire_seconds)
        return result

    async def _fetch_with_retry(self, url: str) -> FetchResult:
        delay = self._settings.backoff_base_seconds
        last_error: str | None = None
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                return FetchResult(url=url, html=response.text, status_code=response.status_code, from_cache=False)
            except httpx.HTTPStatusError as exc:
                last_error = f"HTTP {exc.response.status_code}"
                logger.warning(f"Próba {attempt}/{self._settings.max_retries} nieudana dla {url}: {last_error}")
                if exc.response.status_code in (404, 410):
                    break
            except httpx.HTTPError as exc:
                last_error = str(exc)
                logger.warning(f"Próba {attempt}/{self._settings.max_retries} nieudana dla {url}: {last_error}")
            if attempt < self._settings.max_retries:
                await asyncio.sleep(delay)
                delay *= 2
        return FetchResult(url=url, html=None, status_code=None, from_cache=False, error=last_error)

    async def aclose(self) -> None:
        await self._client.aclose()
        self._cache.close()
