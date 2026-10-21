"""The generator must (a) produce clean, deterministic tables and (b) really plant every trap.

These tests double as the future contract for the engine: whatever it computes must recover the
same signals recorded in ground_truth.json.
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from data_gen.config import FINAL_THIRD_X, TEAMS, in_box, lane_of
from data_gen.generate import main

SEED = 2026


def read(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("gen")
    gt = main(SEED, root / "season", root / "showcase")
    return root, gt


@pytest.fixture(scope="module")
def season(data):
    root, _ = data
    d = root / "season"
    return dict(events=read(d / "events.csv"), passes=read(d / "passes.csv"),
                shots=read(d / "shots.csv"), matches=read(d / "matches.csv"),
                players=read(d / "players.csv"))


def test_deterministic(tmp_path):
    main(SEED, tmp_path / "a", tmp_path / "sa")
    main(SEED, tmp_path / "b", tmp_path / "sb")
    for name in ("events.csv", "passes.csv", "shots.csv", "matches.csv", "ground_truth.json"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name


def test_shape(season):
    assert len(season["matches"]) == 40
    per_team = Counter()
    for m in season["matches"]:
        per_team[m["home_team_id"]] += 1
        per_team[m["away_team_id"]] += 1
    assert set(per_team.values()) == {16}
    assert len(season["players"]) == 55


def test_events_are_clean(season):
    ev = season["events"]
    ids = [e["event_id"] for e in ev]
    assert len(ids) == len(set(ids))
    by_match = defaultdict(list)
    for e in ev:
        by_match[e["match_id"]].append(e)
        for k in ("x_start", "y_start"):
            assert 0 <= float(e[k]) <= 100
        if e["x_end"] != "":
            assert 0 <= float(e["x_end"]) <= 100 and 0 <= float(e["y_end"]) <= 100
    for evs in by_match.values():
        clocks = [int(e["clock_sec"]) for e in evs]
        assert clocks == sorted(clocks)
        assert max(clocks) <= 5500
    kinds = {e["event_type"] for e in ev}
    # the challenge brief names possession changes and pressure events explicitly
    assert {"pass", "shot", "tackle", "interception", "possession_change", "pressure"} <= kinds


def test_pass_and_shot_tables_link_to_events(season):
    ev = {e["event_id"]: e for e in season["events"]}
    for p in season["passes"]:
        assert ev[p["event_id"]]["event_type"] == "pass"
        assert 0 <= float(p["pass_difficulty"]) <= 1
        assert float(p["ball_speed_kmh"]) > 0
    assert len(season["passes"]) == sum(1 for e in ev.values() if e["event_type"] == "pass")
    for s in season["shots"]:
        assert ev[s["event_id"]]["event_type"] == "shot"
        assert 0 < float(s["xg"]) < 1
        assert float(s["shot_speed_kmh"]) > 0
    for s in season["shots"]:
        if s["assist_event_id"]:
            assert ev[s["assist_event_id"]]["event_type"] == "pass"


def test_scores_match_goal_events(season):
    goals = Counter((e["match_id"], e["team_id"]) for e in season["events"]
                    if e["event_type"] == "shot" and e["outcome"] == "goal")
    for m in season["matches"]:
        assert goals[(m["match_id"], m["home_team_id"])] == int(m["home_score"])
        assert goals[(m["match_id"], m["away_team_id"])] == int(m["away_score"])


def test_season_is_football_realistic(season):
    n = len(season["matches"])
    goals = sum(int(m["home_score"]) + int(m["away_score"]) for m in season["matches"]) / n
    shots = len(season["shots"]) / n
    corners = sum(1 for p in season["passes"] if p["pass_type"] == "corner") / n
    xg_per_shot = sum(float(s["xg"]) for s in season["shots"]) / len(season["shots"])
    assert 1.8 <= goals <= 3.6
    assert 18 <= shots <= 30
    assert 7 <= corners <= 15
    assert 0.07 <= xg_per_shot <= 0.14


def test_style_seeds_are_recoverable_season_wide(season):
    """Each team's planted style must be visible in plain event aggregates."""
    ev = season["events"]
    entries = defaultdict(Counter)
    for e in ev:
        if (e["event_type"] == "pass" and e["outcome"] == "success"
                and float(e["x_start"]) < FINAL_THIRD_X <= float(e["x_end"])):
            entries[e["team_id"]][lane_of(float(e["y_end"]))] += 1

    def share(team, lanes):
        c = entries[team]
        return sum(c[l] for l in lanes) / sum(c.values())

    assert share("t_aur", ["left_flank", "left_half_space"]) >= 0.55      # left-heavy
    assert share("t_cal", ["center"]) >= 0.30                              # central
    assert share("t_ves", ["left_flank", "right_flank"]) >= 0.50           # both wings

    # NOR is soft where attackers come down THEIR left (attacker point of view)
    conceded = Counter()
    for e in ev:
        if (e["event_type"] == "pass" and e["outcome"] == "success"
                and float(e["x_start"]) < FINAL_THIRD_X <= float(e["x_end"])
                and e["opponent_team_id"] == "t_nor"):
            conceded[lane_of(float(e["y_end"]))] += 1
    league = Counter()
    for e in ev:
        if (e["event_type"] == "pass" and e["outcome"] == "success"
                and float(e["x_start"]) < FINAL_THIRD_X <= float(e["x_end"])
                and e["opponent_team_id"] != "t_nor"):
            league[lane_of(float(e["y_end"]))] += 1
    nor_left = conceded["left_flank"] / sum(conceded.values())
    lg_left = league["left_flank"] / sum(league.values())
    assert nor_left > lg_left


def test_volume_passer_is_a_league_leader_who_goes_wide(season):
    ev = {e["event_id"]: e for e in season["events"]}
    fwd, wide = Counter(), Counter()
    for p in season["passes"]:
        e = ev[p["event_id"]]
        if p["is_forward"] == "1" and e["outcome"] == "success":
            fwd[p["passer_id"]] += 1
            if lane_of(float(e["y_end"])) in ("left_flank", "right_flank"):
                wide[p["passer_id"]] += 1
    pid = next(p["player_id"] for p in season["players"] if p["trap_flag"] == "volume_passer")
    assert fwd.most_common(1)[0][0] == pid
    others = [wide[k] / v for k, v in fwd.items() if k != pid]
    assert wide[pid] / fwd[pid] >= 0.8
    assert sum(others) / len(others) < 0.5


def test_corner_specialist_creates_from_dead_balls(season):
    pid = next(p["player_id"] for p in season["players"] if p["trap_flag"] == "corner_specialist")
    kp = [p for p in season["passes"] if p["passer_id"] == pid and p["is_key_pass"] == "1"]
    corners = sum(1 for p in kp if p["pass_type"] == "corner")
    assert corners >= 0.5 * len(kp)
    assert all(p["pass_type"] == "corner" for p in season["passes"]
               if p["passer_id"] == pid and p["pass_type"] == "corner")


def test_leading_team_sits_deep_across_the_season(season):
    """Field tilt is skewed toward the trailing team once a team leads (AUR protects leads)."""
    ev = season["events"]
    matches = {m["match_id"]: m for m in season["matches"]}
    chase_f3, lead_f3 = 0, 0
    for e in ev:
        if e["event_type"] != "pass" or e["outcome"] != "success" or float(e["x_start"]) < FINAL_THIRD_X:
            continue
        m = matches[e["match_id"]]
        if "t_aur" not in (m["home_team_id"], m["away_team_id"]) or int(e["clock_sec"]) < 600:
            continue
        diff = int(e["score_home"]) - int(e["score_away"])
        aur_diff = diff if m["home_team_id"] == "t_aur" else -diff
        if aur_diff >= 1:
            if e["team_id"] == "t_aur":
                lead_f3 += 1
            else:
                chase_f3 += 1
    assert chase_f3 > 1.3 * lead_f3


def test_showcase_contains_every_trap(data):
    root, gt = data
    sc = gt["showcase"]
    assert all(t["passed"] for t in sc["traps"].values())
    assert set(sc["traps"]) == {"field_tilt_while_leading", "shot_spam", "volume_passer",
                                "corner_specialist", "one_flank_vs_weak_lane"}
    tilt = sc["traps"]["field_tilt_while_leading"]
    assert tilt["chaser_field_tilt"] >= 0.68
    assert tilt["chaser_box_entries"] <= 0.15 * tilt["chaser_f3_passes"]
    # evidence ids must exist in the showcase events
    ev_ids = {e["event_id"] for e in read(root / "showcase" / "events.csv")}
    for t in sc["traps"].values():
        assert t["evidence_event_ids"] and set(t["evidence_event_ids"]) <= ev_ids


def test_showcase_and_ground_truth_have_no_real_names(data):
    root, _ = data
    text = (root / "showcase" / "teams.csv").read_text() + (root / "showcase" / "ground_truth.json").read_text()
    for real in ("Arsenal", "Chelsea", "Liverpool", "Manchester", "Tottenham", "Premier League"):
        assert real not in text
