"""Test na realnym przypadku ze zgłoszenia użytkownika: serwer zwrócił binarną treść
(PDF) pod adresem trafionym przez crawler jako "podstrona" - traktowanie jej jako HTML
wywalało parser (UnicodeDecodeError). HttpFetcher powinien rozpoznać to po content-type
i zwrócić brak treści zamiast przekazywać binarne dane dalej."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fetch.http_client import HttpFetcher
from config import Settings


@pytest.fixture
def fetcher(tmp_path):
    settings = Settings(cache_dir=tmp_path / "cache")
    instance = HttpFetcher(settings)
    yield instance


async def test_fetch_skips_non_html_content_type(fetcher, monkeypatch):
    response = MagicMock()
    response.headers = {"content-type": "application/pdf"}
    response.status_code = 200
    response.raise_for_status = MagicMock()
    fetcher._client.get = AsyncMock(return_value=response)

    result = await fetcher.fetch("https://example.pl/statut.pdf")

    assert result.html is None
    assert not result.ok
    await fetcher.aclose()


async def test_fetch_keeps_html_content_type(fetcher, monkeypatch):
    response = MagicMock()
    response.headers = {"content-type": "text/html; charset=utf-8"}
    response.status_code = 200
    response.text = "<html><body>OK</body></html>"
    response.raise_for_status = MagicMock()
    fetcher._client.get = AsyncMock(return_value=response)

    result = await fetcher.fetch("https://example.pl/")

    assert result.ok
    assert "OK" in result.html
    await fetcher.aclose()
