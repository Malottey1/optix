"""Banned intent and causal wording (contracts/banned_language.json): the template linter, the
phraser prompt, and the output guard against model replies that use a banned word or change a
number (both must fall back to the template)."""
import json
from pathlib import Path

import pytest

from agents import narrative, output_guard
from agents.narrative import render
from agents.phraser import SYSTEM_PROMPT, AzureOpenAIPhraser, PhrasingCache
from contracts import banned

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("en", "es", "fr")


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def test_three_lists_in_one_file():
    data = json.loads(banned.PATH.read_text(encoding="utf-8"))
    for lang in LANGS:
        assert len(data[lang]) >= 15, lang
    assert {"because", "on purpose", "in order to", "trap", "plan", "forced", "designed to"} <= set(data["en"])


def test_matcher_is_whole_word_and_case_insensitive():
    assert banned.find("Because they won it back", "en") == ["because"]
    assert banned.find("an explanation of the planet", "en") == []
    assert banned.find("played in  order  to", "en") == ["in  order  to"]
    assert banned.find("lo hizo a propósito", "es") == ["a propósito"]
    assert banned.find("c'est un piège", "fr") == ["piège"]


@pytest.mark.parametrize("lang", LANGS)
def test_template_linter_no_banned_word_in_any_template(lang):
    """Every string of the language's template file: templates, variants, labels, rule reasons."""
    data = json.loads((ROOT / f"agents/templates/{lang}.json").read_text(encoding="utf-8"))
    hits = [(s, banned.find(s, lang) + banned.find(s, "en")) for s in _strings(data)]
    assert [h for h in hits if h[1]] == []


def test_phraser_prompt_has_no_banned_word():
    assert banned.find(SYSTEM_PROMPT) == []


CLAIM = {"claim_id": "clm_test", "claim_type": "milestone", "metric": "milestone_count", "scope": "window",
         "subject": {"kind": "player", "id": "AUR_08", "team_code": "AUR"}, "template_key": "milestone.pass_count",
         "value": {"amount": 50, "unit": "count", "sample_size": 50}, "supporting_values": {},
         "params": {"player": "Ama Tester", "team": "AUR", "amount": 50},
         "verification": {"status": "published", "rule_ids": []}}
KNOWN, NAMES = {"AUR", "Aurelia Rovers", "Ama Tester"}, {"AUR": "Aurelia Rovers"}


def _good():
    return {lang: render(CLAIM["template_key"], CLAIM["params"], lang)["casual"] for lang in LANGS}


def test_the_clean_reply_passes():
    for lang, text in _good().items():
        assert output_guard.check(text, CLAIM, lang, KNOWN, NAMES) == [], (lang, text)


CASES = [(lang, w) for lang in LANGS for w in banned.words(lang)]


@pytest.mark.parametrize("lang,word", CASES, ids=[f"{l}-{w}" for l, w in CASES])
def test_guard_rejects_every_banned_word(lang, word):
    text = _good()[lang].rstrip(".") + f", {word} it."
    problems = output_guard.check(text, CLAIM, lang, KNOWN, NAMES)
    assert any(p.startswith("banned wording") for p in problems), (text, problems)


class FakeClient:
    model = deployment = "fake-model"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, system, user):
        return self.reply


@pytest.mark.parametrize("attack", ["banned", "wrong number"])
def test_a_bad_model_reply_falls_back_to_the_template(tmp_path, attack):
    good = _good()
    bad = dict(good)
    if attack == "banned":
        bad["en"] = "Ama Tester has now completed 50 passes for AUR because they kept the ball."
        bad["fr"] = "Ama Tester a déjà réussi 50 passes pour AUR, exprès dans ce match."
    else:
        bad["en"] = good["en"].replace("50", "51")
        bad["fr"] = good["fr"].replace("50", "500")
    ph = AzureOpenAIPhraser(FakeClient(json.dumps(bad)), KNOWN, NAMES, cache=PhrasingCache(tmp_path / "c"))
    res = ph.phrase(CLAIM, LANGS)
    for lang in ("en", "fr"):
        assert res.rendered[lang] == render(CLAIM["template_key"], CLAIM["params"], lang)
        assert res.source[lang] == "template" and res.guard_rejected[lang]
    assert res.source["es"] == "model"


def test_template_variants_never_carry_banned_words_after_rendering():
    """Rendered sentences too (labels and plural forms are filled in at render time)."""
    for lang in LANGS:
        for key in narrative.templates(lang):
            for s in _strings(narrative.templates(lang)[key]):
                assert banned.find(s, lang) == [], (lang, key, s)
