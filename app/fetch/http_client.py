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

# Błędy sieciowe, których ponawianie nie ma sensu - adres nie istnieje albo jest niepoprawny.
_PERMANENT_NETWORK_ERRORS = (httpx.ConnectError, httpx.UnsupportedProtocol, httpx.InvalidURL)


def _failure_key(url: str) -> str:
    return f"__failed__{url}"


@dataclass(slots=True)
class FetchResult:
    url: str
    html: str | None
    status_code: int | None
    from_cache: bool
    error: str | None = None
    # Niepowodzenie, którego przeglądarka też nie naprawi (nie-HTML content-type, 404/410,
    # nieistniejąca domena) - nie ma sensu uruchamiać dla niego Playwrighta.
    permanent_failure: bool = False

    @property
    def ok(self) -> bool:
        return self.html is not None


def needs_browser_rendering(result: FetchResult, settings: Settings = settings) -> bool:
    if result.permanent_failure:
        # Playwright na pliku PDF, stronie 404 czy martwej domenie to kilkanaście sekund
        # zmarnowane na pewny brak wyniku.
        return False
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
            headers={"User-Agent": settings.user_agent, **dict(settings.default_headers)},
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )

    async def fetch(self, url: str) -> FetchResult:
        cached_html = self._cache.get(url)
        if cached_html is not None:
            return FetchResult(url=url, html=cached_html, status_code=200, from_cache=True)
        cached_error = self._cache.get(_failure_key(url))
        if cached_error is not None:
            # Bez tego każdy kolejny przebieg powtarzał pełną serię prób z backoffem dla tych
            # samych martwych adresów - przy setkach podmiotów to kilkanaście minut na nic.
            return FetchResult(url=url, html=None, status_code=None, from_cache=True,
                                error=cached_error, permanent_failure=True)

        async with self._semaphore:
            result = await self._fetch_with_retry(url)

        if result.ok:
            self._cache.set(url, result.html, expire=self._settings.cache_expire_seconds)
        elif result.permanent_failure:
            self._cache.set(_failure_key(url), result.error or "brak treści HTML",
                             expire=self._settings.failed_fetch_cache_seconds)
        return result

    async def _fetch_with_retry(self, url: str) -> FetchResult:
        delay = self._settings.backoff_base_seconds
        last_error: str | None = None
        permanent = False
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                response = await self._client.get(url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type.lower() and content_type:
                    # Zweryfikowane realnie: linki do PDF/JPG na stronach organizacji trafiały
                    # tu jako "podstrona" i selectolax wywalał się próbując zdekodować binarną
                    # treść jako HTML (UnicodeDecodeError). Traktujemy to jak brak treści HTML.
                    logger.debug(f"Pomijam nie-HTML odpowiedź dla {url}: content-type={content_type}")
                    return FetchResult(url=url, html=None, status_code=response.status_code, from_cache=False,
                                        error=f"nie-HTML content-type: {content_type}", permanent_failure=True)
                return FetchResult(url=url, html=response.text, status_code=response.status_code, from_cache=False)
            except httpx.HTTPStatusError as exc:
                last_error = f"HTTP {exc.response.status_code}"
                logger.warning(f"Próba {attempt}/{self._settings.max_retries} nieudana dla {url}: {last_error}")
                if exc.response.status_code in (404, 410):
                    permanent = True
                    break
                if exc.response.status_code in (401, 403):
                    # Odmowa dostępu nie zmieni się po odczekaniu - ale przeglądarka bywa
                    # wpuszczana tam, gdzie samo httpx nie, więc NIE jest to trwały błąd
                    # i fallback na Playwright ma sens.
                    break
            except _PERMANENT_NETWORK_ERRORS as exc:
                # Nieistniejąca domena, odmowa połączenia albo niepoprawny adres nie zaczną
                # działać po 1,5 s przerwy - ponawianie ich to czysta strata czasu, a w bazie
                # organizacji polonijnych sporo adresów WWW jest już nieaktywnych.
                last_error = str(exc)
                permanent = True
                logger.warning(f"Adres nieosiągalny, nie ponawiam {url}: {last_error}")
                break
            except httpx.HTTPError as exc:
                last_error = str(exc)
                logger.warning(f"Próba {attempt}/{self._settings.max_retries} nieudana dla {url}: {last_error}")
            if attempt < self._settings.max_retries:
                await asyncio.sleep(delay)
                delay *= 2
        return FetchResult(url=url, html=None, status_code=None, from_cache=False, error=last_error,
                            permanent_failure=permanent)

    async def aclose(self) -> None:
        await self._client.aclose()
        self._cache.close()
