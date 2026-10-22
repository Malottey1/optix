"""The generator must (a) produce clean, deterministic tables and (b) really plant every trap.

These tests double as the future contract for the engine: whatever it computes must recover the
same signals recorded in ground_truth.json.
"""
import csv
import dataclasses
import json
import random
from collections import Counter, defaultdict
from itertools import permutations
from pathlib import Path

import pytest

from data_gen import calibration, traps
from data_gen.config import FINAL_THIRD_X, TEAM_BY_ID, TEAMS, in_box, lane_of
from data_gen.generate import main, make_players, simulate
from data_gen.simulator import MatchSim, build_players

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
    # squads of 24 (an XI, a bench and cover); no full name repeats
    assert len(season["players"]) == 5 * 24
    assert Counter(p["team_id"] for p in season["players"]) == {t.team_id: 24 for t in TEAMS}
    assert len({p["name"] for p in season["players"]}) == len(season["players"])


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
        # 90 minutes plus stoppage time (at most about 20 minutes over both halves)
        assert 5400 < max(clocks) <= 5400 + 20 * 60
        assert [e["period"] for e in evs if e["event_type"] == "half_end"] == ["1", "2"]
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


def test_volume_passer_is_a_top_forward_passer_who_goes_wide(season):
    ev = {e["event_id"]: e for e in season["events"]}
    fwd, wide = Counter(), Counter()
    for p in season["passes"]:
        e = ev[p["event_id"]]
        if p["is_forward"] == "1" and e["outcome"] == "success":
            fwd[p["passer_id"]] += 1
            if lane_of(float(e["y_end"])) in ("left_flank", "right_flank"):
                wide[p["passer_id"]] += 1
    pid = next(p["player_id"] for p in season["players"] if p["trap_flag"] == "volume_passer")
    ranked = fwd.most_common()
    rank = [k for k, _ in ranked].index(pid) + 1
    assert rank <= 3
    # realistic, not obvious: near the top of the league, not a runaway leader
    best_other = next(v for k, v in ranked if k != pid)
    assert fwd[pid] < 1.25 * best_other
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


# ---------- calibration ----------

def season_rows(season):
    return calibration.season_stats(season)


def test_season_meets_calibration_targets(season):
    """Every applicable target is met, apart from the ones the generator does not model yet
    (calibration.NOT_YET_MODELLED, emptied stage by stage; the full league checks that set exactly)."""
    failed = calibration.failing(season_rows(season))
    assert failed <= calibration.NOT_YET_MODELLED, sorted(failed - calibration.NOT_YET_MODELLED)


def test_ground_truth_records_expected_targets(data):
    root, gt = data
    assert gt["expected"] == calibration.expected()
    for k, t in calibration.TARGETS.items():
        assert gt["expected"][k]["tolerance"] == [t["lo"], t["hi"]] and t["lo"] < t["hi"]
        assert gt["expected"][k]["source"]
    on_disk = json.loads((root / "season" / "ground_truth.json").read_text())
    assert on_disk["expected"] == gt["expected"]
    assert on_disk["measured"] == pytest.approx(calibration.measured(season_rows_from_disk(root / "season")), abs=1e-3)


def season_rows_from_disk(d):
    return calibration.season_stats({k: read(d / f"{k}.csv") for k in ("matches", "events", "passes", "shots")})


@pytest.mark.slow
def test_calibration_is_not_a_lucky_seed():
    """Five other seeds pooled (200 matches) meet the same targets as seed 2026, so the tuning is not
    fitted to one seed."""
    from data_gen.generate import season_tables, small_season
    pooled = {k: [] for k in ("matches", "events", "passes", "shots")}
    for seed in range(1, 6):
        t = season_tables(*small_season(seed, make_players(seed)))
        for k in pooled:
            for r in t[k]:                    # keep ids unique across seeds
                for col in ("match_id", "event_id", "assist_event_id"):
                    if r.get(col):
                        r[col] = f"s{seed}_{r[col]}"
            pooled[k] += t[k]
    failed = calibration.failing(calibration.season_stats(pooled))
    assert failed <= calibration.NOT_YET_MODELLED, sorted(failed - calibration.NOT_YET_MODELLED)


# ---------- attacking output is independent of the defensive block ----------

def test_attacking_output_drives_goals_independently_of_sit_deep():
    """Two clones with identical strength (att, dfn) and identical sit_deep, differing only in
    attacking_output, must score clearly different numbers of goals against the same opponent."""
    base = TEAM_BY_ID["t_ves"]
    hi = dataclasses.replace(base, team_id="t_xhi", code="XHI", attacking_output=1.4)
    lo = dataclasses.replace(base, team_id="t_xlo", code="XLO", attacking_output=0.7)
    opp = TEAM_BY_ID["t_har"]
    rng = random.Random(7)
    players = {t.team_id: build_players(rng, t) for t in (hi, lo, opp)}
    goals = Counter()
    n = 100                 # 30 a side was underpowered: the true ratio is about 1.8, 30 games gave 1.4
    for spec in (hi, lo):
        for i in range(n):
            home, away = (spec, opp) if i % 2 == 0 else (opp, spec)
            sim = MatchSim(random.Random(1000 + i), f"m_x{i}", home, away, players)
            sim.run()
            goals[spec.team_id] += sim.score[spec.team_id]
    gpm_hi, gpm_lo = goals["t_xhi"] / n, goals["t_xlo"] / n
    assert hi.att == lo.att and hi.dfn == lo.dfn and hi.sit_deep == lo.sit_deep
    assert gpm_hi >= 1.5 * gpm_lo and gpm_hi - gpm_lo >= 0.5, (gpm_hi, gpm_lo)


# ---------- field-tilt detector: false-positive control ----------

def _spells(events, team_id):
    """(start, end, goal difference for team_id) for each spell between goals."""
    out, start, diff = [], 0, 0
    for e in events:
        if e["event_type"] == "shot" and e["outcome"] == "goal":
            out.append((start, int(e["clock_sec"]), diff))
            start = int(e["clock_sec"])
            diff += 1 if e["team_id"] == team_id else -1
    out.append((start, int(events[-1]["clock_sec"]), diff))
    return out


def _typed(events):
    num = ("clock_sec", "x_start", "y_start", "x_end", "y_end")
    return [{**e, **{k: (float(e[k]) if e[k] != "" else None) for k in num}} for e in events]


def test_field_tilt_does_not_fire_on_cal_dominance(season):
    """CAL is a high press team that is genuinely dominant. Its high final-third-share spells while
    level or ahead (no deep block to chase) clear the tilt and volume gates but must not fire,
    because CAL keeps getting into the box. Realistic final-third volumes (about one completed
    final-third pass a minute) mean a 20-minute spell rarely reaches the detector's 100-pass
    volume gate, so the control lowers that gate to 40 to exercise the box-entry gate on its own."""
    by_match = defaultdict(list)
    for e in season["events"]:
        by_match[e["match_id"]].append(e)
    high = []
    for evs in by_match.values():
        if "t_cal" not in {evs[0]["team_id"], evs[0]["opponent_team_id"]}:
            continue
        evs = _typed(evs)
        for s, t, diff in _spells(evs, "t_cal"):
            if diff < 0 or t - s < 1200:
                continue
            r = traps.field_tilt_spell(evs, (s, t), "t_cal", min_f3=40)
            if r["chaser_field_tilt"] >= 0.68 and r["chaser_f3_passes"] >= 40:
                high.append(r)
    assert len(high) >= 2, "control is vacuous: CAL never had a high-tilt spell"
    for r in high:
        assert not r["passed"], r
        assert r["chaser_box_entries"] > 0.15 * r["chaser_f3_passes"]


def _synthetic_spell(n_f3=120, n_entries=5, n_opp=30):
    """Hand-built events: the chaser plays n_f3 final-third passes, n_entries of them into the box."""
    ev, k = [], 0
    for i in range(n_f3):
        into_box = i < n_entries
        ev.append(dict(event_id=f"e{k}", event_type="pass", outcome="success", team_id="t_a",
                       clock_sec=10 + i, x_start=75.0, y_start=10.0,
                       x_end=90.0 if into_box else 78.0, y_end=50.0 if into_box else 12.0))
        k += 1
    for i in range(n_opp):
        ev.append(dict(event_id=f"e{k}", event_type="pass", outcome="success", team_id="t_b",
                       clock_sec=10 + i, x_start=70.0, y_start=50.0, x_end=72.0, y_end=50.0))
        k += 1
    return ev


def test_field_tilt_fires_only_when_box_entries_are_low():
    low = traps.field_tilt_spell(_synthetic_spell(n_entries=5), (0, 5400), "t_a")
    assert low["chaser_field_tilt"] >= 0.68 and low["chaser_f3_passes"] >= 100
    assert low["passed"]
    # same tilt and volume; only the share of passes entering the box changes
    high = traps.field_tilt_spell(_synthetic_spell(n_entries=30), (0, 5400), "t_a")
    assert high["chaser_field_tilt"] == low["chaser_field_tilt"]
    assert high["chaser_f3_passes"] == low["chaser_f3_passes"]
    assert not high["passed"]


def test_field_tilt_firings_in_the_season_all_have_low_box_entries(season):
    """Across every lead spell in the season: fired -> few box entries; high tilt and volume but
    not fired -> many box entries. The box-entry gate is what decides."""
    by_match = defaultdict(list)
    for e in season["events"]:
        by_match[e["match_id"]].append(e)
    fired = 0
    for evs in by_match.values():
        evs = _typed(evs)
        a, b = evs[0]["team_id"], evs[0]["opponent_team_id"]
        for leader, chaser in ((a, b), (b, a)):
            r = traps.field_tilt_trap(evs, leader, chaser)
            if r and r["passed"]:
                fired += 1
                assert r["chaser_box_entries"] <= 0.15 * r["chaser_f3_passes"]
            elif r and r["chaser_field_tilt"] >= 0.68 and r["chaser_f3_passes"] >= traps.FIELD_TILT_MIN_F3:
                assert r["chaser_box_entries"] > 0.15 * r["chaser_f3_passes"]
    assert fired >= 1, "the trap should also occur naturally outside the showcase"


def test_showcase_keeps_the_strong_volume_passer(data):
    root, gt = data
    vp = gt["showcase"]["traps"]["volume_passer"]
    assert vp["passed"] and vp["rank_in_match"] == 1
    sc_usage = {p["player_id"]: float(p["usage"]) for p in read(root / "showcase" / "players.csv")}
    season_usage = {p["player_id"]: float(p["usage"]) for p in read(root / "season" / "players.csv")}
    pid = next(k for k, v in gt["planted_players"].items() if v["trap"] == "volume_passer")
    assert sc_usage[pid] > season_usage[pid]
    assert {k: v for k, v in sc_usage.items() if k != pid} == {k: v for k, v in season_usage.items() if k != pid}


def test_showcase_traps_clear_thresholds_with_margin(data):
    _, gt = data
    margins = traps.trap_margins(gt["showcase"]["traps"])
    assert margins == gt["showcase"]["trap_margins"]
    low = {k: m for k, m in margins.items() if m["margin"] < 0.10}
    assert not low, low


@pytest.mark.slow
def test_showcase_search_hint_matches_a_search_from_zero():
    """SHOWCASE_SEARCH_START only skips work: a search from 0 must find the same first seed."""
    from data_gen.generate import SHOWCASE_SEARCH_START, build_showcase
    from data_gen.config import SHOWCASE_PLAYER_TRAITS
    players = make_players(SEED, SHOWCASE_PLAYER_TRAITS)
    _, _, s_hint, _ = build_showcase(SEED, players)
    _, _, s_zero, _ = build_showcase(SEED, players, start=0)
    assert s_hint == s_zero == SEED * 10_000 + SHOWCASE_SEARCH_START[SEED]
