"""Playwright jako fallback wyłącznie dla stron wymagających JavaScript (pkt 7 algorytmu)."""

from __future__ import annotations

import os

from playwright.async_api import Browser, Playwright, async_playwright

from app.fetch.http_client import FetchResult
from app.logging.logger import logger
from config import Settings, settings


class BrowserFetcher:
    def __init__(self, settings: Settings = settings) -> None:
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        # Chromium nie honoruje automatycznie HTTPS_PROXY z środowiska (w przeciwieństwie
        # do httpx/curl) - trzeba je przekazać jawnie przy starcie przeglądarki.
        https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        proxy = {"server": https_proxy} if https_proxy else None
        self._browser = await self._playwright.chromium.launch(
            headless=True, executable_path=self._settings.playwright_executable_path, proxy=proxy,
        )

    async def fetch(self, url: str) -> FetchResult:
        if self._browser is None:
            await self.start()
        assert self._browser is not None

        page = await self._browser.new_page(user_agent=self._settings.user_agent)
        try:
            response = await page.goto(
                url, timeout=self._settings.playwright_timeout_ms, wait_until="networkidle",
            )
            html = await page.content()
            status_code = response.status if response else None
            return FetchResult(url=url, html=html, status_code=status_code, from_cache=False)
        except Exception as exc:  # Playwright rzuca różne wyjątki zależnie od przyczyny błędu
            logger.warning(f"Playwright nie pobrał {url}: {exc}")
            return FetchResult(url=url, html=None, status_code=None, from_cache=False, error=str(exc))
        finally:
            await page.close()

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
