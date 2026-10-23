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

from . import telemetry
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
    """template_key -> {"analyst", "casual"}, or a list of such variants, for one language."""
    return {k: v for k, v in _file(language).items() if not k.startswith("_")}


def variants(language: str) -> list:
    """(template_key, index, {"analyst", "casual"}) for every phrasing of every key: a key holds
    one pair or a list of variants (pattern families)."""
    return [(k, i, pair) for k, v in templates(language).items()
            for i, pair in enumerate(v if isinstance(v, list) else [v])]


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


PLURAL = re.compile(r"\{(\w+)\|([^|{}]*)\|([^|{}]*)\}")


def _plural(text: str, params: dict, language: str) -> str:
    """{name|one|other}: the word form for the count in params[name] (en/es: one only for 1; fr:
    one for 0 and 1). The number itself is written separately as {name}."""
    def pick(m):
        v = params.get(m.group(1))
        one = v is not None and (abs(v) < 2 if language == "fr" else v == 1)
        return m.group(2) if one else m.group(3)
    return PLURAL.sub(pick, text)


def _variant(seed, n: int) -> int:
    """A stable variant index for a claim id (sha256, so it does not change between runs)."""
    if not seed or n <= 1:
        return 0
    import hashlib
    return int(hashlib.sha256(str(seed).encode()).hexdigest()[:8], 16) % n


def render(template_key: str, params: dict, language: str, variant_seed: str | None = None) -> dict:
    """The sentence in both tones. A template may be a list of variants: the one used is chosen by
    a stable hash of variant_seed (the claim id), so repeated patterns do not read identically
    across matches while the same claim always reads the same."""
    t = templates(language)[template_for(template_key, params)]
    values = {k: fmt(v, language) for k, v in params.items()}
    if "lane" in params:
        values["lane_label"] = labels(language)["lane"][params["lane"]]
    if "side" in params:
        values["side_label"] = labels(language)["side"][params["side"]]
    if isinstance(t, list):                    # phrasing variants: chosen by the claim id, never at random
        t = t[_variant(variant_seed, len(t))]
    return {tone: _plural(t[tone], params, language).format_map(values) for tone in TONES}


class NarrativeAgent:
    name = "narrative"

    def __init__(self, log, languages_: tuple = ("en",), phraser=None):
        from .phraser import TemplatePhraser
        self.log, self.languages = log, tuple(languages_)
        self.phraser = phraser or TemplatePhraser()      # agents/phraser.py; the template is the default
        self.last_phrase = None

    def write(self, claim: dict) -> RenderedText:
        """Render a verified (published) claim in every configured language and tone. The phraser
        only words it; the number guard then runs again on every sentence, whoever wrote it."""
        if claim["verification"]["status"] not in ("published", "published_with_context"):
            raise ValueError("only verified claims are narrated")
        key, params = claim["template_key"], claim["params"]
        with telemetry.span("phraser.call", claim_id=claim["claim_id"], phraser=self.phraser.name) as put:
            res = self.phraser.phrase(claim, self.languages)
            rendered, problems = res.rendered, []
            for lang in self.languages:
                for tone, text in rendered[lang].items():
                    problems += [f"{lang}/{tone}: {p}" for p in number_guard(text, params, lang)]
            ok = not problems
            put(source=res.source, guard_rejected=sorted(res.guard_rejected), number_guard_passed=ok,
                guard_result="fallback" if res.guard_rejected else "accepted")
        self.last_phrase = res
        self.log(self.name, "rendered", claim_id=claim["claim_id"], template_key=key,
                 languages=list(self.languages), number_guard_passed=ok, problems=problems,
                 phraser=res.phraser, phrase_source=res.source, guard_rejected=res.guard_rejected)
        return RenderedText(key, dict(params), rendered, ok)
