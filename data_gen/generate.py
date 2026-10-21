"""Generate the synthetic season and the showcase match.

    python -m data_gen.generate --seed 2026 --out data/generated --showcase-out data/showcase

Deterministic: the same seed always writes identical files.
Tables: teams, players, matches, events, passes, shots (+ ground_truth.json).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from itertools import permutations
from pathlib import Path

from . import traps
from . import calibration
from .config import SHOWCASE_PLAYER_TRAITS, TEAMS, TEAM_BY_ID
from .simulator import MatchSim, build_players

SEASON = "2026-27"
SHOWCASE_ID = "m_showcase"
EVENT_COLS = ["event_id", "match_id", "period", "minute", "second", "clock_sec", "team_id", "player_id",
              "opponent_team_id", "event_type", "x_start", "y_start", "x_end", "y_end", "outcome",
              "body_part", "play_pattern", "under_pressure", "possession_id", "sequence_id",
              "sequence_index", "score_home", "score_away"]
PASS_COLS = ["event_id", "match_id", "passer_id", "recipient_player_id", "pass_distance_m",
             "pass_angle_rad", "pass_type", "pass_difficulty", "ball_speed_kmh", "is_forward",
             "is_progressive", "is_key_pass", "xa"]
SHOT_COLS = ["event_id", "match_id", "team_id", "player_id", "shot_distance_m", "shot_angle_rad",
             "shot_type", "assist_event_id", "is_big_chance", "shot_result", "xg", "shot_speed_kmh"]
TEAM_COLS = ["team_id", "code", "name", "style_seed", "lane_weights", "weak_lane", "att", "dfn",
             "press", "tempo", "directness", "sit_deep", "attacking_output", "counter", "shot_spam"]
PLAYER_COLS = ["player_id", "team_id", "name", "shirt", "position", "role", "home_x", "home_y",
               "finishing", "usage", "set_piece_taker", "trap_flag"]
MATCH_COLS = ["match_id", "season", "matchweek", "date", "home_team_id", "away_team_id",
              "home_score", "away_score", "home_xg", "away_xg"]


def write_csv(path: Path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def make_players(seed: int, overrides: dict | None = None):
    """Same seed gives the same names and roles; `overrides` only changes trait values."""
    rng = random.Random(seed)
    return {t.team_id: build_players(rng, t, overrides) for t in TEAMS}


def simulate(seed: int, match_id: str, home_id: str, away_id: str, players, force_goal=None):
    sim = MatchSim(random.Random(seed), match_id, TEAM_BY_ID[home_id], TEAM_BY_ID[away_id],
                   players, force_goal)
    sim.run()
    return sim


def match_row(sim: MatchSim, week: int, d: date):
    return dict(match_id=sim.mid, season=SEASON, matchweek=week, date=d.isoformat(),
                home_team_id=sim.home_id, away_team_id=sim.away_id,
                home_score=sim.score[sim.home_id], away_score=sim.score[sim.away_id],
                home_xg=round(sim.xg[sim.home_id], 2), away_xg=round(sim.xg[sim.away_id], 2))


def showcase_checks(sim: MatchSim, players) -> dict:
    nor_players = {p.trap_flag: p.player_id for p in players["t_nor"] if p.trap_flag}
    return dict(
        field_tilt_while_leading=traps.field_tilt_trap(sim.events, "t_aur", "t_nor"),
        shot_spam=traps.shot_spam_trap(sim.events, sim.shots, "t_nor"),
        volume_passer=traps.volume_passer_trap(sim.events, sim.passes, nor_players["volume_passer"]),
        corner_specialist=traps.corner_specialist_trap(sim.events, sim.passes, nor_players["corner_specialist"]),
        one_flank_vs_weak_lane=traps.flank_attack_trap(sim.events, "t_aur", "t_nor"),
    )


SHOWCASE_MIN_MARGIN = 0.10   # every trap threshold must be cleared by at least 10%
# Where the seed search starts, per generator seed. A full search from 0 takes ~2 minutes, so we
# record the first offset that a search from 0 finds; tests/test_data_gen.py (slow) re-runs the
# search from 0 and checks it lands on the same offset. Set to 0 after changing the simulator.
SHOWCASE_SEARCH_START = {2026: 4547}


def build_showcase(seed: int, players, max_tries: int = 6000, start: int | None = None):
    """Same simulator as the season, with a scripted early AUR goal. We then search seeds until
    all five traps fire in the one match, each threshold cleared with SHOWCASE_MIN_MARGIN, so the
    demo match is reproducible, unedited and not balanced on a knife edge."""
    start = SHOWCASE_SEARCH_START.get(seed, 0) if start is None else start
    for k in range(start, start + max_tries):
        s = seed * 10_000 + k
        sim = simulate(s, SHOWCASE_ID, "t_aur", "t_nor", players,
                       force_goal=dict(team_id="t_aur", after_sec=600))
        checks = showcase_checks(sim, players)
        if (all(c and c["passed"] for c in checks.values())
                and min(m["margin"] for m in traps.trap_margins(checks).values()) >= SHOWCASE_MIN_MARGIN):
            return sim, checks, s, k + 1
    raise RuntimeError("no seed produced all five traps; loosen thresholds or tune the simulator")


def write_dataset(out: Path, sims, players, weeks):
    rows_e, rows_p, rows_s, rows_m = [], [], [], []
    start = date(2026, 8, 15)
    for sim, wk in zip(sims, weeks):
        rows_e += sim.events
        rows_p += list(sim.passes.values())
        rows_s += sim.shots
        rows_m.append(match_row(sim, wk, start + timedelta(days=7 * (wk - 1))))
    write_csv(out / "teams.csv", TEAM_COLS, [
        {**t.__dict__, "lane_weights": json.dumps(t.lane_weights)} for t in TEAMS])
    write_csv(out / "players.csv", PLAYER_COLS, [
        dict(player_id=p.player_id, team_id=p.team_id, name=p.name, shirt=p.shirt, position=p.position,
             role=p.role, home_x=p.hx, home_y=p.hy, finishing=p.finishing, usage=p.usage,
             set_piece_taker=int(p.set_piece_taker), trap_flag=p.trap_flag)
        for ps in players.values() for p in ps])
    write_csv(out / "matches.csv", MATCH_COLS, rows_m)
    write_csv(out / "events.csv", EVENT_COLS, rows_e)
    write_csv(out / "passes.csv", PASS_COLS, rows_p)
    write_csv(out / "shots.csv", SHOT_COLS, rows_s)


def main(seed: int, out: Path, showcase_out: Path):
    players = make_players(seed)
    sims, weeks = [], []
    # 5 teams: one home-and-away round is 20 matches; two rounds = 40 (16 per team).
    pairs = []
    for rnd in range(2):
        block = list(permutations([t.team_id for t in TEAMS], 2))
        random.Random(seed + rnd).shuffle(block)
        pairs += block
    for i, (h, a) in enumerate(pairs):
        sims.append(simulate(seed * 1000 + i, f"m_{i + 1:03d}", h, a, players))
        weeks.append(i // 2 + 1)
    write_dataset(out, sims, players, weeks)

    sc_players = make_players(seed, SHOWCASE_PLAYER_TRAITS)
    sc_sim, checks, sc_seed, tries = build_showcase(seed, sc_players)
    write_dataset(showcase_out, [sc_sim], sc_players, [1])

    stats = calibration.season_stats(
        [dict(home_score=s.score[s.home_id], away_score=s.score[s.away_id]) for s in sims],
        [x for s in sims for x in s.shots], [p for s in sims for p in s.passes.values()])

    gt = dict(
        season=SEASON, generator_seed=seed, n_matches=len(sims),
        expected={k: dict(target=t["target"], tolerance=[t["lo"], t["hi"]], unit=t["unit"],
                          definition=t["definition"]) for k, t in calibration.TARGETS.items()},
        measured={k: round(v, 3) for k, v in stats.items()},
        pitch_frame="x 0-100 toward the opponent goal; every event is in the acting team's attacking frame",
        teams={t.code: dict(team_id=t.team_id, style_seed=t.style_seed, lane_weights=t.lane_weights,
                            weak_lane_attacker_pov=t.weak_lane) for t in TEAMS},
        planted_players={p.player_id: dict(team=p.team_id, role=p.role, trap=p.trap_flag)
                         for ps in players.values() for p in ps if p.trap_flag},
        showcase=dict(match_id=SHOWCASE_ID, sim_seed=sc_seed, seeds_tried=tries, home="t_aur", away="t_nor",
                      scripted="AUR scores their first chance of quality after minute 10",
                      player_overrides={f"{c}:{r}": v for (c, r), v in SHOWCASE_PLAYER_TRAITS.items()},
                      score=[sc_sim.score["t_aur"], sc_sim.score["t_nor"]], traps=checks,
                      trap_margins=traps.trap_margins(checks), min_margin=SHOWCASE_MIN_MARGIN),
    )
    for d in (out, showcase_out):
        (d / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    return gt


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=Path("data/generated"))
    ap.add_argument("--showcase-out", type=Path, default=Path("data/showcase"))
    a = ap.parse_args()
    g = main(a.seed, a.out, a.showcase_out)
    print(f"wrote {g['n_matches']} matches to {a.out}; showcase seed {g['showcase']['sim_seed']} "
          f"after {g['showcase']['seeds_tried']} tries, score {g['showcase']['score']}")
