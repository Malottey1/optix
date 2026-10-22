"""Verifier rules against the full league's ground truth (slow): precision, recall and the fire rate
on non-trap cases. A rule that fires on more than 10% of non-trap cases needs tuning.

Cases:
  * shot_spam: every (match, team) xG claim. Positive = a planted shot-spam team that trailed for at
    least 45 minutes (the trap only acts while trailing); a spam team that did not trail that long is
    left out of both counts.
  * field_tilt_with_lead: every (match, team) field tilt claim. Positive = the opponent is a planted
    sit-deep team and the subject trailed for at least 45 minutes; same exclusion.
  * set_piece_inflation: every player's season chances_created claim with >= 4 chances. Positive =
    planted corner specialist.
  * wide_forward_passes: every player's season forward_passes claim with >= 15 passes. Positive =
    planted volume passer.
small_sample_xg, ppda_alone and the three blocking rules have no planted trap; their behaviour is
covered by tests/test_verifier.py.
"""
from collections import Counter

import pytest

from data_gen.generate import main_full
from engine.claims import build_claim
from engine.tables import load, match_events, score_diff
from engine.verifier import verdict

pytestmark = pytest.mark.slow

MAX_NON_TRAP_RATE = 0.10
TRAILING_SEC = 2700
# measured on the v2 full league, seed 2026 (shot_spam 13/25, field_tilt_with_lead 22/28) after the
# realism-v2 retune of both rules; pinned about one sampling SD below (25-30 positives per rule)
MIN_MATCH_RECALL = {"shot_spam": 0.42, "field_tilt_with_lead": 0.65}


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    out = tmp_path_factory.mktemp("full_verifier")
    gt = main_full(2026, out)
    return load(out), gt


def _trailing_sec(evs, tid):
    total, prev = 0, None
    for e in evs:
        if prev is not None and score_diff(prev, tid) < 0:
            total += e["clock_sec"] - prev["clock_sec"]
        prev = e
    return total


def _counts(full):
    ds, gt = full
    code = {t["team_id"]: t["code"] for t in ds.teams.values()}
    traps = {c: {x["trap"] for x in v} for c, v in gt["team_traps"].items()}
    planted = {pid: p["trap"] for pid, p in gt["planted_players"].items()}
    res = Counter()
    for mid, evs in match_events(ds).items():
        m = ds.matches[mid]
        for tid, opp in ((m["home_team_id"], m["away_team_id"]), (m["away_team_id"], m["home_team_id"])):
            trailed = _trailing_sec(evs, tid) >= TRAILING_SEC
            for rule, metric, trap, owner in (("shot_spam", "xg", "shot_spam", tid),
                                              ("field_tilt_with_lead", "field_tilt", "sit_deep_when_leading", opp)):
                is_trap = trap in traps.get(code[owner], ())
                if is_trap and not trailed:
                    continue
                c = build_claim(ds, metric, "match", {"kind": "team", "id": tid}, match_id=mid,
                                template_key=f"{metric}.stat", param_values=("amount",))
                res[(rule, is_trap, rule in verdict(c, ds).rule_ids)] += 1
    for pid in ds.players:
        for rule, metric, trap, min_n in (("set_piece_inflation", "chances_created", "corner_specialist", 4),
                                          ("wide_forward_passes", "forward_passes", "volume_passer", 15)):
            c = build_claim(ds, metric, "season", {"kind": "player", "id": pid}, template_key=f"{metric}.stat",
                            param_values=("amount",))
            if c["value"]["amount"] >= min_n:
                res[(rule, planted.get(pid) == trap, rule in verdict(c, ds).rule_ids)] += 1
    return res


def test_rule_precision_recall_on_full_league(full):
    res = _counts(full)
    report = {}
    for rule in ("shot_spam", "field_tilt_with_lead", "set_piece_inflation", "wide_forward_passes"):
        tp, fn = res[(rule, True, True)], res[(rule, True, False)]
        fp, tn = res[(rule, False, True)], res[(rule, False, False)]
        report[rule] = dict(tp=tp, fn=fn, fp=fp, tn=tn, recall=tp / (tp + fn), precision=tp / max(1, tp + fp),
                            non_trap_rate=fp / (fp + tn))
    print("\nrule precision/recall (full league):")
    for rule, r in report.items():
        print(f"  {rule:22s} TP {r['tp']:3d} FN {r['fn']:3d} FP {r['fp']:3d} TN {r['tn']:4d} "
              f"recall {r['recall']:.2f} precision {r['precision']:.2f} non-trap fire rate {r['non_trap_rate']:.3f}")
    for rule, r in report.items():
        assert r["non_trap_rate"] <= MAX_NON_TRAP_RATE, (rule, r)
    assert report["set_piece_inflation"]["recall"] == 1.0
    assert report["wide_forward_passes"]["recall"] == 1.0
    for rule, floor in MIN_MATCH_RECALL.items():
        assert report[rule]["recall"] >= floor, (rule, report[rule])
