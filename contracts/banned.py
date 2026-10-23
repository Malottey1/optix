"""Banned intent and causal wording (contracts/banned_language.json), one matcher for every check:
the template linter test, the phraser output guard and the UI scan in tools/check_web.py."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parent / "banned_language.json"
LANGUAGES = ("en", "es", "fr")


@lru_cache(maxsize=None)
def words(language: str | None = None) -> tuple:
    """The banned words and phrases of one language, or of all three (language=None)."""
    data = json.loads(PATH.read_text(encoding="utf-8"))
    langs = LANGUAGES if language is None else (language,)
    return tuple(w for lang in langs for w in data.get(lang, ()))


@lru_cache(maxsize=None)
def _pattern(language: str | None) -> re.Pattern:
    alts = sorted((re.escape(w).replace(r"\ ", r"\s+") for w in words(language)), key=len, reverse=True)
    return re.compile(r"(?<![\w])(" + "|".join(alts) + r")(?![\w])", re.IGNORECASE | re.UNICODE)


def find(text: str, language: str | None = None) -> list:
    """Banned words found in `text` (whole words, case-insensitive), in order of appearance."""
    t = unicodedata.normalize("NFC", text)
    return [m.group(1).lower() for m in _pattern(language).finditer(t)]
