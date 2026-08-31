"""Нормализация описаний и пользовательские подсказки категорий."""

from __future__ import annotations

import re


def description_key(description: str | None) -> str:
    """Ключ для сопоставления похожих платежей (без регистра, сжатые пробелы)."""
    s = re.sub(r"\s+", " ", (description or "").strip()).upper()
    return s[:500]


def descriptions_match(a: str | None, b: str | None) -> bool:
    return description_key(a) == description_key(b) and bool(description_key(a))
