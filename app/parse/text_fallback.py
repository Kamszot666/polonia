"""trafilatura jako fallback ekstrakcji czystego tekstu ze stron trudnych lub zaszumionych."""

from __future__ import annotations

import trafilatura


def extract_clean_text(html: str, url: str | None = None) -> str | None:
    return trafilatura.extract(html, url=url, include_comments=False, include_tables=True)
