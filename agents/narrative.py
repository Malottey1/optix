"""Narrative agent: fills a verified claim's template_key with its params. No free text, no numbers
of its own: every number in a sentence is a param, and every numeric param appears in every
sentence (number_guard). Templates live in agents/templates/<language>.json with an "analyst" and
a "casual" variant per template_key.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .messages import RenderedText

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TONES = ("analyst", "casual")
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
_CACHE: dict = {}


def templates(language: str) -> dict:
    if language not in _CACHE:
        _CACHE[language] = json.loads((TEMPLATES_DIR / f"{language}.json").read_text(encoding="utf-8"))
    return _CACHE[language]


def languages() -> list:
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.json"))


def fmt(v) -> str:
    """How a number is written in every language: shortest exact form of the rounded param."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v) if isinstance(v, int) else f"{v:g}"


def numeric_params(params: dict) -> dict:
    return {k: v for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def number_guard(text: str, params: dict) -> list:
    """Problems with the numbers in `text`: a numeric param missing, or a number that is not a param."""
    nums = numeric_params(params)
    found = NUMBER.findall(text)
    problems = [f"param {k}={fmt(v)} missing" for k, v in nums.items() if fmt(v) not in found
                and fmt(abs(v)) not in found]
    allowed = {fmt(v) for v in nums.values()} | {fmt(abs(v)) for v in nums.values()}
    problems += [f"number {n} is not a param" for n in found if n not in allowed and n.lstrip("-") not in allowed]
    return problems


def render(template_key: str, params: dict, language: str) -> dict:
    t = templates(language)[template_key]
    values = {k: fmt(v) for k, v in params.items()}
    return {tone: t[tone].format_map(values) for tone in TONES}


class NarrativeAgent:
    name = "narrative"

    def __init__(self, log, languages_: tuple = ("en",)):
        self.log, self.languages = log, tuple(languages_)

    def write(self, claim: dict) -> RenderedText:
        """Render a verified (published) claim in every configured language and tone."""
        if claim["verification"]["status"] not in ("published", "published_with_context"):
            raise ValueError("only verified claims are narrated")
        key, params = claim["template_key"], claim["params"]
        rendered, problems = {}, []
        for lang in self.languages:
            rendered[lang] = render(key, params, lang)
            for tone, text in rendered[lang].items():
                problems += [f"{lang}/{tone}: {p}" for p in number_guard(text, params)]
        ok = not problems
        self.log(self.name, "rendered", claim_id=claim["claim_id"], template_key=key,
                 languages=list(self.languages), number_guard_passed=ok, problems=problems)
        return RenderedText(key, dict(params), rendered, ok)
