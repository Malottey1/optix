"""Narrative agent: fills a verified claim's template_key with its params. No free text, no numbers
of its own: every number in a sentence is a param, and every numeric param appears in every
sentence (number_guard). Templates live in agents/templates/<language>.json with an "analyst" and
a "casual" variant per template_key, plus `_labels` for string params that need translating (lane
names) and `_rules` (one plain sentence per Verifier rule, no numbers, for the dashboard).
Translation happens here, after verification, and the number guard runs on every language:
numbers are written in the language's own form (decimal comma in es/fr) and must match the params.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .messages import RenderedText

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TONES = ("analyst", "casual")
NUMBER = re.compile(r"(?<![\w.,])-?\d+(?:[.,]\d+)?")
DECIMAL_COMMA = {"es", "fr"}
_CACHE: dict = {}


def _file(language: str) -> dict:
    if language not in _CACHE:
        _CACHE[language] = json.loads((TEMPLATES_DIR / f"{language}.json").read_text(encoding="utf-8"))
    return _CACHE[language]


def templates(language: str) -> dict:
    """template_key -> {"analyst", "casual"} for one language."""
    return {k: v for k, v in _file(language).items() if not k.startswith("_")}


def labels(language: str) -> dict:
    """Translated labels for string params (e.g. labels("es")["lane"]["left_flank"])."""
    return _file(language)["_labels"]


def rule_reasons(language: str) -> dict:
    """rule_id -> one plain sentence (no numbers) saying why the Verifier stopped or reworded a claim."""
    return _file(language)["_rules"]


def languages() -> list:
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.json"))


def fmt(v, language: str = "en") -> str:
    """How a number is written: shortest exact form of the rounded param, with the language's
    decimal separator. Strings pass through."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    out = str(v) if isinstance(v, int) else f"{v:g}"
    return out.replace(".", ",") if language in DECIMAL_COMMA else out


def numeric_params(params: dict) -> dict:
    return {k: v for k, v in params.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def number_guard(text: str, params: dict, language: str = "en") -> list:
    """Problems with the numbers in `text`: a numeric param missing, or a number that is not a param."""
    nums = numeric_params(params)
    found = NUMBER.findall(text)
    problems = [f"param {k}={fmt(v, language)} missing" for k, v in nums.items()
                if fmt(v, language) not in found and fmt(abs(v), language) not in found]
    allowed = {fmt(v, language) for v in nums.values()} | {fmt(abs(v), language) for v in nums.values()}
    problems += [f"number {n} is not a param" for n in found if n not in allowed and n.lstrip("-") not in allowed]
    return problems


# A template variant chosen on a value: (param, value) -> the variant's key suffix. A volume passer
# with no forward pass into a central danger zone reads "not one of them", not "0 times the league".
VARIANTS = {"forward_passes.wide_low_threat": ("pass_quality_ratio", 0, ".none")}


def template_for(template_key: str, params: dict) -> str:
    """The template key to fill: the claim's own key, or its value-chosen variant."""
    v = VARIANTS.get(template_key)
    if v and params.get(v[0]) == v[1]:
        return template_key + v[2]
    return template_key


def render(template_key: str, params: dict, language: str) -> dict:
    t = templates(language)[template_for(template_key, params)]
    values = {k: fmt(v, language) for k, v in params.items()}
    if "lane" in params:
        values["lane_label"] = labels(language)["lane"][params["lane"]]
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
                problems += [f"{lang}/{tone}: {p}" for p in number_guard(text, params, lang)]
        ok = not problems
        self.log(self.name, "rendered", claim_id=claim["claim_id"], template_key=key,
                 languages=list(self.languages), number_guard_passed=ok, problems=problems)
        return RenderedText(key, dict(params), rendered, ok)
