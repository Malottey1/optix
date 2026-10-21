"""Team style profiles per game-state bracket, each metric compared with the league average.

League average = the same metric pooled over every team in the same bracket (a team is part of
its own league average). z-scores are sampling z-scores against that average, so they grow with
sample size: |z| >= 2 means "unlikely to be noise", not "a big difference". Read the value, the
league value and the sample size together.

Brackets: "all" (every minute), "leading", "level", "trailing" (team's own point of view).
"""
from __future__ import annotations

from functools import lru_cache

from . import metrics as M
from .tables import BRACKETS3, Dataset
from .zones import LANES

BRACKETS = ("all",) + BRACKETS3

# name -> (function, kind, unit). kind "share" uses a proportion z, "mean" a mean z.
SCALARS = {
    "field_tilt": (M.field_tilt, "share", "ratio"),
    "tempo_sec_per_pass": (M.tempo, "mean", "seconds"),
    "directness": (M.directness, "share", "ratio"),
    "counter_share": (M.counter_share, "share", "ratio"),
    "ball_won_height": (M.ball_won_height, "mean", "x 0-100"),
    "passes_per_sequence": (M.passes_per_sequence, "mean", "passes"),
    "press_intensity": (M.press_intensity, "share", "ratio"),
}
LANE_SETS = {
    "entry_lanes": lambda ev, tid, st: M.final_third_entries(ev, tid, state=st),
    "entry_lanes_conceded": lambda ev, tid, st: M.final_third_entries(ev, tid, state=st, conceded=True),
    "chance_lanes_conceded": lambda ev, tid, st: M.chances_conceded_by_lane(ev, tid, state=st),
}


def _state(bracket: str):
    if bracket not in BRACKETS:
        raise ValueError(f"bracket must be one of {BRACKETS}")
    return None if bracket == "all" else bracket


def _lane_shares(r: M.MetricResult) -> dict:
    n = r.value
    return {l: (c / n if n else None) for l, c in r.detail["lanes"].items()}


@lru_cache(maxsize=None)
def team_metric(ds: Dataset, team_id: str, name: str, bracket: str) -> M.MetricResult:
    st = _state(bracket)
    if name in SCALARS:
        return SCALARS[name][0](ds.events, team_id, state=st)
    return LANE_SETS[name](ds.events, team_id, st)


@lru_cache(maxsize=None)
def league_baseline(ds: Dataset, bracket: str) -> dict:
    """League value per scalar metric (pooled over teams) and league lane shares, for one bracket.

    Shares pool hits over trials, so league field tilt is 0.5 over all minutes but below 0.5 for
    leading teams (they cede territory). Lane shares pool every team's entries (entries made ==
    entries conceded league-wide).
    """
    out = {}
    for name in SCALARS:
        rs = [team_metric(ds, tid, name, bracket) for tid in ds.teams]
        if SCALARS[name][1] == "mean":
            n = sum(r.sample_size for r in rs)
            m = sum(r.value * r.sample_size for r in rs if r.value is not None) / n
            # pooled per-observation variance: within-team plus between-team parts
            var = sum((r.sample_size - 1) * r.sd ** 2 + r.sample_size * (r.value - m) ** 2
                      for r in rs if r.value is not None) / max(1, n - 1)
            out[name] = dict(value=m, sd=var ** 0.5)
        else:
            n = sum(r.sample_size for r in rs)
            hits = sum(r.value * r.sample_size for r in rs if r.value is not None)
            out[name] = dict(value=hits / n if n else None, sd=None)
    for name in LANE_SETS:
        rs = [team_metric(ds, tid, name, bracket) for tid in ds.teams]
        total = sum(r.value for r in rs)
        out[name] = {l: sum(r.detail["lanes"][l] for r in rs) / total if total else None for l in LANES}
    return out


def _compare(value, base, sd, n, kind):
    z = M.z_proportion(value, base, n) if kind == "share" else M.z_mean(value, base, sd, n)
    return dict(value=value, league=base, z=z, n=n)


def team_style_profile(ds: Dataset, team_id: str, bracket: str = "all") -> dict:
    """Style profile of one team in one game-state bracket.

    Returns {team_id, code, bracket, metrics: {name: {value, league, z, n, unit}},
    lanes: {set_name: {lane: {share, league, z, n}}}}. Lane sets: entry_lanes (where the team gets
    into the final third), entry_lanes_conceded and chance_lanes_conceded (where opponents get in,
    all from the attacker's point of view). n is the metric's own sample size (see each metric).
    """
    base = league_baseline(ds, bracket)
    out = dict(team_id=team_id, code=ds.code(team_id), bracket=bracket, metrics={}, lanes={})
    for name, (_, kind, unit) in SCALARS.items():
        r = team_metric(ds, team_id, name, bracket)
        out["metrics"][name] = dict(**_compare(r.value, base[name]["value"], base[name]["sd"],
                                               r.sample_size, kind), unit=unit)
    for name in LANE_SETS:
        r = team_metric(ds, team_id, name, bracket)
        shares = _lane_shares(r)
        out["lanes"][name] = {
            l: dict(share=shares[l], league=base[name][l],
                    z=M.z_proportion(shares[l], base[name][l], r.value), n=r.value)
            for l in LANES}
    return out


def bracket_shift(ds: Dataset, team_id: str, to_bracket: str = "leading", from_bracket: str = "level") -> dict:
    """How the team's scalar metrics change between two brackets of its own, next to the same
    change for the league. Descriptive only: a shift is not a cause.

    Returns {name: {from, to, delta, league_delta, n_from, n_to}}.
    """
    a, b = team_style_profile(ds, team_id, from_bracket), team_style_profile(ds, team_id, to_bracket)
    la, lb = league_baseline(ds, from_bracket), league_baseline(ds, to_bracket)
    out = {}
    for name in SCALARS:
        va, vb = a["metrics"][name]["value"], b["metrics"][name]["value"]
        out[name] = dict(**{"from": va, "to": vb},
                         delta=None if va is None or vb is None else vb - va,
                         league_delta=lb[name]["value"] - la[name]["value"],
                         n_from=a["metrics"][name]["n"], n_to=b["metrics"][name]["n"])
    return out
