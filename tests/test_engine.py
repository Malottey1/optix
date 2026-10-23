"""The engine must rediscover the planted patterns from events alone.

Only these tests read ground_truth.json (and data_gen, to check zone definitions agree); engine
code never does. The season is generated fresh into a temp dir so the tests do not depend on
whatever is in data/generated.
"""
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from data_gen import config as gen_config
from data_gen.generate import main as generate
from engine import metrics as M
from engine import zones
from engine.matchup import lane_matchup, matchup_claim
from engine.profiles import BRACKETS, bracket_shift, team_style_profile
from engine.report import main as report_main
from engine.tables import load

ROOT = Path(__file__).resolve().parent.parent
SEED = 2026


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    root = tmp_path_factory.mktemp("engine_data")
    gt = generate(SEED, root / "season", root / "showcase")
    return root, gt


@pytest.fixture(scope="module")
def ds(generated):
    return load(generated[0] / "season")


@pytest.fixture(scope="module")
def gt(generated):
    return generated[1]


@pytest.fixture(scope="module")
def claim_validator():
    return Draft202012Validator(json.loads((ROOT / "contracts" / "claim.schema.json").read_text()))


def tid(ds, code):
    return ds.team_by_code(code)


# ---------- independence from the generator ----------

def test_engine_code_never_touches_generator_or_ground_truth():
    for path in (ROOT / "engine").rglob("*.py"):
        text = path.read_text()
        assert "data_gen" not in text and "ground_truth" not in text, path


def test_loader_drops_hidden_generator_columns(ds):
    for t in ds.teams.values():
        assert set(t) == {"team_id", "code", "name"}
    for p in ds.players.values():
        assert not {"usage", "finishing", "trap_flag", "set_piece_taker"} & set(p)


def test_zones_match_the_data_dictionary():
    assert zones.LANES == tuple(gen_config.LANES)
    assert zones.FINAL_THIRD_X == gen_config.FINAL_THIRD_X
    assert (zones.BOX_X, zones.BOX_Y) == (gen_config.BOX_X, gen_config.BOX_Y)
    for y10 in range(0, 1001):
        y = y10 / 10
        assert zones.lane_of(y) == gen_config.lane_of(y)
    for x in range(0, 101, 2):
        for y in range(0, 101, 2):
            assert zones.in_box(x, y) == gen_config.in_box(x, y)
    assert zones.lane_of(5) == "left_flank" and zones.flip(10, 5) == (90, 95)


# ---------- metrics: values come with evidence ----------

def test_every_metric_returns_value_and_existing_evidence(ds):
    ev_ids = {e["event_id"] for e in ds.events}
    aur = tid(ds, "AUR")
    results = [
        M.final_third_passes(ds.events, aur), M.final_third_entries(ds.events, aur),
        M.box_entries(ds.events, aur), M.field_tilt(ds.events, aur),
        M.xg_sum(ds.events, ds.shots, aur), M.npxg_sum(ds.events, ds.shots, aur),
        M.shots_by_xg_band(ds.events, ds.shots, aur), M.forward_passes_wide_share(ds.events, aur),
        M.chances_created(ds.events, ds.passes, aur), M.ball_won_height(ds.events, aur),
        M.tempo(ds.events, aur), M.directness(ds.events, aur), M.counter_share(ds.events, aur),
        M.passes_per_sequence(ds.events, aur), M.press_intensity(ds.events, aur),
        M.ppda(ds.events, aur), M.chances_conceded_by_lane(ds.events, aur),
        M.forward_passes_by_player(ds.events, aur),
    ]
    for r in results:
        assert r.value is not None
        assert r.evidence_event_ids and set(r.evidence_event_ids) <= ev_ids
        assert r.sample_size > 0


def test_metric_definitions_hold_on_their_evidence(ds):
    by_id = {e["event_id"]: e for e in ds.events}
    aur = tid(ds, "AUR")
    for i in M.box_entries(ds.events, aur).evidence_event_ids:
        e = by_id[i]
        assert e["team_id"] == aur and e["outcome"] == "success"
        assert zones.in_box(e["x_end"], e["y_end"]) and not zones.in_box(e["x_start"], e["y_start"])
    for i in M.final_third_passes(ds.events, aur).evidence_event_ids:
        assert by_id[i]["x_start"] >= zones.FINAL_THIRD_X
    xg = M.xg_sum(ds.events, ds.shots, aur)
    assert xg.value == pytest.approx(sum(ds.shots[i]["xg"] for i in xg.evidence_event_ids))
    bands = M.shots_by_xg_band(ds.events, ds.shots, aur)
    assert sum(bands.value.values()) == xg.sample_size
    cc = M.chances_created(ds.events, ds.passes, aur)
    assert cc.value == cc.detail["open_play"] + cc.detail["set_piece"]
    assert all(ds.passes[i]["pass_type"] == "corner" or by_id[i]["play_pattern"] == "set_piece"
               for i in cc.detail["set_piece_ids"])


def test_field_tilt_window_and_state_partition(ds):
    aur = tid(ds, "AUR")
    whole = M.field_tilt(ds.events, aur)
    # the clock runs on through stoppage time, so the second window is open-ended
    halves = [M.field_tilt(ds.events, aur, window=w) for w in ((0, 2699), (2700, 10**6))]
    assert sum(h.detail["team_f3_passes"] for h in halves) == whole.detail["team_f3_passes"]
    states = [M.field_tilt(ds.events, aur, state=s) for s in ("leading", "level", "trailing")]
    assert sum(s.sample_size for s in states) == whole.sample_size
    fine = [M.field_tilt(ds.events, aur, state=s) for s in
            ("leading_2plus", "leading_1", "level", "trailing_1", "trailing_2plus")]
    assert sum(s.sample_size for s in fine) == whole.sample_size
    with pytest.raises(ValueError):
        M.field_tilt(ds.events, None, state="level")


def test_profiles_have_league_comparison_and_sample_sizes(ds):
    for code in ("AUR", "NTG", "CAL", "VES", "HAR"):
        for b in BRACKETS:
            p = team_style_profile(ds, tid(ds, code), b)
            for m in p["metrics"].values():
                assert m["n"] > 0 and m["league"] is not None and m["z"] is not None
            for lanes in p["lanes"].values():
                assert set(lanes) == set(zones.LANES)
                assert sum(v["share"] for v in lanes.values()) == pytest.approx(1.0)


# ---------- rediscovering the planted styles (only here is ground truth read) ----------

def test_recovers_aur_left_heavy_attack(ds, gt):
    planted = gt["teams"]["AUR"]["lane_weights"]
    planted_top = zones.LANES[max(range(5), key=lambda i: planted[i])]
    lanes = team_style_profile(ds, tid(ds, "AUR"))["lanes"]["entry_lanes"]
    found_top = max(lanes, key=lambda l: lanes[l]["z"])
    assert found_top == planted_top == "left_flank"
    assert lanes["left_flank"]["share"] + lanes["left_half_space"]["share"] >= 0.5
    assert lanes["left_flank"]["z"] >= 3


def test_recovers_ntg_soft_lane_from_attacker_pov(ds, gt):
    planted = gt["teams"]["NTG"]["weak_lane_attacker_pov"]
    prof = team_style_profile(ds, tid(ds, "NTG"))["lanes"]
    for set_name in ("entry_lanes_conceded", "chance_lanes_conceded"):
        lanes = prof[set_name]
        assert max(lanes, key=lambda l: lanes[l]["z"]) == planted, set_name
    assert prof["entry_lanes_conceded"][planted]["z"] >= 2
    # the mirror lane must NOT light up: that would mean frames got flipped
    assert prof["entry_lanes_conceded"]["right_flank"]["z"] < 0


def test_recovers_aur_behaviour_change_when_leading(ds, gt):
    assert "sitting deep" in gt["teams"]["AUR"]["style_seed"]
    shifts = {code: bracket_shift(ds, tid(ds, code), "leading", "level")
              for code in ("AUR", "NTG", "CAL", "VES", "HAR")}
    aur = shifts["AUR"]
    assert aur["field_tilt"]["delta"] <= -0.1          # cedes territory once ahead
    assert aur["press_intensity"]["delta"] < 0         # stops pressing
    assert aur["passes_per_sequence"]["delta"] < 0     # shorter, more direct possessions
    for metric in ("field_tilt", "press_intensity", "passes_per_sequence"):
        biggest_drop = min(shifts, key=lambda c: shifts[c][metric]["delta"])
        assert biggest_drop == "AUR", metric
    leading = team_style_profile(ds, tid(ds, "AUR"), "leading")["metrics"]
    assert leading["field_tilt"]["z"] < -2 and leading["press_intensity"]["z"] < -2


def test_recovers_cal_as_high_press(ds, gt):
    assert "high press" in gt["teams"]["CAL"]["style_seed"]
    press = {code: team_style_profile(ds, tid(ds, code))["metrics"]["press_intensity"]
             for code in ("AUR", "NTG", "CAL", "VES", "HAR")}
    ranked = sorted(press, key=lambda c: press[c]["value"], reverse=True)
    assert ranked[0] == "CAL"
    assert press["CAL"]["z"] >= 5
    assert press["CAL"]["value"] >= 1.5 * press[ranked[1]]["value"]


# ---------- matchup and claim ----------

def test_top_matchup_is_aur_left_vs_ntg_soft_left(ds, gt):
    m = lane_matchup(ds, tid(ds, "AUR"), tid(ds, "NTG"))
    assert m["top"]["lane"] == gt["teams"]["NTG"]["weak_lane_attacker_pov"] == "left_flank"
    assert m["top"]["attack_z"] > 0 and m["top"]["concede_z"] > 0
    assert m["n_attack"] > 0 and m["n_concede"] > 0
    by_id = {e["event_id"]: e for e in ds.events}
    for i in m["top"]["evidence_event_ids"]:
        e = by_id[i]
        # every evidence event is a final-third entry into the attacker's LEFT flank, made by AUR
        # or conceded by NTG: both sides in the attacker's frame
        assert e["team_id"] == tid(ds, "AUR") or e["opponent_team_id"] == tid(ds, "NTG")
        assert zones.lane_of(e["y_end"]) == "left_flank"
        assert e["x_start"] < zones.FINAL_THIRD_X <= e["x_end"]


def test_matchup_claim_validates_and_matches_the_numbers(ds, claim_validator):
    claim = matchup_claim(ds, tid(ds, "AUR"), tid(ds, "NTG"))
    assert not [e.message for e in claim_validator.iter_errors(claim)]
    assert claim["verification"]["status"] == "pending"
    assert claim["template_key"] == "matchup.weak_flank"
    assert claim["zone"] == {"lane": "left_flank", "third": "attacking"}
    assert claim["params"]["attack_share"] == claim["value"]["amount"]
    assert claim["params"]["league_share"] == claim["value"]["baseline"]
    m = lane_matchup(ds, tid(ds, "AUR"), tid(ds, "NTG"))
    assert claim["value"]["amount"] == round(100 * m["top"]["attack_share"], 1)
    assert claim["value"]["sample_size"] == m["n_attack"]
    assert claim["evidence_event_ids"] == m["top"]["evidence_event_ids"]


def test_report_cli_json_is_a_valid_claim(generated, capsys, claim_validator):
    root, _ = generated
    assert report_main(["--team", "AUR", "--opponent", "NTG", "--data", str(root / "season"), "--json"]) == 0
    claim = json.loads(capsys.readouterr().out)
    assert not list(claim_validator.iter_errors(claim))


def test_report_cli_text(generated, capsys):
    root, _ = generated
    report_main(["--team", "AUR", "--opponent", "NTG", "--data", str(root / "season")])
    out = capsys.readouterr().out
    assert "top mismatch: left_flank" in out
    assert re.search(r"AUR when leading vs level", out)


def test_engine_runs_on_the_showcase_match(generated, claim_validator):
    sc = load(generated[0] / "showcase")
    claim = matchup_claim(sc, sc.team_by_code("AUR"), sc.team_by_code("NTG"), match_id="m_showcase")
    assert claim is not None and not list(claim_validator.iter_errors(claim))
    assert claim["match_id"] == "m_showcase"


def test_matchup_claim_uses_season_scope_and_backed_params(ds):
    from contracts.checks import check_param_numbers
    claim = matchup_claim(ds, tid(ds, "AUR"), tid(ds, "NTG"))
    assert claim["scope"] == "season" and "window" not in claim
    assert check_param_numbers(claim) == []
    v = claim["value"]
    assert v["interval"]["low"] < v["amount"] < v["interval"]["high"]
    assert v["effect_pp"] == pytest.approx(v["amount"] - v["baseline"], abs=0.11)
    # a matchup takes the lower of its two confidences: the attacker's lane share and the
    # defender's completion rate in that lane (both recomputed from the claim's own numbers)
    from engine.metrics import min_confidence, share_confidence
    sv = claim["supporting_values"]
    share_c = share_confidence(round(v["amount"] / 100 * v["sample_size"]), v["sample_size"], v["baseline"] / 100)
    k = round(sv["concede_completion"] / 100 * sv["completion_attempts"])
    comp_c = share_confidence(k, sv["completion_attempts"], sv["league_completion"] / 100)
    assert v["confidence"] == min_confidence(share_c, comp_c)
    assert v["confidence"] in ("medium", "high") and sv["completion_attempts"] < v["sample_size"]
    assert v["baseline_source"]["kind"] == "season" and v["baseline_source"]["n"] > v["sample_size"]


def test_soft_lane_from_completion_rate_on_small_league(ds, gt):
    from engine.profiles import SOFT_LANE_MIN_PP, soft_lane
    nor = soft_lane(ds, tid(ds, "NTG"))
    assert nor is not None and nor["lane"] == gt["teams"]["NTG"]["weak_lane_attacker_pov"]
    assert nor["effect_pp"] >= SOFT_LANE_MIN_PP and nor["interval"][0] > nor["league"]
    # no team without a planted weak lane is flagged
    for code, t in gt["teams"].items():
        if t["weak_lane_attacker_pov"] is None:
            assert soft_lane(ds, t["team_id"]) is None, code


def test_showcase_uses_season_baseline(generated, ds, claim_validator):
    root, _ = generated
    sc = load(root / "showcase", baseline="season", season_dir=root / "season")
    assert sc.baseline is not None and sc.baseline.label == "season"
    claim = matchup_claim(sc, sc.team_by_code("AUR"), sc.team_by_code("NTG"))
    assert not list(claim_validator.iter_errors(claim))
    src = claim["value"]["baseline_source"]
    season_n = sum(M.final_third_entries(ds.events, None).detail["lanes"].values())
    assert src == {"kind": "season", "n": season_n, "dataset": "season"}
    assert claim["scope"] == "match" and claim["match_id"] == "m_showcase" and claim["window"]["from_sec"] == 0
    # the baseline really is the season's, not the match's own
    season_share = lane_matchup(ds, tid(ds, "AUR"), tid(ds, "NTG"))["lanes"][claim["zone"]["lane"]]["league_share"]
    assert claim["value"]["baseline"] == round(100 * season_share, 1)
    selfbase = matchup_claim(load(root / "showcase"), "t_aur", "t_ntg")
    assert selfbase["value"]["baseline_source"]["n"] < src["n"]


def test_profile_and_matchup_run_on_any_league(ds):
    """No hard-coded team ids: every pair in the small league gets a profile and a matchup."""
    for a in ds.teams:
        p = team_style_profile(ds, a)
        assert p["metrics"]["press_intensity"]["interval"] is not None
        for d in ds.teams:
            if a != d:
                m = lane_matchup(ds, a, d)
                assert set(m["lanes"]) == set(zones.LANES)
