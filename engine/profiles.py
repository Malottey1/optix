"""Team style profiles per game-state bracket, each metric compared with the league average.

League average = the same metric pooled over every team in the same bracket of the BASELINE
dataset (a team is part of its own league average). The baseline is the dataset itself unless it
was loaded with baseline="season" (single-match analyses), in which case it is the season.

Each comparison reports the effect (difference from the league: percentage points for shares,
units for means), a 95% interval (Wilson for shares, normal for means), a confidence label and
the sample size. A sampling z-score is still included but only as an internal ranking signal:
it grows with sample size, so it says "unlikely to be noise", not "a big difference".

Brackets: "all" (every minute), "leading", "level", "trailing" (team's own point of view).
"""
from __future__ import annotations

import math

from functools import lru_cache

from . import metrics as M
from .tables import BRACKETS3, Dataset, baseline_of, team_events
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
    ev = team_events(ds, team_id)      # only the team's matches: same result, ~N/2-teams the work
    if name in SCALARS:
        return SCALARS[name][0](ev, team_id, state=st)
    if name == "entry_completion_conceded":
        return M.entry_completion_by_lane(ev, team_id, state=st)
    return LANE_SETS[name](ev, team_id, st)


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
        out[name + "_n"] = total
    rs = [team_metric(ds, tid, "entry_completion_conceded", bracket) for tid in ds.teams]
    att = {l: sum(r.detail["lanes"][l]["attempted"] for r in rs) for l in LANES}
    done = {l: sum(r.detail["lanes"][l]["completed"] for r in rs) for l in LANES}
    out["entry_completion_conceded"] = {l: done[l] / att[l] if att[l] else None for l in LANES}
    out["entry_completion_conceded_n"] = att
    return out


def _compare(value, base, sd, n, kind, own_sd=None):
    """value vs league base: effect, 95% interval, confidence, n (and z for ranking only)."""
    if kind == "share":
        hits = round(value * n) if value is not None else 0
        iv = M.wilson_interval(hits, n)
        conf = M.share_confidence(hits, n, base)
        effect = None if value is None or base is None else 100 * (value - base)
        z = M.z_proportion(value, base, n)
    else:
        iv = M.mean_interval(value, own_sd, n)
        conf = M.interval_confidence(iv, base, n)
        effect = None if value is None or base is None else value - base
        z = M.z_mean(value, base, sd, n)
    return dict(value=value, league=base, effect=effect,
                effect_unit="pp" if kind == "share" else "units", interval=iv, confidence=conf, z=z, n=n)


def _lane_compare(hits, n, base):
    share = hits / n if n else None
    return dict(share=share, league=base, effect_pp=None if share is None or base is None else 100 * (share - base),
                interval=M.wilson_interval(hits, n), confidence=M.share_confidence(hits, n, base),
                z=M.z_proportion(share, base, n), n=n)


def team_style_profile(ds: Dataset, team_id: str, bracket: str = "all") -> dict:
    """Style profile of one team in one game-state bracket.

    Returns {team_id, code, bracket, metrics: {name: {value, league, z, n, unit}},
    lanes: {set_name: {lane: {share, league, z, n}}}}. Lane sets: entry_lanes (where the team gets
    into the final third), entry_lanes_conceded and chance_lanes_conceded (where opponents get in,
    all from the attacker's point of view). n is the metric's own sample size (see each metric).
    """
    bds = baseline_of(ds)
    base = league_baseline(bds, bracket)
    out = dict(team_id=team_id, code=ds.code(team_id), bracket=bracket, metrics={}, lanes={},
               completion={}, baseline=dict(dataset=bds.label, is_self=bds is ds))
    for name, (_, kind, unit) in SCALARS.items():
        r = team_metric(ds, team_id, name, bracket)
        out["metrics"][name] = dict(**_compare(r.value, base[name]["value"], base[name]["sd"],
                                               r.sample_size, kind, r.sd), unit=unit)
    for name in LANE_SETS:
        r = team_metric(ds, team_id, name, bracket)
        out["lanes"][name] = {l: _lane_compare(r.detail["lanes"][l], r.value, base[name][l]) for l in LANES}
    r = team_metric(ds, team_id, "entry_completion_conceded", bracket)
    out["completion"]["entry_completion_conceded"] = {
        l: dict(rate=v["rate"], league=base["entry_completion_conceded"][l],
                attempted=v["attempted"], completed=v["completed"],
                **{k: x for k, x in _lane_compare(v["completed"], v["attempted"],
                                                  base["entry_completion_conceded"][l]).items()
                   if k in ("effect_pp", "interval", "confidence", "z")})
        for l, v in r.detail["lanes"].items()}
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


# Soft-lane rule (see docs/engine.md): a defence is soft in a lane when opponents complete entries
# into it at least SOFT_LANE_MIN_PP above the league rate for that lane AND the lower end of the
# team's 95% Wilson interval is above the league rate AND the lane's lift stands out from the
# team's lift in its other lanes (z >= SOFT_LANE_MIN_Z_OWN). The last gate matters for a side that
# often sits deep: a deep block lets opponents complete entries more easily in every lane, which
# is not a soft lane. At most one lane per team: the largest lift. The z gate is one-sided 5%
# Bonferroni-corrected for the five lanes tested per team (0.05 / 5 -> z 2.33).
SOFT_LANE_MIN_PP = 4.0
SOFT_LANE_MIN_Z_OWN = 2.33


def _z_vs_rest(comp: dict, lane: str) -> float | None:
    """Two-sample z of `lane`'s conceded-completion lift over the league rate for that lane, vs the
    team's pooled lift over the league rate in its other lanes. Lifts, not raw rates: lanes have
    different league baselines (a central entry is harder to complete than one down a flank)."""
    k1, n1, l1 = comp[lane]["completed"], comp[lane]["attempted"], comp[lane]["league"]
    rest = [v for l, v in comp.items() if l != lane and v["attempted"] and v["league"] is not None]
    n2 = sum(v["attempted"] for v in rest)
    if not n1 or not n2 or l1 is None:
        return None
    p1 = k1 / n1
    lift1 = p1 - l1
    lift2 = sum(v["completed"] - v["attempted"] * v["league"] for v in rest) / n2
    var2 = sum(v["attempted"] * (v["completed"] / v["attempted"]) * (1 - v["completed"] / v["attempted"])
               for v in rest) / n2 ** 2
    se = math.sqrt(p1 * (1 - p1) / n1 + var2)
    return (lift1 - lift2) / se if se else None


def soft_lane(ds: Dataset, team_id: str, bracket: str = "all") -> dict | None:
    """The lane (attacker point of view) where `team_id`'s defence concedes entries most easily
    relative to the league, if it passes the soft-lane rule; else None.

    Returns {lane, rate, league, effect_pp, interval, confidence, attempted, evidence_event_ids}.
    Known limits: needs a few hundred attempts per lane (a full season). Effects below ~5 pp are
    not recoverable at that sample size; on a single match this never fires reliably.
    """
    comp = team_style_profile(ds, team_id, bracket)["completion"]["entry_completion_conceded"]
    ok = [l for l, v in comp.items() if v["effect_pp"] is not None and v["interval"] is not None
          and v["effect_pp"] >= SOFT_LANE_MIN_PP and v["interval"][0] > v["league"]
          and (_z_vs_rest(comp, l) or 0.0) >= SOFT_LANE_MIN_Z_OWN]
    if not ok:
        return None
    lane = max(ok, key=lambda l: comp[l]["effect_pp"])
    r = team_metric(ds, team_id, "entry_completion_conceded", bracket)
    return dict(lane=lane, **comp[lane], z_vs_own_lanes=round(_z_vs_rest(comp, lane), 2),
                evidence_event_ids=list(r.detail["lane_attempt_ids"][lane][:12]))
