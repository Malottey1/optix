"""Match-flow metrics: xA split, territorial stress, shot clusters, rhythm, momentum, milestones.

Same conventions as metrics.py: pure functions over event rows (chronological within a match),
each returning a MetricResult with value, evidence event IDs and sample size, and a docstring
with definition, inputs and known limits.
"""
from __future__ import annotations

import math
from collections import defaultdict

from .metrics import MetricResult, _acting
from .threat import value_at

ON_BALL = ("pass", "shot")


def xa_split(events, passes, team_id=None, player_id=None, window=None, state=None) -> MetricResult:
    """Expected assists (xG of the shot each key pass set up), open play vs set piece.

    Definition: set piece = pass_type "corner" or play_pattern "set_piece"; xa comes from the
    passes table (the assisted shot's xG).
    Inputs: events; passes table; team_id and/or player_id; optional window and game state.
    Value: total xA. detail: open_play_xa, set_piece_xa, open_play_n, set_piece_n and their IDs.
    Known limits: only the final pass gets credit; a set-piece taker's xA says little about his
    open-play creativity (rule set_piece_inflation).
    """
    op, sp = [], []
    for e in _acting(events, team_id, window, state, "pass"):
        if player_id is not None and e["player_id"] != player_id:
            continue
        p = passes[e["event_id"]]
        if not p["is_key_pass"]:
            continue
        (sp if p["pass_type"] == "corner" or e["play_pattern"] == "set_piece" else op).append((e["event_id"], p["xa"]))
    op_xa, sp_xa = sum(x for _, x in op), sum(x for _, x in sp)
    return MetricResult(op_xa + sp_xa, tuple(i for i, _ in op + sp), len(op) + len(sp),
                        detail=dict(open_play_xa=op_xa, set_piece_xa=sp_xa, open_play_n=len(op),
                                    set_piece_n=len(sp), open_play_ids=tuple(i for i, _ in op),
                                    set_piece_ids=tuple(i for i, _ in sp)))


def territorial_stress(match_events, team_id, min_x: float = 50.0, top: int = 3) -> MetricResult:
    """Longest spells of one team keeping the ball in the opponent's half.

    Definition: a spell is a maximal run of consecutive on-ball events (passes, shots) by team_id
    that all start at x >= min_x (its attacking half), with no on-ball event by the opponent in
    between. Pressure events do not break a spell. Spell length = clock of last event - clock of
    first event, seconds.
    Inputs: one match's events in order; team_id; min_x; how many spells to keep.
    Value: longest spell in seconds. detail["spells"]: the top spells, each {start_sec, end_sec,
    seconds, n_events, event_ids}. Evidence: the longest spell's events.
    Known limits: possession inside the half is not pressure on goal; a team circulating around a
    deep block produces long spells (pair with box entries).
    """
    spells, cur = [], []
    for e in match_events:
        if e["event_type"] not in ON_BALL:
            continue
        if e["team_id"] == team_id and e["x_start"] >= min_x:
            cur.append(e)
            continue
        if cur:
            spells.append(cur)
        cur = []
    if cur:
        spells.append(cur)
    rows = sorted(({"start_sec": s[0]["clock_sec"], "end_sec": s[-1]["clock_sec"],
                    "seconds": s[-1]["clock_sec"] - s[0]["clock_sec"], "n_events": len(s),
                    "event_ids": [e["event_id"] for e in s]} for s in spells),
                  key=lambda r: (-r["seconds"], r["start_sec"]))[:top]
    best = rows[0] if rows else None
    return MetricResult(best["seconds"] if best else 0, tuple(best["event_ids"]) if best else (),
                        len(spells), detail=dict(spells=rows))


def shot_clusters(match_events, shots, team_id, gap_sec: int = 120) -> MetricResult:
    """Bursts of shots: consecutive shots by the team no more than gap_sec apart form a cluster.

    Inputs: one match's events; shots table; team_id; gap_sec.
    Value: shot_cluster_score = shots in the largest cluster. detail["clusters"]: clusters with at
    least 2 shots, each {start_sec, end_sec, shots, xg, event_ids}, largest first.
    Evidence: the largest cluster's shots.
    Known limits: a cluster after a corner (rebounds) and a sustained spell of pressure look the
    same here; read the clusters' xG, not only their size.
    """
    sh = [e for e in match_events if e["event_type"] == "shot" and e["team_id"] == team_id]
    groups, cur = [], []
    for e in sh:
        if cur and e["clock_sec"] - cur[-1]["clock_sec"] > gap_sec:
            groups.append(cur)
            cur = []
        cur.append(e)
    if cur:
        groups.append(cur)
    rows = sorted(({"start_sec": g[0]["clock_sec"], "end_sec": g[-1]["clock_sec"], "shots": len(g),
                    "xg": round(sum(shots[e["event_id"]]["xg"] for e in g), 4),
                    "event_ids": [e["event_id"] for e in g]} for g in groups if len(g) >= 2),
                  key=lambda r: (-r["shots"], -r["xg"], r["start_sec"]))
    best = rows[0] if rows else None
    return MetricResult(best["shots"] if best else (1 if sh else 0),
                        tuple(best["event_ids"]) if best else tuple(e["event_id"] for e in sh[:1]),
                        len(sh), detail=dict(clusters=rows))


def rhythm(match_events, end_minute: int | None = None, length: int = 15) -> MetricResult:
    """Control-vs-chaos rhythm, one value per minute for the last `length` minutes.

    Definition per minute m: possession_changes = possession_change events with minute == m;
    tempo_var = variance of the gaps (seconds) between consecutive passes in that minute (same
    sequence); rhythm_index = possession_changes per minute (higher = more chaotic).
    Inputs: one match's events; end_minute (default: last minute with an event); length.
    Value: list of `length` rhythm_index values, oldest first (a series ready to draw).
    detail: per-minute possession_changes and tempo_var lists, minutes. Evidence: the
    possession_change events in the window.
    Known limits: whole-second clock; added time is folded into the minute it is logged in.
    """
    last = max(e["minute"] for e in match_events) if end_minute is None else end_minute
    minutes = list(range(last - length + 1, last + 1))
    changes = defaultdict(list)
    gaps = defaultdict(list)
    prev = {}
    for e in match_events:
        if e["minute"] > last:
            break
        if e["event_type"] == "possession_change":
            changes[e["minute"]].append(e["event_id"])
        elif e["event_type"] == "pass":
            key = (e["sequence_id"], e["team_id"])
            if key in prev:
                gaps[e["minute"]].append(e["clock_sec"] - prev[key])
            prev[key] = e["clock_sec"]

    def var(xs):
        if len(xs) < 2:
            return 0.0
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)

    series = [float(len(changes[m])) for m in minutes]
    ids = tuple(i for m in minutes for i in changes[m])
    return MetricResult(series, ids, len(ids),
                        detail=dict(minutes=minutes, possession_changes=series,
                                    tempo_var=[round(var(gaps[m]), 3) for m in minutes]))


def momentum(match_events, shots, grid, home_id: str, away_id: str, half_life_sec: float = 300.0,
             step_sec: int = 60) -> MetricResult:
    """Rolling momentum from threat and shot quality, one value per `step_sec`.

    Definition: each team's pressure P(t) = exponentially decayed sum (half-life half_life_sec) of
    xT added by its completed passes (positive part only) plus the xG of its shots. Momentum at t
    = 100 * (P_home - P_away) / (P_home + P_away), in [-100, 100]; 0 when both are 0.
    Inputs: one match's events; shots table; an xT grid (season); home and away team ids.
    Value: list of (clock_sec, momentum). detail: per-step home and away pressure. Evidence:
    shots and threat-adding passes, in order.
    Known limits: a descriptive swing indicator, not a forecast; it reacts to volume of threat,
    so many low-quality shots still move it (pair with xG per shot).
    """
    decay = math.log(2) / half_life_sec
    contrib = []
    for e in match_events:
        if e["event_type"] == "shot":
            contrib.append((e["clock_sec"], e["team_id"], shots[e["event_id"]]["xg"], e["event_id"]))
        elif e["event_type"] == "pass" and e["outcome"] == "success":
            d = value_at(grid, e["x_end"], e["y_end"]) - value_at(grid, e["x_start"], e["y_start"])
            if d > 0:
                contrib.append((e["clock_sec"], e["team_id"], d, e["event_id"]))
    end = max((e["clock_sec"] for e in match_events), default=0)
    out, ph, pa = [], [], []
    k = 0
    h = a = 0.0
    last_t = 0.0
    for t in range(0, end + step_sec, step_sec):
        while k < len(contrib) and contrib[k][0] <= t:
            ct, team, v, _ = contrib[k]
            f = math.exp(-decay * (ct - last_t))
            h, a, last_t = h * f, a * f, ct
            if team == home_id:
                h += v
            elif team == away_id:
                a += v
            k += 1
        f = math.exp(-decay * (t - last_t))
        hh, aa = h * f, a * f
        ph.append(hh)
        pa.append(aa)
        out.append((t, 0.0 if hh + aa == 0 else 100 * (hh - aa) / (hh + aa)))
    return MetricResult(out, tuple(c[3] for c in contrib), len(contrib),
                        detail=dict(home_pressure=ph, away_pressure=pa))


def milestones(events, pass_steps=(25, 50, 75, 100)) -> MetricResult:
    """Within-dataset player milestones (never career or real-world records).

    Definition: first_goal = a player's first goal in this dataset (by match order, then clock);
    pass_count = a player reaches N completed passes within one match, for N in pass_steps.
    Inputs: events (any number of matches, in file order).
    Value: number of milestones. detail["milestones"]: list of {kind, player_id, team_id,
    match_id, clock_sec, count, event_id}. Evidence: the milestone events.
    Known limits: "first in the dataset" depends on the dataset's start; it is not a career first.
    """
    out, scored = [], set()
    passes = defaultdict(int)
    for e in events:
        if e["event_type"] == "shot" and e["outcome"] == "goal" and e["player_id"] not in scored:
            scored.add(e["player_id"])
            out.append(dict(kind="first_goal", player_id=e["player_id"], team_id=e["team_id"],
                            match_id=e["match_id"], clock_sec=e["clock_sec"], count=1, event_id=e["event_id"]))
        elif e["event_type"] == "pass" and e["outcome"] == "success":
            key = (e["match_id"], e["player_id"])
            passes[key] += 1
            if passes[key] in pass_steps:
                out.append(dict(kind="pass_count", player_id=e["player_id"], team_id=e["team_id"],
                                match_id=e["match_id"], clock_sec=e["clock_sec"], count=passes[key],
                                event_id=e["event_id"]))
    return MetricResult(len(out), tuple(m["event_id"] for m in out), len(out), detail=dict(milestones=out))
