"""Pattern claims end to end: templates, the block-and-revise loop for the naive claims, the
Verifier on pattern evidence (mutations), cross-claim consistency and the ranking caps.

Runs on the generated 2026 season (planted motifs) and its showcase match."""
import json
import re
from pathlib import Path

import jsonschema
import pytest

from agents import narrative as N
from agents import output_guard
from agents.analyst import (COMBINED_REVISIONS, FAMILY_CAP, NOT_REVISABLE, PATTERN_PARAMS, PATTERN_TEMPLATES,
                            PATTERN_ZERO_VARIANTS, REVISIONS, rank_candidates)
from agents.stream import InsightStream
from data_gen.generate import main as generate
from engine import patterns as PAT
from engine.patterns import elastic_low_block, rest_defence, starved_finisher
from engine.rules import PATTERN_RULES
from engine.tables import load, match_events
from engine.claims import build_claim
from engine.verifier import verdict

ROOT = Path(__file__).resolve().parents[1]
MID = "m_showcase"
LANGS = ("en", "es", "fr")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
SEASON_MATCHES = [f"m_{i:03d}" for i in range(1, 13)]


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("patterns")
    generate(2026, root / "season", root / "showcase")
    return (load(root / "showcase", baseline="season", season_dir=root / "season"), load(root / "season"))


def _run(ds, mid):
    s = InsightStream(ds, mid, languages=LANGS)
    results = []
    orig = s.orc.verifier.check

    def check(p, state):
        r = orig(p, state)
        results.append(r)
        return r
    s.orc.verifier.check = check
    s.run()
    return s, results


@pytest.fixture(scope="module")
def showcase(data):
    return _run(data[0], MID)


@pytest.fixture(scope="module")
def season_runs(data):
    return {mid: _run(data[1], mid) for mid in SEASON_MATCHES}


def _all_runs(showcase, season_runs, data):
    yield data[0], MID, showcase
    for mid, run in season_runs.items():
        yield data[1], mid, run


# ---------- templates ----------

def _pairs(key, lang):
    t = N.templates(lang)[key]
    return t if isinstance(t, list) else [t]


def test_pattern_templates_carry_every_param_in_every_variant():
    for fam, base in PATTERN_TEMPLATES.items():
        keys = {base: PATTERN_PARAMS[fam]}
        z = PATTERN_ZERO_VARIANTS.get(fam)
        if z:
            keys[base + z[1]] = tuple(k for k in PATTERN_PARAMS[fam] if k not in z[2])
        for key, params in keys.items():
            for lang in LANGS:
                pairs = _pairs(key, lang)
                assert len(pairs) >= 3, (key, lang)                     # >= 3 phrasings per family
                for pair in pairs:
                    for tone in ("analyst", "casual"):
                        assert set(params) <= set(PLACEHOLDER.findall(pair[tone])), (key, lang, tone)


def test_revised_templates_carry_the_numbers_their_rule_adds():
    for rule, (key, add, _) in REVISIONS.items():
        if rule not in PATTERN_RULES:
            continue
        for lang in LANGS:
            for pair in _pairs(key, lang):
                for tone in ("analyst", "casual"):
                    assert {"amount", *add} <= set(PLACEHOLDER.findall(pair[tone])), (rule, lang, tone)
    for rules, key in COMBINED_REVISIONS.items():
        need = {"amount"} | {k for r in rules for k in REVISIONS[r][1]}
        for lang in LANGS:
            for pair in _pairs(key, lang):
                for tone in ("analyst", "casual"):
                    assert need <= set(PLACEHOLDER.findall(pair[tone])), (key, lang, tone)


def test_every_pattern_rule_has_a_reason_sentence_in_every_language():
    for lang in LANGS:
        for rule in PATTERN_RULES:
            assert N.rule_reasons(lang).get(rule), (lang, rule)
            assert not re.search(r"\d", N.rule_reasons(lang)[rule]), (lang, rule)


def test_variants_are_stable_per_claim_and_spread_across_claims():
    p = {"team": "AUR", "opponent": "NTG", "side": "left", "amount": 2, "build_passes": 16.5, "shots": 1, "xg": 0.2}
    a = N.render("pattern.bait_switch", p, "en", variant_seed="clm_x_pat_bait_switch_t_aur_0_2700")
    assert a == N.render("pattern.bait_switch", p, "en", variant_seed="clm_x_pat_bait_switch_t_aur_0_2700")
    seen = {N.render("pattern.bait_switch", p, "en", variant_seed=f"clm_m_{i:03d}")["analyst"] for i in range(40)}
    assert len(seen) == 3


def test_plural_forms_follow_the_count():
    p = {"team": "AUR", "opponent": "NTG", "amount": 1, "xg": 0.3, "tilt": 66.0}
    one = N.render("pattern.rest_defence", p, "en", variant_seed="s")["analyst"]
    many = N.render("pattern.rest_defence", {**p, "amount": 3}, "en", variant_seed="s")["analyst"]
    assert " 1 shot" in one and " 3 shots" in many
    fr = N.render("pattern.rest_defence", {**p, "amount": 0}, "fr", variant_seed="s")
    assert all(" 0 tirs" not in t for t in fr.values())                       # French: singular for 0


# ---------- the showcase stream ----------

def test_showcase_surfaces_new_families_and_revised_naive_claims(showcase):
    s, results = showcase
    fams = {i["payload"]["family"] for i in s.insights
            if i["insight_type"] == "tactical_pattern" and i["payload"]["claim_metric"].startswith("pat_")}
    # an experimental (disabled) family publishes no card of its own
    assert not {f for f in fams if not PAT.enabled(f)}, fams
    revised = {r.claim["claim_id"].rsplit("_a", 1)[0] for r in results
               if not r.claim["metric"].startswith("pat_")
               and set(r.claim["verification"]["rule_ids"]) & set(PATTERN_RULES)}
    assert len(revised) >= 2, revised
    # the 20000-try search found no seed with four families and two revised naive claims; the
    # brief's fallback is three families, shown as cards or through the rules that rewrote a naive
    # claim (docs/PROGRESS.md, Pattern decisions)
    fired = {PATTERN_RULES[rid] for r in results if not r.claim["metric"].startswith("pat_")
             for rid in r.claim["verification"]["rule_ids"] if rid in PATTERN_RULES}
    assert len(fams | fired) >= 3, (fams, fired)
    traps = {i["insight_type"] for i in s.insights}
    assert {"perimeter_lock", "volume_vs_value", "matchup_mismatch"} <= traps


def test_stream_items_and_claims_follow_the_contracts(showcase, season_runs, data):
    ins_schema = json.loads((ROOT / "contracts/insight.schema.json").read_text())
    claim_schema = json.loads((ROOT / "contracts/claim.schema.json").read_text())
    n = 0
    for _, _, (s, results) in _all_runs(showcase, season_runs, data):
        for i in s.insights:
            jsonschema.validate(i, ins_schema)
        for r in results:
            if r.claim["metric"].startswith("pat_") or set(r.claim["verification"]["rule_ids"]) & set(PATTERN_RULES):
                jsonschema.validate(r.claim, claim_schema)
                n += 1
    assert n > 0


def test_pattern_claims_publish_and_every_number_is_in_every_language(showcase, season_runs, data):
    seen = set()
    for _, _, (s, _) in _all_runs(showcase, season_runs, data):
        for i in s.insights:
            if i["insight_type"] != "tactical_pattern":
                continue
            seen.add(i["payload"]["family"])
            assert i["text"]["number_guard_passed"]
            for lang in LANGS:
                for sentence in i["text"]["rendered"][lang].values():
                    assert not N.number_guard(sentence, i["text"]["params"], lang), sentence
                    assert output_guard.language_of(sentence) == lang, sentence
    assert len(seen) >= 5, seen


def test_no_pattern_claim_is_dropped_by_the_number_guard(showcase, season_runs, data):
    for _, mid, (s, _) in _all_runs(showcase, season_runs, data):
        assert not [d for d in s.orc.state.dropped if d[1] == "number_guard"], mid


def test_stream_is_capped_per_family(showcase, season_runs, data):
    for _, mid, (s, _) in _all_runs(showcase, season_runs, data):
        counts = {}
        for i in s.insights:
            if i["insight_type"] == "tactical_pattern" and i["payload"]["claim_metric"].startswith("pat_"):
                counts[i["payload"]["family"]] = counts.get(i["payload"]["family"], 0) + 1
        assert all(v <= FAMILY_CAP for v in counts.values()), (mid, counts)


# ---------- the Verifier on pattern evidence ----------

def _published_pattern_claims(showcase, season_runs, data):
    for ds, mid, (s, results) in _all_runs(showcase, season_runs, data):
        for r in results:
            if r.claim["metric"].startswith("pat_") and r.status == "published":
                yield ds, s, r.claim


def _check(ds, s, claim):
    return verdict(claim, s.orc.state.view(ds))


def test_pattern_claims_recheck_clean(showcase, season_runs, data):
    n = 0
    for ds, s, c in _published_pattern_claims(showcase, season_runs, data):
        assert _check(ds, s, c).status == "published", c["claim_id"]
        n += 1
    assert n >= 5


def _assert_mutations_blocked(ds, s, c):
    ev = list(c["evidence_event_ids"])
    others = [e["event_id"] for e in match_events(s.orc.state.view(ds))[c["match_id"]]
              if e["event_id"] not in ev and e["event_type"] == "pass"]
    mutations = {"drop": ev[:-1], "foreign": ev[:-1] + [others[len(others) // 2]]}
    if len(ev) >= 2 and ev[0] != ev[1]:
        mutations["swap"] = [ev[1], ev[0]] + ev[2:]
    for name, m in mutations.items():
        bad = dict(c, evidence_event_ids=m)
        v = _check(ds, s, bad)
        assert v.status == "blocked" and v.fact_check == "fail", (c["claim_id"], name)
    wrong = json.loads(json.dumps(c))
    wrong["value"]["amount"] = c["value"]["amount"] + 1
    assert _check(ds, s, wrong).status == "blocked", c["claim_id"]


def test_mutated_pattern_evidence_is_blocked(showcase, season_runs, data):
    n = 0
    for ds, s, c in _published_pattern_claims(showcase, season_runs, data):
        _assert_mutations_blocked(ds, s, c)
        n += 1
    assert n >= 5


@pytest.fixture(scope="module")
def switched_on(data):
    """The showcase with the experimental (disabled) families switched on, as a deployment could."""
    off = [f for f in PAT.FAMILIES if not PAT.enabled(f)]
    for f in off:
        PAT.CONFIG[f]["enabled"] = True
    try:
        return off, _run(data[0], MID)
    finally:
        for f in off:
            PAT.CONFIG[f]["enabled"] = False


def test_experimental_families_are_off_by_default_and_still_verified_when_switched_on(showcase, switched_on, data):
    off, (s, results) = switched_on
    assert set(off) == {"pat_elastic_low_block", "pat_rest_defence",   # docs/pattern-recall.md: experimental
                        "pat_set_piece_dependence"}
    assert not {r.claim["metric"] for r in showcase[1]} & set(off)
    claims = [r.claim for r in results if r.claim["metric"] in off and r.status == "published"]
    assert {c["metric"] for c in claims} == set(off)
    for c in claims:
        assert _check(data[0], s, c).status == "published", c["claim_id"]
        _assert_mutations_blocked(data[0], s, c)


# ---------- cross-claim consistency ----------

def _window(c):
    return c["window"]["from_sec"], c["window"]["to_sec"]


def test_no_unqualified_dominance_claim_where_a_low_block_or_counters_hold(showcase, season_runs, data):
    """A field-tilt claim published without context must not sit in a window where P4 (the
    opponent defends deep) or P6 (the team concedes counters) holds."""
    checked = 0
    for ds, mid, (s, results) in _all_runs(showcase, season_runs, data):
        view = s.orc.state.view(ds)
        m = view.matches[mid]
        for r in results:
            c = r.claim
            if c["metric"] != "field_tilt" or c["subject"]["kind"] != "team" or r.status != "published":
                continue
            tid = c["subject"]["id"]
            opp = m["away_team_id"] if tid == m["home_team_id"] else m["home_team_id"]
            lo, hi = _window(c)
            evs = [e for e in match_events(view)[mid] if lo <= e["clock_sec"] <= hi]
            assert rest_defence.detect(view, evs, tid) is None, c["claim_id"]
            low = elastic_low_block.detect(view, mid, opp, hi)
            assert low is None or low.window[1] < lo or low.window[0] > hi, c["claim_id"]
            checked += 1
    assert checked >= 1


def test_dominance_claims_in_p4_or_p6_windows_carry_the_caveat(showcase):
    s, results = showcase
    tilt = [r for r in results if r.claim["metric"] == "field_tilt" and r.status != "blocked"
            and set(r.claim["verification"]["rule_ids"]) & {"ctx_tilt_without_access",
                                                            "ctx_dominance_with_transition_exposure",
                                                            "field_tilt_with_lead"}]
    assert tilt and all(r.status == "published_with_context" for r in tilt)


def test_no_quiet_game_claim_beside_a_starved_finisher(showcase, season_runs, data):
    blocked = 0
    for ds, mid, (s, results) in _all_runs(showcase, season_runs, data):
        view = s.orc.state.view(ds)
        published = {r.claim["subject"]["id"] for r in results
                     if r.claim["metric"] == "player_touches" and r.status != "blocked"}
        for tid in (view.matches[mid]["home_team_id"], view.matches[mid]["away_team_id"]):
            for f in starved_finisher.detect(view, match_events(view)[mid], tid):
                assert f.player_id not in published, (mid, f.player_id)
        for r in results:
            if "ctx_low_volume_high_quality" in r.claim["verification"]["rule_ids"]:
                assert r.status == "blocked"
                assert any(d[0] == r.claim["claim_id"] and "ctx_low_volume_high_quality" in d[1]
                           for d in s.orc.state.dropped)            # blocked, never rephrased
    # and the rule itself: the naive claim about every starved finisher found is blocked, never revised
    for ds, mid, (s, _) in _all_runs(showcase, season_runs, data):
        view = s.orc.state.view(ds)
        for tid in (view.matches[mid]["home_team_id"], view.matches[mid]["away_team_id"]):
            for f in starved_finisher.detect(view, match_events(view)[mid], tid):
                c = build_claim(view, "player_touches", "match", {"kind": "player", "id": f.player_id}, match_id=mid,
                                template_key="touches.quiet", param_values=("amount",),
                                extra_params={"team": view.code(tid), "player": "P"})
                v = verdict(c, view)
                assert v.status == "blocked" and "ctx_low_volume_high_quality" in v.rule_ids, (mid, f.player_id)
                blocked += 1
    assert blocked >= 1 and "ctx_low_volume_high_quality" in NOT_REVISABLE


# ---------- ranking ----------

def _c(fam, tid="t_a", mag=3.0, score=1.0, key=""):
    return dict(family=fam, team_id=tid, magnitude=mag, score=score, key=key)


def test_ranking_puts_the_best_of_each_family_first_and_caps_families():
    cands = [_c("a", key="1"), _c("a", key="2"), _c("a", key="3"), _c("a", key="4"), _c("b", score=0.9)]
    counts = {}
    out = rank_candidates(cands, None, counts)
    assert [c["family"] for c in out][:2] == ["a", "b"]
    assert sum(c["family"] == "a" for c in out) == FAMILY_CAP and counts["a"] == FAMILY_CAP
    assert rank_candidates([_c("a", key="9")], None, counts) == []                  # cap holds over the match


def test_novelty_down_weights_a_repeat_unless_the_magnitude_moved():
    hist = {"t_a": [{"a": 3.0}]}
    same = rank_candidates([_c("a", score=1.0), _c("b", score=0.6)], hist, {}, per_summary=1)
    assert same[0]["family"] == "b"                                                 # 1.0 * 0.5 < 0.6
    assert [c["family"] for c in rank_candidates([_c("a", score=1.0)], hist, {})] == []   # held back
    moved = rank_candidates([_c("a", mag=5.0, score=1.0), _c("b", score=0.6)], hist, {}, per_summary=1)
    assert moved[0]["family"] == "a"                                                # +67%, +2: no penalty
    # +33% but one more instance: noise in a small count, still a repeat
    assert rank_candidates([_c("a", mag=4.0, score=1.0)], hist, {}) == []
    assert rank_candidates([_c("a", mag=2.0, score=1.0)], {"t_a": [{"a": 1.0}]}, {}) == []
    assert rank_candidates([_c("a"), _c("b", score=0.6)], None, {}, per_summary=1)[0]["family"] == "a"


def test_full_time_does_not_repeat_half_time_unless_it_moved():
    shown = {}
    assert rank_candidates([_c("a", mag=2.0)], None, {}, shown=shown)
    assert rank_candidates([_c("a", mag=2.0)], None, {}, shown=shown) == []
    assert rank_candidates([_c("a", mag=3.0)], None, {}, shown=shown) == []        # +1: not a move
    assert rank_candidates([_c("a", mag=4.0)], None, {}, shown=shown)


def test_partial_matches_skip_full_match_only_families():
    assert PAT.FULL_MATCH_ONLY == ("pat_starved_finisher",)


# ---------- templates with edge values ----------

EDGE = (0, 1, 2, 1234, 12.5)
PATTERN_KEYS = sorted({k for k in N.templates("en") if k.startswith("pattern.")}
                      | {REVISIONS[r][0] for r in PATTERN_RULES if r in REVISIONS}
                      | set(COMBINED_REVISIONS.values())
                      | {"attack_side.stat", "crosses.stat", "f3_volume.stat", "f3_losses.stat", "fouls.stat",
                         "touches.quiet"})
STRINGS = {"team": "AUR", "opponent": "NTG", "player": "Kaito Ruvel", "side": "left"}


@pytest.mark.parametrize("key", PATTERN_KEYS)
def test_every_pattern_template_renders_edge_values_in_every_language(key):
    from contracts import banned
    names = set()
    for pair in _pairs(key, "en"):
        for tone in ("analyst", "casual"):
            names |= set(PLACEHOLDER.findall(pair[tone]))
    names -= {"side_label", "lane_label"} | set(STRINGS)
    for v in EDGE:
        params = {**STRINGS, **{n: v for n in names}}
        for lang in LANGS:
            for k in range(len(_pairs(key, lang))):
                out = N.render(key, params, lang, variant_seed=None if k == 0 else f"seed{k}")
                for tone, s in out.items():
                    assert "{" not in s and "}" not in s, (key, lang, tone, s)
                    assert not N.number_guard(s, params, lang), (key, lang, tone, v, s)
                    assert banned.find(s, lang) == [], (key, lang, s)
                    assert len(s) <= output_guard.MAX_LEN, (key, lang, tone, len(s))
                    if v == 1 and lang == "en":
                        assert not re.search(r"\b1 (shots|touches|times|spells|switches|fouls|crosses|losses)\b", s), s
                    if v in (0, 1) and lang == "fr":
                        assert not re.search(r"\b[01] (tirs|fautes|séquences|pertes|ballons)\b", s), s
                    if v == 2 and lang == "en":
                        assert not re.search(r"\b2 (shot|touch|spell|switch|foul|cross|loss)\b", s), s


def test_variant_seeds_reach_every_variant():
    seen = {N._variant(f"clm_m_{i:03d}_x", 3) for i in range(30)}
    assert seen == {0, 1, 2}


# ---------- Tier 2 trap rules: the naive claim with and without the pattern ----------

TIER2 = {  # rule -> (family, naive metric, subject kind)
    "ctx_xg_from_set_pieces": ("pat_set_piece_dependence", "xg", "team"),
    "ctx_low_possession_with_direct_threat": ("pat_direct_transition", "possession_pct", "team"),
    "ctx_completion_without_pressure_split": ("pat_press_resistant", "pass_completion", "player"),
    "ctx_press_without_secure_build_up": ("pat_pressed_presser", "ppda", "team"),
}


def _naive_claim(ds, mid, metric, subject, rule=None):
    params = dict(REVISIONS[rule][2]) if rule else {}
    keys = ("amount",) + (tuple(REVISIONS[rule][1]) if rule else ())
    t1 = max(e["clock_sec"] for e in match_events(ds)[mid])
    return build_claim(ds, metric, "window", subject, template_key="x", params=params, match_id=mid,
                       window=(0, t1), param_values=keys, extra_params={"team": "T"})


@pytest.mark.parametrize("rule", sorted(TIER2))
def test_tier2_rule_fires_with_the_pattern_and_not_without(data, rule):
    """Where the detector finds the pattern, the plain claim is held for context and the revised one
    publishes with it; where it does not, the rule stays quiet."""
    family, metric, kind = TIER2[rule]
    ds = data[1]
    hit = miss = None
    for mid, m in sorted(ds.matches.items()):
        for tid in (m["home_team_id"], m["away_team_id"]):
            fs = PAT.detect_team(ds, mid, tid, families=[family])
            if kind == "player":
                subj = ({"kind": "player", "id": fs[0].player_id} if fs else
                        {"kind": "player", "id": next(e["player_id"] for e in match_events(ds)[mid]
                                                      if e["team_id"] == tid and e["event_type"] == "pass")})
            else:
                subj = {"kind": "team", "id": tid}
            if fs and hit is None:
                hit = (mid, subj)
            if not fs and miss is None:
                miss = (mid, subj)
        if hit and miss:
            break
    assert hit and miss, rule
    v = verdict(_naive_claim(ds, hit[0], metric, hit[1]), ds)
    assert rule in v.rule_ids and v.status == "blocked" and rule in v.revision_hint
    rv = verdict(_naive_claim(ds, hit[0], metric, hit[1], rule), ds)
    assert rv.fact_check == "pass" and rule in rv.rule_ids and rule not in rv.revision_hint
    assert rule not in verdict(_naive_claim(ds, miss[0], metric, miss[1]), ds).rule_ids
