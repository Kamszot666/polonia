"""Konfiguracja loguru używana przez cały pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_LOG_DIR = Path("data/logs")


def configure_logging(*, verbose: bool = False) -> None:
    logger.remove()
    console_level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=console_level, colorize=True,
                format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | "
                       "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(_LOG_DIR / "run_{time:YYYY-MM-DD}.log", level="DEBUG", rotation="1 day",
               retention="30 days", encoding="utf-8")
    logger.add(_LOG_DIR / "errors_{time:YYYY-MM-DD}.log", level="ERROR", rotation="1 day",
               retention="90 days", encoding="utf-8")


__all__ = ["configure_logging", "logger"]
