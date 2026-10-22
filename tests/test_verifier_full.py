"""Verifier rules against the full league's ground truth (slow): recall on planted cases and the
fire rate on non-trap cases. A rule that fires on more than 10% of non-trap cases needs tuning.

The league seed is OPTIX_VERIFIER_SEED (default 2026), so the test can be run on other leagues:
    OPTIX_VERIFIER_SEED=2029 python -m pytest -m slow tests/test_verifier_full.py

Cases (tests/verifier_cases.py):
  * shot_spam: every (match, team) xG claim. Planted = a planted shot-spam team that trailed for at
    least 45 minutes (the trap only acts while trailing); a spam team that did not trail that long
    is left out of every count. A planted case is a TRUE case unless it is below detection (fewer
    than 12 non-penalty shots while trailing, or no more low-xG shots while trailing than the
    league's share).
  * field_tilt_with_lead: every (match, team) field tilt claim. Planted = the opponent is a planted
    sit-deep team and the subject trailed for at least 45 minutes; same exclusion. True unless below
    detection (fewer than 30 final-third passes while trailing, or a field tilt while trailing
    under 60%).
  * set_piece_inflation: every player's season chances_created claim with >= 4 chances. Positive =
    planted corner specialist.
  * wide_forward_passes: every player's season forward_passes claim with >= 15 passes. Positive =
    planted volume passer.
Recall is asserted on true cases and printed on all planted cases too. Two levels for the match
rules: one full-match claim per team (claim level) and the claims the Analyst proposes while
streaming each match (pipeline level, the one users see).
small_sample_xg, ppda_alone and the three blocking rules have no planted trap; their behaviour is
covered by tests/test_verifier.py.
"""
import os
from collections import Counter

import pytest

from data_gen.generate import main_full
from engine import metrics as M
from engine.claims import build_claim
from engine.tables import load, match_events
from engine.verifier import verdict
from verifier_cases import cases, drop_match_caches, pipeline_claims

pytestmark = pytest.mark.slow

SEED = int(os.environ.get("OPTIX_VERIFIER_SEED", "2026"))
MAX_NON_TRAP_RATE = 0.10
# Pinned just under the Wilson 95% lower bounds of recall on true cases, pooled over the full
# leagues of seeds 2026-2030 after the recall work (docs/verifier-recall.md; tools/verifier_recall.py):
#   claim level    shot_spam  0.89 [0.81-0.93] (85/96)   field_tilt_with_lead  0.53 [0.44-0.63] (56/105)
#   pipeline level shot_spam  0.90 [0.82-0.94] (86/96)   field_tilt_with_lead  0.87 [0.79-0.92] (91/105)
# A pooled bound is a bound on the mean: one league has only 14-25 true cases per rule, so a single
# seed can sit below it (claim-level field tilt does on 2 of the 5 leagues; docs/PROGRESS.md).
MIN_RECALL = {"claim": {"shot_spam": 0.80, "field_tilt_with_lead": 0.43},
              "pipeline": {"shot_spam": 0.81, "field_tilt_with_lead": 0.78}}
# The Analyst proposes several field-tilt windows per match, so the rule fires on unplanted
# chasers far more often than on one full-match claim (14-17% of cases on the 5 leagues). Most of
# those fires are justified by the outcome (the chaser made no more xG than an average chaser);
# the real false positives (more total xG than the league's 75th percentile) are capped
# separately. docs/engine.md, "Reading the field tilt caveat".
MAX_PIPELINE_NON_TRAP_RATE = {"shot_spam": 0.10, "field_tilt_with_lead": 0.20}
MAX_FIELD_TILT_FALSE_POSITIVE_RATE = 0.02


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    out = tmp_path_factory.mktemp("full_verifier")
    gt = main_full(SEED, out)
    return load(out), gt


@pytest.fixture(scope="module")
def match_rule_counts(full):
    """Counter over (level, rule, kind, fired) with kind in true / below_detection / non_trap."""
    ds, gt = full
    res = Counter()
    pipe = {}
    for mid in match_events(ds):
        pipe[mid] = pipeline_claims(ds, mid)
        drop_match_caches(ds)
    for c in cases(ds, gt):
        if c["planted"] is None:
            continue
        kind = "non_trap" if not c["planted"] else "below_detection" if c["reason"] else "true"
        claim = build_claim(ds, c["metric"], "match", {"kind": "team", "id": c["team_id"]}, match_id=c["match_id"],
                            template_key=f"{c['metric']}.stat", param_values=("amount",))
        res[("claim", c["rule"], kind, c["rule"] in verdict(claim, ds).rule_ids)] += 1
        wins = pipe[c["match_id"]].get((c["team_id"], c["metric"]), [])
        fired = [w for w in wins if c["rule"] in w["rules"]]
        res[("pipeline", c["rule"], kind, bool(fired))] += 1
        if kind == "non_trap" and c["rule"] == "field_tilt_with_lead" and fired:
            res["field_tilt_false_positive"] += any(_total_xg_false_positive(ds, c, w["window"]) for w in fired)
    return res


def _total_xg_false_positive(ds, case, window) -> bool:
    """The outcome label of one fire (tools/verifier_recall.py): the chaser made more non-penalty xG
    (every shot) than the league's 75th percentile of chasers over scopes of that length."""
    evs = [e for e in match_events(ds)[case["match_id"]] if window[0] <= e["clock_sec"] <= window[1]]
    r = M.chaser_threat(evs, ds.shots, case["team_id"], M.state_npxg_rates(ds)).value
    line = M.chaser_threat_line(ds, window[1] - window[0])
    return r is not None and line is not None and r > line


def _report(res, level, rule):
    k = lambda kind, fired: res[(level, rule, kind, fired)]
    tp, fn = k("true", True), k("true", False)
    dp, dn = k("below_detection", True), k("below_detection", False)
    fp, tn = k("non_trap", True), k("non_trap", False)
    return dict(tp=tp, fn=fn, recall=tp / max(1, tp + fn), recall_all=(tp + dp) / max(1, tp + fn + dp + dn),
                planted=tp + fn + dp + dn, non_trap_rate=fp / max(1, fp + tn), fp=fp, tn=tn)


@pytest.mark.parametrize("level", ["claim", "pipeline"])
def test_match_rule_recall_and_fire_rate(match_rule_counts, level):
    print(f"\nmatch rules, {level} level (full league, seed {SEED}):")
    for rule in ("shot_spam", "field_tilt_with_lead"):
        r = _report(match_rule_counts, level, rule)
        print(f"  {rule:22s} true cases {r['tp']}/{r['tp'] + r['fn']} recall {r['recall']:.2f}; all planted "
              f"{r['planted']} recall {r['recall_all']:.2f}; non-trap fire rate {r['non_trap_rate']:.3f} "
              f"({r['fp']}/{r['fp'] + r['tn']})")
        assert r["recall"] >= MIN_RECALL[level][rule], (level, rule, r)
        cap = MAX_NON_TRAP_RATE if level == "claim" else MAX_PIPELINE_NON_TRAP_RATE[rule]
        assert r["non_trap_rate"] <= cap, (level, rule, r)
    if level == "pipeline":
        n = sum(v for k, v in match_rule_counts.items() if k[:3] == ("pipeline", "field_tilt_with_lead", "non_trap"))
        fp = match_rule_counts["field_tilt_false_positive"]
        print(f"  field_tilt_with_lead real false positives (total xG above the league's 75th percentile) "
              f"{fp}/{n} = {fp / n:.3f}")
        assert fp / n <= MAX_FIELD_TILT_FALSE_POSITIVE_RATE


def test_player_rule_recall_on_full_league(full):
    ds, gt = full
    planted = {pid: p["trap"] for pid, p in gt["planted_players"].items()}
    res = Counter()
    for pid in ds.players:
        for rule, metric, trap, min_n in (("set_piece_inflation", "chances_created", "corner_specialist", 4),
                                          ("wide_forward_passes", "forward_passes", "volume_passer", 15)):
            c = build_claim(ds, metric, "season", {"kind": "player", "id": pid}, template_key=f"{metric}.stat",
                            param_values=("amount",))
            if c["value"]["amount"] >= min_n:
                res[(rule, planted.get(pid) == trap, rule in verdict(c, ds).rule_ids)] += 1
    print(f"\nplayer rules (full league, seed {SEED}):")
    for rule in ("set_piece_inflation", "wide_forward_passes"):
        tp, fn = res[(rule, True, True)], res[(rule, True, False)]
        fp, tn = res[(rule, False, True)], res[(rule, False, False)]
        print(f"  {rule:22s} planted {tp}/{tp + fn} non-trap fire rate {fp / (fp + tn):.3f} ({fp}/{fp + tn})")
        assert fn == 0 and tp >= 4, (rule, tp, fn)            # 4 plants per league: every one is caught
        assert fp / (fp + tn) <= MAX_NON_TRAP_RATE, (rule, fp, tn)
