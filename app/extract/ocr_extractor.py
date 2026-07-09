"""EasyOCR - używane wyłącznie gdy dane kontaktowe znajdują się na obrazie, nie w tekście strony."""

from __future__ import annotations

from functools import lru_cache

from config import Settings, settings


@lru_cache(maxsize=1)
def _get_reader(languages: tuple[str, ...]):
    import easyocr  # import odłożony - ciężka zależność, ładowana tylko na żądanie

    return easyocr.Reader(list(languages), gpu=False)


def extract_text_from_image(image: str | bytes, settings: Settings = settings) -> str:
    reader = _get_reader(settings.ocr_languages)
    results = reader.readtext(image, detail=0)
    return "\n".join(results)
