"""Normalizacja URL - używana przez fetch i parse do deduplikacji linków i kluczy cache."""

from __future__ import annotations

from url_normalize import url_normalize


def normalize_url(url: str) -> str:
    return url_normalize(url)
