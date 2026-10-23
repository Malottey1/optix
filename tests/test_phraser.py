"""Phrasing layer: TemplatePhraser keeps the stream identical; every model reply passes the output
guard or falls back to the template, with the rejection recorded. The model is a fake client."""
import json
from pathlib import Path

import pytest

from agents import output_guard
from agents.narrative import fmt, numeric_params, render
from agents.phraser import (AzureOpenAIPhraser, PhrasingCache, TemplatePhraser, claim_hash, known_entities,
                            model_input, variant_seed)
from agents.stream import InsightStream
from data_gen.generate import main as generate
from engine.tables import load

ROOT = Path(__file__).resolve().parent.parent
MID = "m_showcase"
LANGS = ("en", "es", "fr")


@pytest.fixture(scope="module")
def ds(tmp_path_factory):
    root = tmp_path_factory.mktemp("phraser")
    generate(2026, root / "season", root / "showcase")
    return load(root / "showcase", baseline="season", season_dir=root / "season")


@pytest.fixture(scope="module")
def template_stream(ds):
    s = InsightStream(ds, MID, languages=LANGS, phraser=TemplatePhraser())
    s.run()
    return s


@pytest.fixture(scope="module")
def claims(template_stream):
    return [p.result.claim for p in template_stream.orc.state.published]


def _strip(ins):
    ins = json.loads(json.dumps(ins))
    ins["clock"].pop("emitted_latency_ms")
    return ins


def test_template_phraser_stream_equals_the_golden_stream(template_stream):
    """The committed replay (web/public/data/insights.jsonl) is the golden stream."""
    golden = [json.loads(l) for l in (ROOT / "web/public/data/insights.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [_strip(i) for i in template_stream.insights] == [_strip(i) for i in golden]


def test_default_narrative_is_the_template_phraser(ds, template_stream):
    s = InsightStream(ds, MID, languages=LANGS)
    s.run()
    assert [_strip(i) for i in s.insights] == [_strip(i) for i in template_stream.insights]


def test_every_template_casual_sentence_passes_the_output_guard(ds, claims):
    """The guard must not reject what the engine itself would say."""
    known, names = known_entities(ds)
    for c in claims:
        for lang in LANGS:
            text = render(c["template_key"], c["params"], variant_seed=variant_seed(c), language=lang)["casual"]
            assert output_guard.check(text, c, lang, known, names) == [], (c["claim_id"], lang, text)


def test_the_model_sees_only_the_language_independent_claim(claims):
    c = claims[0]
    m = model_input(c)
    assert "evidence_event_ids" not in m and "rendered" not in json.dumps(m)
    assert set(m["verification"]) == {"status", "rule_ids"}
    assert claim_hash(c) == claim_hash(json.loads(json.dumps(c)))


class FakeClient:
    model = "fake-model"
    deployment = "fake-deployment"

    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.reply(json.loads(user)) if callable(self.reply) else self.reply


def _target(claims):
    """A claim with a team, a decimal and an integer param: the twenty low-xG shots trap."""
    for c in claims:
        nums = numeric_params(c["params"])
        if c["params"].get("team") and any(isinstance(v, float) and not v.is_integer() for v in nums.values()) \
                and any(isinstance(v, int) for v in nums.values()):
            return c
    pytest.fail("no claim with a team, a decimal and an integer param")


def _good(claim):
    return {lang: render(claim["template_key"], claim["params"], variant_seed=variant_seed(claim), language=lang)["casual"]
            for lang in LANGS}


def _phrase(ds, claim, reply, tmp_path):
    known, names = known_entities(ds)
    client = FakeClient(reply)
    ph = AzureOpenAIPhraser(client, known, names, cache=PhrasingCache(tmp_path / "cache"))
    return ph.phrase(claim, LANGS), client, ph


def _decimal(claim):
    return next(v for v in numeric_params(claim["params"]).values() if isinstance(v, float) and not v.is_integer())


def _other_team(ds, claim):
    return next(t["name"] for t in ds.teams.values() if t["code"] not in json.dumps(claim["params"]))


ADVERSARIAL = {
    "altered number": lambda c, ds, s: s.replace(fmt(_decimal(c), "en"), fmt(round(_decimal(c) + 0.1, 3), "en")),
    "invented number": lambda c, ds, s: s.rstrip(".") + " over 7 matches.",
    "different team": lambda c, ds, s: s.rstrip(".") + f", more than {_other_team(ds, c)}.",
    "prediction": lambda c, ds, s: s.rstrip(".") + ", and they will win this.",
    "over-length": lambda c, ds, s: (s + " ") * 6,
    "two lines": lambda c, ds, s: s + "\n" + s,
}


@pytest.mark.parametrize("attack", sorted(ADVERSARIAL))
def test_adversarial_english_reply_is_rejected_and_falls_back(ds, claims, tmp_path, attack):
    c = _target(claims)
    good = _good(c)
    bad = dict(good, en=ADVERSARIAL[attack](c, ds, good["en"]))
    assert bad["en"] != good["en"]
    res, client, _ = _phrase(ds, c, json.dumps(bad), tmp_path)
    tmpl = render(c["template_key"], c["params"], variant_seed=variant_seed(c), language="en")
    assert res.rendered["en"] == tmpl                       # fell back to the exact template
    assert res.guard_rejected["en"] and res.source["en"] == "template"
    assert res.source["es"] == res.source["fr"] == "model"  # the clean languages are kept
    assert len(client.calls) == 1


def test_spanish_reply_with_a_decimal_point_is_rejected(ds, claims, tmp_path):
    c = _target(claims)
    good = _good(c)
    d = _decimal(c)
    assert fmt(d, "es") in good["es"]
    bad = dict(good, es=good["es"].replace(fmt(d, "es"), fmt(d, "en")))
    res, _, _ = _phrase(ds, c, json.dumps(bad), tmp_path)
    assert res.rendered["es"] == render(c["template_key"], c["params"], variant_seed=variant_seed(c), language="es")
    assert any("numbers" in p for p in res.guard_rejected["es"])


def test_reply_in_the_wrong_language_is_rejected(ds, claims, tmp_path):
    c = _target(claims)
    good = _good(c)
    res, _, _ = _phrase(ds, c, json.dumps(dict(good, fr=good["es"])), tmp_path)
    assert any(p.startswith("language") or p.startswith("numbers") for p in res.guard_rejected["fr"])
    assert res.rendered["fr"] == render(c["template_key"], c["params"], variant_seed=variant_seed(c), language="fr")


@pytest.mark.parametrize("reply", ["not json {", "[1, 2]", "", json.dumps({"en": 5})])
def test_malformed_reply_falls_back_everywhere(ds, claims, tmp_path, reply):
    c = _target(claims)
    res, _, _ = _phrase(ds, c, reply, tmp_path)
    assert res.rendered == TemplatePhraser().phrase(c, LANGS).rendered
    assert set(res.guard_rejected) >= {"es", "fr"} and set(res.guard_rejected) <= set(LANGS)


def test_a_failing_client_falls_back(ds, claims, tmp_path):
    def boom(_):
        raise TimeoutError("network")
    c = _target(claims)
    res, _, _ = _phrase(ds, c, boom, tmp_path)
    assert res.rendered == TemplatePhraser().phrase(c, LANGS).rendered
    assert all("TimeoutError" in res.guard_rejected[l][0] for l in LANGS)


def test_accepted_reply_replaces_only_the_casual_tone_and_is_cached(ds, claims, tmp_path):
    c = _target(claims)
    good = _good(c)
    reworded = {l: "Note: " + s for l, s in good.items()}
    reworded["es"] = "Ojo: " + good["es"]
    reworded["fr"] = "À noter : " + good["fr"]
    res, client, ph = _phrase(ds, c, json.dumps(reworded), tmp_path)
    assert res.guard_rejected == {}
    for lang in LANGS:
        assert res.rendered[lang]["casual"] == reworded[lang]
        assert res.rendered[lang]["analyst"] == render(c["template_key"], c["params"], variant_seed=variant_seed(c), language=lang)["analyst"]
    rec = ph.cache.get("fake-model", c)
    assert rec["sentences"] == reworded and rec["claim_hash"] == claim_hash(c)
    assert rec["origin"]["source"] == "azure-openai" and rec["prompt_version"]
    # replay: a second phraser with no client reads the cache and makes no call
    known, names = known_entities(ds)
    off = AzureOpenAIPhraser(None, known, names, cache=ph.cache, model="fake-model")
    again = off.phrase(c, LANGS)
    assert again.rendered == res.rendered and set(again.source.values()) == {"cache"}


def test_a_tampered_cache_entry_is_still_guarded(ds, claims, tmp_path):
    c = _target(claims)
    known, names = known_entities(ds)
    cache = PhrasingCache(tmp_path / "cache")
    cache.put("fake-model", c, {"en": "They will win, odds on, 99 percent."}, {"source": "test"})
    res = AzureOpenAIPhraser(None, known, names, cache=cache, model="fake-model").phrase(c, ("en",))
    assert res.rendered["en"] == render(c["template_key"], c["params"], variant_seed=variant_seed(c), language="en") and res.guard_rejected["en"]


def test_call_cap(ds, claims, tmp_path):
    c = _target(claims)
    known, names = known_entities(ds)
    client = FakeClient("not json")
    ph = AzureOpenAIPhraser(client, known, names, cache=PhrasingCache(tmp_path / "c"), max_calls=2)
    for _ in range(4):
        ph.phrase(c, LANGS)
    assert len(client.calls) == 2
    assert "cap" in ph.phrase(c, LANGS).guard_rejected["en"][0]


def test_stream_with_a_hostile_model_is_the_template_stream(ds, template_stream, tmp_path):
    """Nothing unguarded reaches the stream: a model that always predicts changes no insight."""
    known, names = known_entities(ds)
    hostile = FakeClient(lambda u: {l: "Northgate will win, the odds say 3 to 1." for l in u["languages"]})
    ph = AzureOpenAIPhraser(hostile, known, names, cache=PhrasingCache(tmp_path / "c"), max_calls=1000)
    s = InsightStream(ds, MID, languages=LANGS, phraser=ph)
    s.run()
    assert [_strip(i) for i in s.insights] == [_strip(i) for i in template_stream.insights]
    rej = s.orc.log.where(agent="narrative", event="rendered")
    assert rej and all(set(r["guard_rejected"]) == set(LANGS) for r in rej)
    assert not list((tmp_path / "c").rglob("*.json"))


def test_every_template_reads_as_its_own_language():
    """The guard's language check accepts every template sentence of every key and tone."""
    import string
    from agents.narrative import _plural, labels, variants
    for lang in LANGS:
        for key, _, t in variants(lang):
            for tone, tmpl in t.items():
                tmpl = _plural(tmpl, {}, lang)          # plural forms resolved as at render time
                fields = {f for _, f, _, _ in string.Formatter().parse(tmpl) if f}
                vals = {f: "Kaito Ruvel" for f in fields}
                if "lane_label" in fields:
                    vals["lane_label"] = next(iter(labels(lang)["lane"].values()))
                if "side_label" in fields:
                    vals["side_label"] = next(iter(labels(lang)["side"].values()))
                assert output_guard.language_of(tmpl.format_map(vals)) == lang, (lang, key, tone)
