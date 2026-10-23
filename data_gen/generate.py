"""Generate the synthetic season and the showcase match.

    python -m data_gen.generate --seed 2026 --out data/generated --showcase-out data/showcase

Deterministic: the same seed always writes identical files.
Tables: teams, players, matches, lineups, events, passes, shots (+ ground_truth.json).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date
from pathlib import Path

from . import calibration, motifs, schedule, traps
from .config import (MOTIF_RATES, MOTIF_SCALE, MOTIF_SIDES, MOTIFS, PLAYER_MOTIFS, SHOWCASE_PLAYER_TRAITS, TEAM_BY_ID,
                     TEAMS)
from .league import EXPECTED_EVIDENCE, EXTRA_PLAYER_TRAITS, full_teams, team_traps
from .simulator import MatchSim, build_players
from .squads import SquadManager, name_pool

SEASON = "2026-27"
SHOWCASE_ID = "m_showcase"
EVENT_COLS = ["event_id", "match_id", "period", "minute", "second", "clock_sec", "team_id", "player_id",
              "opponent_team_id", "event_type", "x_start", "y_start", "x_end", "y_end", "outcome",
              "body_part", "play_pattern", "under_pressure", "possession_id", "sequence_id",
              "sequence_index", "score_home", "score_away", "related_player_id"]
PASS_COLS = ["event_id", "match_id", "passer_id", "recipient_player_id", "pass_distance_m",
             "pass_angle_rad", "pass_type", "pass_difficulty", "ball_speed_kmh", "is_forward",
             "is_progressive", "is_key_pass", "xa"]
SHOT_COLS = ["event_id", "match_id", "team_id", "player_id", "shot_distance_m", "shot_angle_rad",
             "shot_type", "assist_event_id", "is_big_chance", "shot_result", "xg", "shot_speed_kmh"]
TEAM_COLS = ["team_id", "code", "name", "style_seed", "lane_weights", "weak_lane", "att", "dfn",
             "press", "tempo", "directness", "sit_deep", "attacking_output", "counter", "shot_spam", "weak_strength", "formation"]
PLAYER_COLS = ["player_id", "team_id", "name", "shirt", "position", "role", "home_x", "home_y",
               "first_choice", "finishing", "usage", "set_piece_taker", "trap_flag"]
MATCH_COLS = ["match_id", "season", "matchweek", "date", "kickoff", "home_team_id", "away_team_id",
              "home_score", "away_score", "home_xg", "away_xg", "ball_in_play_sec"]
LINEUP_COLS = ["match_id", "team_id", "player_id", "role", "starter", "on_sec", "off_sec", "minutes_played",
               "sent_off"]


def write_csv(path: Path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def make_players(seed: int, overrides: dict | None = None, teams=None):
    """Squads (24 per team). Same seed gives the same names and roles; `overrides` only changes
    trait values. Teams are built in order, so the first five teams get the same players in every
    league. Names come from one pool, so no full name repeats in a league."""
    rng = random.Random(seed)
    names = name_pool(rng)
    return {t.team_id: build_players(rng, t, overrides, names) for t in (teams or TEAMS)}


def simulate(seed: int, match_id: str, home_id: str, away_id: str, players, force_goal=None,
             teams_by_id=None, motif_scale: float = MOTIF_SCALE):
    tb = teams_by_id or TEAM_BY_ID
    sim = MatchSim(random.Random(seed), match_id, tb[home_id], tb[away_id], players, force_goal,
                   motifs=motifs.active((tb[home_id], tb[away_id]), motif_scale), motif_seed=seed)
    sim.run()
    return sim


def match_row(sim: MatchSim, fx: dict):
    return dict(match_id=sim.mid, season=SEASON, matchweek=fx["matchweek"], date=fx["date"], kickoff=fx["kickoff"],
                home_team_id=sim.home_id, away_team_id=sim.away_id,
                home_score=sim.score[sim.home_id], away_score=sim.score[sim.away_id],
                home_xg=round(sim.xg[sim.home_id], 2), away_xg=round(sim.xg[sim.away_id], 2),
                ball_in_play_sec=int(sim.bip))


def showcase_checks(sim: MatchSim, players, reference_completion=None) -> dict:
    ntg_players = {p.trap_flag: p.player_id for p in players["t_ntg"] if p.trap_flag}
    return dict(
        field_tilt_while_leading=traps.field_tilt_trap(sim.events, "t_aur", "t_ntg"),
        shot_spam=traps.shot_spam_trap(sim.events, sim.shots, "t_ntg"),
        volume_passer=traps.volume_passer_trap(sim.events, sim.passes, ntg_players["volume_passer"]),
        corner_specialist=traps.corner_specialist_trap(sim.events, sim.passes, ntg_players["corner_specialist"]),
        one_flank_vs_weak_lane=traps.flank_attack_trap(sim.events, "t_aur", "t_ntg", reference_completion),
    )


SHOWCASE_MIN_MARGIN = 0.10   # every trap threshold must be cleared by at least 10%
# The demo match must also look like a real match, not a freak: approximate upper tails of a
# Premier League match (football knowledge, not a measurement).
SHOWCASE_REALISM = dict(max_team_shots=30, max_goals=6, min_team_passes=250)


def showcase_is_realistic(sim: MatchSim) -> bool:
    shots = {t: 0 for t in sim.teams}
    for s in sim.shots:
        shots[s["team_id"]] += 1
    passes = {t: 0 for t in sim.teams}
    for e in sim.events:
        if e["event_type"] == "pass":
            passes[e["team_id"]] += 1
    r = SHOWCASE_REALISM
    return (max(shots.values()) <= r["max_team_shots"] and sum(sim.score.values()) <= r["max_goals"]
            and min(passes.values()) >= r["min_team_passes"])
# Where the seed search starts, per generator seed. A full search from 0 takes ~2 minutes, so we
# record the first offset that a search from 0 finds; tests/test_data_gen.py (slow) re-runs the
# search from 0 and checks it lands on the same offset. Set to 0 after changing the simulator.
# Keyed by (seed, motif scale): planting changes the matches, so each scale has its own first hit
# (scale 0 keeps the pre-patterns showcase byte for byte).
SHOWCASE_SEARCH_START = {(2026, 0.0): 1383, (2026, 1.0): 6914}


def showcase_reference(seed: int, tables=None, motif_scale: float = MOTIF_SCALE) -> float:
    """The season's completion rate of entries into NTG's weak lane (the dashboard's baseline)."""
    tables = tables or season_tables(*small_season(seed, make_players(seed), motif_scale))
    return traps.lane_entry_completion(tables["events"], TEAM_BY_ID["t_ntg"].weak_lane)


def build_showcase(seed: int, players, max_tries: int = 20000, start: int | None = None, reference_completion=None,
                   motif_scale: float = MOTIF_SCALE):
    """Same simulator as the season, with a scripted early AUR goal. We then search seeds until
    all five traps fire in the one match, each threshold cleared with SHOWCASE_MIN_MARGIN, inside
    the SHOWCASE_REALISM envelope, so the demo match is reproducible, unedited, plausible and not
    balanced on a knife edge."""
    start = SHOWCASE_SEARCH_START.get((seed, float(motif_scale)), 0) if start is None else start
    if reference_completion is None:
        reference_completion = showcase_reference(seed, motif_scale=motif_scale)
    for k in range(start, start + max_tries):
        s = seed * 10_000 + k
        sim = simulate(s, SHOWCASE_ID, "t_aur", "t_ntg", players,
                       force_goal=dict(team_id="t_aur", after_sec=600), motif_scale=motif_scale)
        if not showcase_is_realistic(sim):
            continue
        checks = showcase_checks(sim, players, reference_completion)
        if (all(c and c["passed"] for c in checks.values())
                and min(m["margin"] for m in traps.trap_margins(checks).values()) >= SHOWCASE_MIN_MARGIN):
            return sim, checks, s, k + 1
    raise RuntimeError("no seed produced all five traps; loosen thresholds or tune the simulator")


def season_tables(sims, fixtures) -> dict:
    """The match, lineup, event, pass and shot rows of a list of simulated matches."""
    rows_e, rows_p, rows_s, rows_m, rows_l = [], [], [], [], []
    for sim, fx in zip(sims, fixtures):
        rows_e += sim.events
        rows_p += list(sim.passes.values())
        rows_s += sim.shots
        rows_m.append(match_row(sim, fx))
        rows_l += sim.lineup_rows()
    return dict(matches=rows_m, events=rows_e, passes=rows_p, shots=rows_s, lineups=rows_l)


def play_season(seed: int, fixtures, players, teams_by_id=None, seed_mult: int = 1000, motif_scale: float = MOTIF_SCALE):
    """Simulate the fixtures in date order. A SquadManager carries availability between matches:
    suspensions (a red card, five yellows), injuries and light rotation after a congested week.
    motif_scale multiplies the planted motif propensities (0 = none planted)."""
    tb = teams_by_id or TEAM_BY_ID
    mgr = SquadManager(players, random.Random(seed + 11))
    sims = []
    for i, fx in enumerate(fixtures):
        d = date.fromisoformat(fx["date"])
        lus = {tid: mgr.matchday(tb[tid], d) for tid in (fx["home"], fx["away"])}
        s = seed * seed_mult + i
        sim = MatchSim(random.Random(s), f"m_{i + 1:03d}", tb[fx["home"]], tb[fx["away"]], lus,
                       motifs=motifs.active((tb[fx["home"]], tb[fx["away"]]), motif_scale), motif_seed=s)
        sim.run()
        for tid in (fx["home"], fx["away"]):
            mine = {s.player_id for s in players[tid]}
            mgr.record(tid, d, [c for c in sim.cards if c[0] in mine],
                       [j for j in sim.injured if j[0] in mine], set())
        sims.append(sim)
    return sims


def write_dataset(out: Path, sims, players, fixtures, teams=None, team_cols=TEAM_COLS):
    """Write the tables; returns them (as written) for calibration."""
    tables = season_tables(sims, fixtures)
    rows_e, rows_p, rows_s, rows_m, rows_l = (tables[k] for k in ("events", "passes", "shots", "matches", "lineups"))
    write_csv(out / "teams.csv", team_cols, [
        {**t.__dict__, "lane_weights": json.dumps(t.lane_weights)} for t in (teams or TEAMS)])
    write_csv(out / "players.csv", PLAYER_COLS, [
        dict(player_id=p.player_id, team_id=p.team_id, name=p.name, shirt=p.shirt, position=p.position,
             role=p.role, home_x=p.hx, home_y=p.hy, first_choice=int(p.first_choice),
             finishing=p.finishing, usage=p.usage,
             set_piece_taker=int(p.set_piece_taker), trap_flag=p.trap_flag)
        for ps in players.values() for p in ps])
    write_csv(out / "matches.csv", MATCH_COLS, rows_m)
    write_csv(out / "lineups.csv", LINEUP_COLS, rows_l)
    write_csv(out / "events.csv", EVENT_COLS, rows_e)
    write_csv(out / "passes.csv", PASS_COLS, rows_p)
    write_csv(out / "shots.csv", SHOT_COLS, rows_s)
    return tables


def fixtures_for(team_ids, seed: int, cycles: int = 1) -> list[dict]:
    """Season fixtures in date order (see data_gen/schedule.py)."""
    rounds = schedule.season_rounds(team_ids, random.Random(seed + 7), cycles)
    return schedule.calendar(rounds, random.Random(seed + 8))


def small_season(seed: int, players, motif_scale: float = MOTIF_SCALE):
    """The 5-team season (two double round robins, 40 matches, 16 per team): sims and fixtures."""
    fixtures = fixtures_for([t.team_id for t in TEAMS], seed, cycles=2)
    return play_season(seed, fixtures, players, motif_scale=motif_scale), fixtures


def planted_motifs(sims, teams, players, scale: float) -> dict | None:
    """Ground truth of the planted motifs: propensities (team and player level, after `scale`) and
    the completed instances per match. None when nothing was planted (the file is then unchanged)."""
    team_cfg = {t.code: {k: round(v * scale, 4) for k, v in MOTIFS.get(t.code, {}).items() if v * scale > 0}
                for t in teams}
    team_cfg = {k: v for k, v in team_cfg.items() if v}
    pl = {}
    for (code, role), pm in PLAYER_MOTIFS.items():
        tid = next((t.team_id for t in teams if t.code == code), None)
        p = next((p for p in players.get(tid, []) if p.role == role and p.first_choice), None)
        pm = {k: round(v * scale, 4) for k, v in pm.items() if v * scale > 0}
        if p is not None and pm:
            pl[p.player_id] = dict(team=code, role=role, motifs=pm)
    if not team_cfg and not pl:
        return None
    code = {t.team_id: t.code for t in teams}
    inst = {}
    for sim in sims:
        if sim.motifs is None:
            continue
        rows = {f"{m}|{code[t]}|{pid}": n for (m, t, pid), n in sorted(sim.motifs.log.items())}
        if rows:
            inst[sim.mid] = rows
    return dict(scale=scale, rates=MOTIF_RATES, teams=team_cfg, players=pl,
                sides={f"{c}|{m}": v for (c, m), v in MOTIF_SIDES.items() if c in team_cfg and m in team_cfg[c]},
                instances=inst)


def main(seed: int, out: Path, showcase_out: Path, motif_scale: float = MOTIF_SCALE):
    players = make_players(seed)
    sims, fixtures = small_season(seed, players, motif_scale)
    tables = write_dataset(out, sims, players, fixtures)

    sc_players = make_players(seed, SHOWCASE_PLAYER_TRAITS)
    # the demo's soft side must beat the season's completion rate into that lane, the baseline the
    # dashboard compares the match with
    sc_sim, checks, sc_seed, tries = build_showcase(seed, sc_players,
                                                    reference_completion=showcase_reference(seed, tables),
                                                    motif_scale=motif_scale)
    write_dataset(showcase_out, [sc_sim], sc_players,
                  [dict(matchweek=1, date="2026-08-15", kickoff="17:30", home="t_aur", away="t_ntg")])

    stats = calibration.season_stats(tables)

    gt = dict(
        season=SEASON, generator_seed=seed, n_matches=len(sims),
        expected=calibration.expected(),
        measured=calibration.measured(stats),
        pitch_frame="x 0-100 toward the opponent goal; every event is in the acting team's attacking frame",
        teams={t.code: dict(team_id=t.team_id, style_seed=t.style_seed, lane_weights=t.lane_weights,
                            weak_lane_attacker_pov=t.weak_lane,
                            weak_strength=t.weak_strength if t.weak_lane else None,
                            formation=t.formation) for t in TEAMS},
        planted_players={p.player_id: dict(team=p.team_id, role=p.role, trap=p.trap_flag)
                         for ps in players.values() for p in ps if p.trap_flag},
        showcase=dict(match_id=SHOWCASE_ID, sim_seed=sc_seed, seeds_tried=tries, home="t_aur", away="t_ntg",
                      scripted="AUR scores their first chance of quality after minute 10",
                      player_overrides={f"{c}:{r}": v for (c, r), v in SHOWCASE_PLAYER_TRAITS.items()},
                      score=[sc_sim.score["t_aur"], sc_sim.score["t_ntg"]], traps=checks,
                      trap_margins=traps.trap_margins(checks), min_margin=SHOWCASE_MIN_MARGIN),
    )
    pm = planted_motifs(sims, TEAMS, players, motif_scale)
    if pm:
        gt["planted_motifs"] = pm
        sc = planted_motifs([sc_sim], TEAMS, sc_players, motif_scale)
        gt["showcase"]["motif_instances"] = sc["instances"].get(SHOWCASE_ID, {})
    for d in (out, showcase_out):
        (d / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    return gt


FULL_TEAM_COLS = TEAM_COLS + ["archetype"]


def main_full(seed: int, out: Path, motif_scale: float = MOTIF_SCALE) -> dict:
    """The 20-team league: double round robin (380 matches, 38 per team). The showcase match is
    not touched; it stays the small league's scripted match."""
    teams = full_teams()
    by_id = {t.team_id: t for t in teams}
    players = make_players(seed, EXTRA_PLAYER_TRAITS, teams)
    fixtures = fixtures_for([t.team_id for t in teams], seed)
    sims = play_season(seed, fixtures, players, by_id, seed_mult=10_000, motif_scale=motif_scale)
    tables = write_dataset(out, sims, players, fixtures, teams, FULL_TEAM_COLS)
    stats = calibration.season_stats(tables)
    gt = dict(
        season=SEASON, league="full", generator_seed=seed, n_matches=len(sims), n_teams=len(teams),
        n_events=sum(len(s.events) for s in sims),
        expected=calibration.expected(),
        measured=calibration.measured(stats),
        pitch_frame="x 0-100 toward the opponent goal; every event is in the acting team's attacking frame",
        teams={t.code: dict(team_id=t.team_id, archetype=t.archetype, style_seed=t.style_seed,
                            lane_weights=t.lane_weights, weak_lane_attacker_pov=t.weak_lane,
                            weak_strength=t.weak_strength if t.weak_lane else None,
                            press=t.press, sit_deep=t.sit_deep, shot_spam=t.shot_spam,
                            directness=t.directness, tempo=t.tempo, counter=t.counter) for t in teams},
        team_traps=team_traps(teams),
        planted_players={p.player_id: dict(team=p.team_id, role=p.role, trap=p.trap_flag,
                                           expected_evidence=EXPECTED_EVIDENCE[p.trap_flag])
                         for ps in players.values() for p in ps if p.trap_flag},
        expected_evidence=EXPECTED_EVIDENCE,
    )
    pm = planted_motifs(sims, teams, players, motif_scale)
    if pm:
        gt["planted_motifs"] = pm
    (out / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    return gt


if __name__ == "__main__":
    import time
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--league", choices=["small", "full"], default="small",
                    help="small: the 5-team, 40-match season (+ showcase); full: 20 teams, 380 matches")
    ap.add_argument("--out", type=Path, default=None,
                    help="default data/generated (small) or data/full (full)")
    ap.add_argument("--showcase-out", type=Path, default=Path("data/showcase"))
    ap.add_argument("--motif-scale", type=float, default=MOTIF_SCALE,
                    help="planted motif strength: 1 = the dataset, 0 = none (byte-identity proof), 0.5 = detection limit")
    a = ap.parse_args()
    t0 = time.perf_counter()
    if a.league == "full":
        out = a.out or Path("data/full")
        g = main_full(a.seed, out, a.motif_scale)
        print(f"wrote {g['n_matches']} matches, {g['n_teams']} teams, {g['n_events']} events to {out} "
              f"in {time.perf_counter() - t0:.1f}s")
    else:
        out = a.out or Path("data/generated")
        g = main(a.seed, out, a.showcase_out, a.motif_scale)
        print(f"wrote {g['n_matches']} matches to {out}; showcase seed {g['showcase']['sim_seed']} "
              f"after {g['showcase']['seeds_tried']} tries, score {g['showcase']['score']}")
