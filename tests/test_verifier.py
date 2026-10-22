"""Verifier: fact check on the claim object, then one test per context rule.

Rules must fire where the showcase plants the trap, and must not fire on genuine dominance (CAL
level or ahead with real box entries) or on a team with high territory that gets into the box.
"""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from data_gen.generate import main as generate
from engine import metrics as M
from engine.claims import build_claim
from engine.matchup import matchup_claim
from engine.rules import RULES, field_tilt_with_lead
from engine.tables import load, match_events, score_diff
from engine.verifier import verdict, verify

ROOT = Path(__file__).resolve().parent.parent
MID = "m_showcase"


def team(t):
    return {"kind": "team", "id": t}


def player(p):
    return {"kind": "player", "id": p}


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("verifier")
    gt = generate(2026, root / "season", root / "showcase")
    season = load(root / "season")
    sc = load(root / "showcase", baseline="season", season_dir=root / "season")
    return season, sc, gt


@pytest.fixture(scope="module")
def validator():
    return Draft202012Validator(json.loads((ROOT / "contracts" / "claim.schema.json").read_text()))


def claim_on(sc, metric, subject, scope="match", window=None, **kw):
    kw.setdefault("template_key", f"{metric}.stat")
    kw.setdefault("param_values", ("amount",))
    return build_claim(sc, metric, scope, subject, match_id=MID if scope != "season" else None, window=window, **kw)


def status(claim, ds):
    v = verdict(claim, ds)
    return v.status, v.rule_ids


# ---------- fact check ----------

def test_honest_claim_passes_and_verified_claim_validates(data, validator):
    # AUR has only six shots in the v2 showcase (small_sample_xg rightly fires), so the honest
    # claim is AUR's season xG, built and verified on the season data
    season, _, _ = data
    c = build_claim(season, "xg", "season", team("t_aur"), template_key="xg.stat", param_values=("amount",))
    out = verify(c, season)
    assert out["verification"]["fact_check"] == "pass"
    assert out["verification"]["status"] == "published"
    assert out["verification"]["actual_value"] == pytest.approx(c["value"]["amount"], abs=0.005)
    assert not list(validator.iter_errors(out))
    assert c["verification"] == {"status": "pending", "attempt": 1}      # input untouched


def test_tampered_amount_is_value_mismatch(data):
    _, sc, _ = data
    c = claim_on(sc, "xg", team("t_aur"))
    c["value"]["amount"] = round(c["value"]["amount"] + 0.3, 2)
    c["params"]["amount"] = c["value"]["amount"]
    assert status(c, sc) == ("blocked", ["value_mismatch"])


def test_tampered_supporting_value_is_value_mismatch(data):
    _, sc, _ = data
    c = claim_on(sc, "field_tilt", team("t_nor"))
    c["supporting_values"]["box_entries"] += 5
    assert status(c, sc) == ("blocked", ["value_mismatch"])


def test_param_number_backed_by_nothing_is_value_mismatch(data):
    _, sc, _ = data
    c = claim_on(sc, "xg", team("t_aur"))
    c["params"]["shots_on_target"] = 7
    assert status(c, sc) == ("blocked", ["value_mismatch"])


def test_unknown_or_wrong_evidence_is_missing_evidence(data):
    _, sc, _ = data
    c = claim_on(sc, "xg", team("t_aur"))
    bad = copy.deepcopy(c)
    bad["evidence_event_ids"] = ["m_showcase_e99999"]
    assert status(bad, sc) == ("blocked", ["missing_evidence"])
    wrong = copy.deepcopy(c)        # a NOR shot does not support an AUR xG claim
    nor_shot = next(e["event_id"] for e in sc.events if e["event_type"] == "shot" and e["team_id"] == "t_nor")
    wrong["evidence_event_ids"] = c["evidence_event_ids"][:2] + [nor_shot]
    assert status(wrong, sc) == ("blocked", ["missing_evidence"])
    empty = copy.deepcopy(c)
    empty["evidence_event_ids"] = []
    assert status(empty, sc)[1] == ["missing_evidence"]


def test_window_claim_evidence_must_be_inside_the_window(data):
    _, sc, _ = data
    c = claim_on(sc, "field_tilt", team("t_nor"), scope="window", window=(2700, 5400))
    early = next(e["event_id"] for e in sc.events if e["team_id"] == "t_nor" and e["event_type"] == "pass"
                 and e["outcome"] == "success" and e["x_start"] >= 66.7 and e["clock_sec"] < 2700)
    c["evidence_event_ids"].append(early)
    assert status(c, sc)[1] == ["missing_evidence"]


def test_season_matchup_claim_is_verified(data):
    season, _, _ = data
    c = matchup_claim(season, "t_aur", "t_nor")
    assert status(c, season) == ("published", [])
    c["supporting_values"]["concede_completion"] += 2.0
    assert status(c, season) == ("blocked", ["value_mismatch"])


def test_attempt_number_is_kept(data):
    _, sc, _ = data
    c = claim_on(sc, "xg", team("t_aur"), attempt=3)
    assert verify(c, sc)["verification"]["attempt"] == 3


# ---------- rules fire where the showcase plants the trap ----------

def test_every_rule_is_registered_once():
    ids = [r.RULE_ID for r in RULES]
    assert len(ids) == len(set(ids)) == 9


def test_field_tilt_with_lead_fires_on_nor_in_showcase(data):
    _, sc, gt = data
    w = gt["showcase"]["traps"]["field_tilt_while_leading"]["window_sec"]
    raw = claim_on(sc, "field_tilt", team("t_nor"), scope="window", window=tuple(w))
    v = verdict(raw, sc)        # "NOR have 76% field tilt" on its own: blocked, told to add box entries
    assert v.status == "blocked" and "field_tilt_with_lead" in v.rule_ids
    assert v.context_note == "field_tilt.trailing_vs_deep_block"
    assert v.revision_hint == {"field_tilt_with_lead": ["box_entries"]}
    assert verify(raw, sc)["verification"]["revision_hint"] == {"field_tilt_with_lead": ["box_entries"]}
    ok = claim_on(sc, "field_tilt", team("t_nor"), scope="window", window=tuple(w),
                  param_values=("amount", "box_entries", "team_f3_passes"))
    v = verdict(ok, sc)
    assert v.status == "published_with_context" and v.rule_ids == ["field_tilt_with_lead"] and not v.revision_hint


def test_shot_spam_fires_on_nor_in_showcase(data):
    _, sc, _ = data
    v = verdict(claim_on(sc, "xg", team("t_nor")), sc)
    assert "shot_spam" in v.rule_ids and v.status == "blocked"
    assert v.revision_hint == {"shot_spam": ["shots", "xg_per_shot"]}
    v = verdict(claim_on(sc, "xg", team("t_nor"), param_values=("amount", "shots", "xg_per_shot")), sc)
    assert v.rule_ids == ["shot_spam"] and v.status == "published_with_context"


def test_set_piece_inflation_fires_on_corner_specialist(data):
    _, sc, gt = data
    pid = next(k for k, x in gt["planted_players"].items() if x["trap"] == "corner_specialist")
    assert "set_piece_inflation" in verdict(claim_on(sc, "chances_created", player(pid)), sc).rule_ids


def test_wide_forward_passes_fires_on_volume_passer(data):
    _, sc, gt = data
    pid = next(k for k, x in gt["planted_players"].items() if x["trap"] == "volume_passer")
    assert "wide_forward_passes" in verdict(claim_on(sc, "forward_passes", player(pid)), sc).rule_ids


def test_small_sample_xg_fires_on_short_window(data):
    _, sc, _ = data
    c = claim_on(sc, "xg", team("t_aur"), scope="window", window=(0, 900))
    v = verdict(c, sc)
    assert "small_sample_xg" in v.rule_ids and v.context_note == "xg.small_sample"
    # season xG is never "small sample"
    season, _, _ = data
    c2 = build_claim(season, "xg", "season", team("t_aur"), template_key="xg.stat", param_values=("amount",))
    assert "small_sample_xg" not in verdict(c2, season).rule_ids


def test_ppda_alone_fires_without_press_intensity_and_not_with_it(data):
    season, _, _ = data
    c = build_claim(season, "ppda", "season", team("t_cal"), template_key="ppda.stat", param_values=("amount",))
    v = verdict(c, season)
    assert v.rule_ids == ["ppda_alone"] and v.status == "blocked"
    assert v.revision_hint == {"ppda_alone": ["press_intensity"]}
    c2 = build_claim(season, "ppda", "season", team("t_cal"), template_key="ppda.stat",
                     params={"with_press_intensity": True}, param_values=("amount", "press_intensity"))
    assert verdict(c2, season).status == "published"


def test_single_match_fatigue_blocks_on_showcase_but_not_season(data):
    season, sc, _ = data
    c = claim_on(sc, "chances_created", player("NOR_11"), template_key="fatigue.late_drop")
    v = verdict(c, sc)      # NOR_11 is also the corner specialist, so set_piece_inflation fires too
    assert v.status == "blocked" and "single_match_fatigue" in v.rule_ids
    assert v.context_note == "fatigue.single_match_not_supported"
    c2 = build_claim(season, "chances_created", "season", player("NOR_11"), template_key="fatigue.late_drop",
                     param_values=("amount",))
    assert "single_match_fatigue" not in verdict(c2, season).rule_ids


def test_causal_claims_are_always_blocked(data):
    _, sc, _ = data
    c = claim_on(sc, "xg", team("t_aur"), claim_type="causal")
    v = verdict(c, sc)
    assert v.status == "blocked" and "causal_claim" in v.rule_ids
    rc = claim_on(sc, "xg", team("t_nor"), template_key="red_card.caused_loss")
    v = verdict(rc, sc)
    assert v.status == "blocked" and v.rule_ids[0] == "causal_red_card"
    ok = claim_on(sc, "xg", team("t_aur"), template_key="red_card.segment_rates", claim_type="descriptive_change")
    assert "causal_red_card" not in verdict(ok, sc).rule_ids


# ---------- rules do NOT fire on genuine dominance ----------

def _spells(evs, tid):
    out, start, diff = [], 0, 0
    for e in evs:
        if e["event_type"] == "shot" and e["outcome"] == "goal":
            out.append((start, e["clock_sec"], diff))
            start = e["clock_sec"]
            diff += 1 if e["team_id"] == tid else -1
    out.append((start, evs[-1]["clock_sec"], diff))
    return out


def test_field_tilt_rule_silent_on_cal_level_or_ahead(data):
    season, _, _ = data
    checked = 0
    for mid, evs in match_events(season).items():
        if "t_cal" not in (season.matches[mid]["home_team_id"], season.matches[mid]["away_team_id"]):
            continue
        for s, t, diff in _spells(evs, "t_cal"):
            if diff < 0 or t - s < 900:
                continue
            c = build_claim(season, "field_tilt", "window", team("t_cal"), match_id=mid, window=(s, t),
                            template_key="field_tilt.stat", param_values=("amount",))
            if c["value"]["amount"] >= 60:
                checked += 1
                assert "field_tilt_with_lead" not in verdict(c, season).rule_ids, (mid, s, t)
    assert checked >= 3


def test_field_tilt_rule_silent_on_high_territory_with_box_entries(data):
    season, _, _ = data
    checked = 0
    for mid, evs in match_events(season).items():
        m = season.matches[mid]
        for tid in (m["home_team_id"], m["away_team_id"]):
            c = build_claim(season, "field_tilt", "match", team(tid), match_id=mid,
                            template_key="field_tilt.stat", param_values=("amount",))
            sv = c["supporting_values"]
            # above the rule's entry cap (15% before realism v2, now the retuned constant)
            if c["value"]["amount"] >= 60 and sv["box_entry_share"] > 100 * field_tilt_with_lead.MAX_ENTRY_SHARE:
                checked += 1
                assert "field_tilt_with_lead" not in verdict(c, season).rule_ids, (mid, tid)
    assert checked >= 3


def test_quality_rules_silent_on_genuine_creators(data):
    season, _, _ = data
    # CAL's top forward passer plays centrally; CAL's shots are not spam
    top_cal = M.forward_passes_by_player(season.events, "t_cal").value[0][0]
    fp = build_claim(season, "forward_passes", "season", player(top_cal), template_key="fwd.stat", param_values=("amount",))
    assert "wide_forward_passes" not in verdict(fp, season).rule_ids
    xg = build_claim(season, "xg", "season", team("t_cal"), template_key="xg.stat", param_values=("amount",))
    assert "shot_spam" not in verdict(xg, season).rule_ids
    cc = build_claim(season, "chances_created", "season", player(top_cal), template_key="cc.stat", param_values=("amount",))
    assert "set_piece_inflation" not in verdict(cc, season).rule_ids
