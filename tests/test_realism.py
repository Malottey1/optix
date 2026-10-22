"""Realism of the generated data, beyond the calibration ranges: fixtures, lineups and substitutions,
ball and player continuity, referential integrity, xG calibration, goal counts and timing, league
correlations, names and determinism.

The default suite runs on the 5-team small league (seed 2026); the slow suite on the 20-team league.
Ranges come from data_gen/calibration.py (public sources or wide ranges marked approximate).
"""
import math
from collections import Counter, defaultdict

import pytest

from data_gen import calibration
from data_gen.generate import EXTRA_PLAYER_TRAITS, fixtures_for, make_players, play_season, season_tables, small_season
from data_gen.league import full_teams
from data_gen.schedule import MAX_RUN

ONBALL = ("pass", "carry", "shot", "dribble")
# events with no ball location of their own (paperwork, or a marker at someone else's spot)
NO_BALL = ("substitution", "card", "half_end", "injury", "pressure", "possession_change", "foul", "offside")
RESTARTS = ("throw_in", "goal_kick", "set_piece", "kickoff", "free_kick", "corner", "penalty")
OFF_PITCH_OK = ("substitution", "card", "half_end")
REACH_M, SPEED_M_S = 6.0, 8.0                    # the simulator's teleport guard (data_gen/simulator.py)
BALL_SLACK_M = 6.0                               # a keeper stepping out to release, a first touch


def _f(v):
    return None if v in (None, "") else float(v)


def _league(tables, players):
    tables = dict(tables)
    tables["players"] = [p for ps in players.values() for p in ps]
    return tables


@pytest.fixture(scope="module")
def small():
    players = make_players(2026)
    return _league(season_tables(*small_season(2026, players)), players)


@pytest.fixture(scope="module")
def full():
    teams = full_teams()
    by_id = {t.team_id: t for t in teams}
    players = make_players(2026, EXTRA_PLAYER_TRAITS, teams)
    fixtures = fixtures_for([t.team_id for t in teams], 2026)
    out = _league(season_tables(play_season(2026, fixtures, players, by_id, seed_mult=10_000), fixtures), players)
    out["teams"] = teams
    return out


def _home(t):
    return {m["match_id"]: m["home_team_id"] for m in t["matches"]}


def _abs(e, home, x, y):
    """Event coordinates (attacking frame of the acting team) in the home team's frame."""
    return (x, y) if e["team_id"] == home[e["match_id"]] else (100 - x, 100 - y)


def _metres(ax, ay, bx, by):
    return math.hypot((ax - bx) * 1.05, (ay - by) * 0.68)


def _stints(t):
    """(match, player) -> (on_sec, off_sec) for every player who took the field."""
    return {(r["match_id"], r["player_id"]): (_f(r["on_sec"]), _f(r["off_sec"]))
            for r in t["lineups"] if _f(r["on_sec"]) is not None}


# ---------- every range ----------

def test_every_calibration_target_in_range(small):
    assert calibration.NOT_YET_MODELLED == set()
    failed = calibration.failing(calibration.season_stats(small))
    assert not failed, sorted(failed)


# ---------- fixtures ----------

def _check_fixtures(t, cycles):
    ms = t["matches"]
    teams = {m["home_team_id"] for m in ms} | {m["away_team_id"] for m in ms}
    pairs = Counter((m["home_team_id"], m["away_team_id"]) for m in ms)
    assert set(pairs) == {(a, b) for a in teams for b in teams if a != b}
    assert set(pairs.values()) == {cycles}                         # each side hosts each other side `cycles` times
    dates = Counter((m["date"], tm) for m in ms for tm in (m["home_team_id"], m["away_team_id"]))
    assert set(dates.values()) == {1}                              # nobody plays twice on one date
    for tm in teams:
        seq = ["H" if m["home_team_id"] == tm else "A"
               for m in sorted(ms, key=lambda m: (m["date"], m["kickoff"])) if tm in (m["home_team_id"], m["away_team_id"])]
        run = best = 1
        for a, b in zip(seq, seq[1:]):
            run = run + 1 if a == b else 1
            best = max(best, run)
        assert best <= MAX_RUN, (tm, "".join(seq))
        assert abs(seq.count("H") - seq.count("A")) == 0


def test_fixture_structure_small(small):
    _check_fixtures(small, cycles=2)


# ---------- lineups and substitutions ----------

def _check_lineups(t):
    squad = {p.player_id: p.team_id for p in t["players"]}
    by_tm = defaultdict(list)
    for r in t["lineups"]:
        by_tm[(r["match_id"], r["team_id"])].append(r)
    assert len(by_tm) == 2 * len(t["matches"])
    for key, rows in by_tm.items():
        ids = [r["player_id"] for r in rows]
        assert len(ids) == len(set(ids)), key
        assert all(squad[p] == key[1] for p in ids), key
        starters = [r for r in rows if int(r["starter"]) == 1]
        subs_on = [r for r in rows if int(r["starter"]) == 0 and _f(r["on_sec"]) is not None]
        assert len(starters) == 11, key
        assert sum(1 for r in starters if r["role"] == "goalkeeper") == 1, key
        assert len(subs_on) <= 5, key
        for r in rows:
            on, off = _f(r["on_sec"]), _f(r["off_sec"])
            if on is None:
                assert _f(r["minutes_played"]) == 0
                continue
            assert 0 <= on <= off
            assert _f(r["minutes_played"]) == pytest.approx((off - on) / 60, abs=0.051), (key, r["player_id"])


def test_lineups_are_consistent(small):
    _check_lineups(small)


def _check_on_pitch(t):
    stints = _stints(t)
    for e in t["events"]:
        if not e["player_id"] or e["event_type"] in OFF_PITCH_OK:
            continue
        on, off = stints[(e["match_id"], e["player_id"])]
        assert on <= e["clock_sec"] <= off, (e["event_id"], e["event_type"], e["player_id"], on, off)


def test_no_events_by_players_not_on_the_pitch(small):
    _check_on_pitch(small)


def _on_pitch_counts(t):
    """(match, team) -> sorted list of (clock, players on the pitch just after it) at every change."""
    changes = defaultdict(Counter)
    for r in t["lineups"]:
        on, off = _f(r["on_sec"]), _f(r["off_sec"])
        if on is None:
            continue
        changes[(r["match_id"], r["team_id"])][on] += 1
        changes[(r["match_id"], r["team_id"])][off] -= 1
    out = {}
    end = defaultdict(float)
    for r in t["lineups"]:
        end[r["match_id"]] = max(end[r["match_id"]], _f(r["off_sec"]) or 0)
    for key, ch in changes.items():
        n, seq = 0, []
        for c in sorted(ch):
            n += ch[c]
            if c < end[key[0]]:
                seq.append((c, n))
        out[key] = seq
    return out


def test_eleven_at_kickoff_never_more_and_ten_after_a_red(small):
    counts = _on_pitch_counts(small)
    for key, seq in counts.items():
        assert seq[0] == (0, 11), key
        assert all(7 <= n <= 11 for _, n in seq), key
    reds = [r for r in small["lineups"] if int(r["sent_off"]) == 1]
    assert reds, "no red card in the season: the 11 v 10 check is vacuous"
    for r in reds:
        after = [n for c, n in counts[(r["match_id"], r["team_id"])] if c >= _f(r["off_sec"])]
        assert after and max(after) <= 10, r


def test_substitution_events_match_lineups(small):
    stints = _stints(small)
    subs = [e for e in small["events"] if e["event_type"] == "substitution"]
    assert subs
    for e in subs:
        off_on, off_off = stints[(e["match_id"], e["player_id"])]
        on_on, _ = stints[(e["match_id"], e["related_player_id"])]
        assert off_off == e["clock_sec"] and on_on == e["clock_sec"], e["event_id"]
    tactical = [e for e in subs if e["outcome"] == "tactical"]
    assert sum(1 for e in tactical if 55 <= int(e["minute"]) <= 85) >= 0.6 * len(tactical)


def test_minutes_add_up(small):
    counts = _on_pitch_counts(small)
    end = defaultdict(float)
    for r in small["lineups"]:
        end[r["match_id"]] = max(end[r["match_id"]], _f(r["off_sec"]) or 0)
    mins = defaultdict(float)
    for r in small["lineups"]:
        mins[(r["match_id"], r["team_id"])] += _f(r["minutes_played"])
    for key, seq in counts.items():
        pts = seq + [(end[key[0]], None)]
        expected = sum(n * (pts[i + 1][0] - c) for i, (c, n) in enumerate(seq)) / 60
        assert mins[key] == pytest.approx(expected, abs=0.6), key
        assert mins[key] <= 11 * end[key[0]] / 60 + 0.6, key


def test_sent_off_player_misses_the_next_match(small):
    order = {m["match_id"]: (m["date"], m["kickoff"]) for m in small["matches"]}
    played = defaultdict(list)                                  # team -> its matches in date order
    for m in sorted(small["matches"], key=lambda m: order[m["match_id"]]):
        for tm in (m["home_team_id"], m["away_team_id"]):
            played[tm].append(m["match_id"])
    in_squad = {(r["match_id"], r["player_id"]) for r in small["lineups"]}
    for r in small["lineups"]:
        if int(r["sent_off"]) != 1:
            continue
        ms = played[r["team_id"]]
        i = ms.index(r["match_id"])
        if i + 1 < len(ms):
            assert (ms[i + 1], r["player_id"]) not in in_squad, r


# ---------- ball and player continuity ----------

def _check_players_never_teleport(t):
    home = _home(t)
    last = {}
    for e in t["events"]:
        if not e["player_id"] or e["event_type"] in ("substitution", "card") or e["x_start"] is None:
            continue
        x, y = _abs(e, home, e["x_start"], e["y_start"])
        k = (e["match_id"], e["player_id"])
        if k in last and last[k][3] == e["period"]:
            t0, x0, y0, _ = last[k]
            reach = REACH_M + SPEED_M_S * (e["clock_sec"] - t0 + 1)   # + 1 s: the clock is stored in whole seconds
            assert _metres(x, y, x0, y0) <= reach + 0.5, (e["event_id"], e["player_id"])
        fx, fy = ((e["x_end"], e["y_end"]) if e["event_type"] == "carry" and e["x_end"] is not None
                  else (e["x_start"], e["y_start"]))
        last[k] = (e["clock_sec"], *_abs(e, home, fx, fy), e["period"])


def test_players_never_teleport(small):
    _check_players_never_teleport(small)


def _check_ball_continuity(t):
    """Every open-play on-ball action starts where the ball last was (the end of the previous
    located event, or its spot); restarts place the ball and are exempt."""
    home = _home(t)
    ball, n = None, 0
    for e in t["events"]:
        if e["event_type"] in NO_BALL or e["x_start"] is None:
            continue
        sx, sy = _abs(e, home, e["x_start"], e["y_start"])
        if (e["event_type"] in ONBALL and e["play_pattern"] not in RESTARTS and ball
                and ball[0] == (e["match_id"], e["period"])):
            n += 1
            assert _metres(sx, sy, ball[1], ball[2]) <= BALL_SLACK_M, e["event_id"]
        bx, by = _abs(e, home, e["x_end"], e["y_end"]) if e["x_end"] is not None else (sx, sy)
        ball = ((e["match_id"], e["period"]), bx, by)
    assert n > 1000


def test_ball_continuity(small):
    _check_ball_continuity(small)


def test_restarts_happen_at_legal_spots(small):
    for e in small["events"]:
        if e["event_type"] != "pass" or e["sequence_index"] not in (0, None):
            continue
        pt = e["play_pattern"]
        if pt == "throw_in":
            assert e["y_start"] <= 1.0 or e["y_start"] >= 99.0, e["event_id"]      # on the touchline
        elif pt == "kickoff":
            assert (e["x_start"], e["y_start"]) == (50.0, 50.0), e["event_id"]


def _check_referential_integrity(t):
    evs = {e["event_id"]: e for e in t["events"]}
    players = {p.player_id for p in t["players"]}
    mids = {m["match_id"] for m in t["matches"]}
    assert len(evs) == len(t["events"])
    for p in t["passes"]:
        assert evs[p["event_id"]]["event_type"] == "pass"
    for s in t["shots"]:
        assert evs[s["event_id"]]["event_type"] == "shot"
        if s.get("assist_event_id"):
            assert evs[s["assist_event_id"]]["event_type"] == "pass"
    for e in t["events"]:
        assert e["match_id"] in mids
        assert not e["player_id"] or e["player_id"] in players
        assert not e["related_player_id"] or e["related_player_id"] in players
    for r in t["lineups"]:
        assert r["match_id"] in mids and r["player_id"] in players


def test_referential_integrity(small):
    _check_referential_integrity(small)


# ---------- names and determinism ----------

def test_no_duplicate_full_names(small):
    names = [p.name for p in small["players"]]
    assert len(names) == len(set(names))


def test_generation_is_deterministic(small):
    players = make_players(2026)
    again = season_tables(*small_season(2026, players))
    for k in ("matches", "events", "passes", "shots", "lineups"):
        assert again[k] == small[k], k


# ---------- full league (slow) ----------

@pytest.mark.slow
def test_full_league_structure_and_consistency(full):
    _check_fixtures(full, cycles=1)
    _check_lineups(full)
    _check_on_pitch(full)
    _check_players_never_teleport(full)
    _check_ball_continuity(full)
    _check_referential_integrity(full)
    names = [p.name for p in full["players"]]
    assert len(names) == len(set(names))


@pytest.mark.slow
def test_full_league_every_target_in_range(full):
    failed = calibration.failing(calibration.season_stats(full))
    assert not failed, sorted(failed)


XG_BINS = ((0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 1.01))


@pytest.mark.slow
def test_xg_is_calibrated_by_bin(full):
    """Goals in each xG bin are within 3 binomial SDs of the xG the bin's shots add up to."""
    for lo, hi in XG_BINS:
        s = [x for x in full["shots"] if lo <= x["xg"] < hi]
        assert len(s) >= 100, (lo, hi)
        xg = sum(x["xg"] for x in s)
        goals = sum(1 for x in s if x["shot_result"] == "goal")
        sd = math.sqrt(sum(x["xg"] * (1 - x["xg"]) for x in s))
        assert abs(goals - xg) <= 3 * sd + 1, (lo, hi, goals, round(xg, 1))


@pytest.mark.slow
def test_team_goals_are_close_to_poisson(full):
    g = [int(m[k]) for m in full["matches"] for k in ("home_score", "away_score")]
    mean = sum(g) / len(g)
    var = sum((x - mean) ** 2 for x in g) / (len(g) - 1)
    assert 0.95 <= var / mean <= 1.3, round(var / mean, 3)


@pytest.mark.slow
def test_goals_rise_late_in_each_half(full):
    goals = [e for e in full["events"] if e["event_type"] == "shot" and e["outcome"] == "goal"]
    for period, early, late in (("1", (0, 15), (30, 200)), ("2", (45, 60), (75, 200))):
        mins = [int(e["minute"]) for e in goals if str(e["period"]) == period]
        n_early = sum(1 for m in mins if early[0] <= m < early[1])
        n_late = sum(1 for m in mins if late[0] <= m < late[1])
        assert n_late > n_early, (period, n_early, n_late)


@pytest.mark.slow
def test_league_correlation_signs(full):
    st = calibration.season_stats(full)
    assert st["corr_possession_shots"] > 0
    assert st["corr_possession_pass_accuracy"] > 0
    assert st["corr_ppda_possession"] < 0
    press = {t.team_id: t.press for t in full["teams"]}
    ppda = st["_ppda_by_team"]
    ts = sorted(ppda)
    assert calibration.pearson([press[x] for x in ts], [ppda[x] for x in ts]) < 0   # pressing sides allow fewer passes
