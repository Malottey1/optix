"""P17 Direct transition spike (family pat_direct_transition). The mirror of P6 seen from the side
that wins the ball; it does not read field tilt.

Definition: the team wins the ball (its own possession_change) in its own half (x < own_half_x in
its frame) and takes a shot within counter_sec seconds, with no other possession change in
between; only the first shot after each regain counts. A finding needs >= min_shots such shots and
a rate per own-half regain >= min_rate_vs_league x the league rate.
Anchors per instance: the regain, the shot.
Numbers: transition shots, their xG, own-half regains, transition shots per 100 regains and the
league rate, the team's shots and the share of them that came this way (%).
Known limits: the feed has no positions off the ball, so it cannot say how many players broke or
were left behind; it counts what was recorded within the time limit.
"""
from __future__ import annotations

from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league

FAMILY = "pat_direct_transition"
STRIDE = 2


def transition_shots(evs, team_id, c):
    """(regains in own half, [(regain, shot)])."""
    out, regains = [], []
    idx = {e["event_id"]: k for k, e in enumerate(evs)}
    for g in evs:
        if g["event_type"] != "possession_change" or g["team_id"] != team_id or g["x_start"] >= c["own_half_x"]:
            continue
        regains.append(g)
        k = idx[g["event_id"]] + 1
        while k < len(evs) and evs[k]["clock_sec"] <= g["clock_sec"] + c["counter_sec"]:
            e = evs[k]
            if e["event_type"] == "possession_change":
                break
            if e["event_type"] == "shot" and e["team_id"] == team_id:
                out.append((g, e))
                break
            k += 1
    return regains, out


def league_rate(base: Dataset, c=None) -> float:
    c = c or cfg(FAMILY)
    hits = total = 0
    for mid, evs in match_events(base).items():
        m = base.matches[mid]
        for tid in (m["home_team_id"], m["away_team_id"]):
            rg, pairs = transition_shots(evs, tid, c)
            hits += len(pairs)
            total += len(rg)
    return hits / total if total else 0.0


def _values(ds, pairs, n_regains, team_shots, lg):
    k = len(pairs)
    return dict(amount=k, xg=sum(ds.shots[s["event_id"]]["xg"] for _, s in pairs), regains=n_regains,
                per_100=100 * k / n_regains if n_regains else 0.0, league_per_100=100 * lg,
                team_shots=team_shots, shot_share=100 * k / team_shots if team_shots else 0.0)


def detect(ds: Dataset, events, team_id, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    rg, pairs = transition_shots(events, team_id, c)
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    if len(pairs) < c["min_shots"] or not rg or len(pairs) / len(rg) < c["min_rate_vs_league"] * lg:
        return None
    shots = sum(1 for e in events if e["event_type"] == "shot" and e["team_id"] == team_id)
    return Finding(FAMILY, team_id, [[g["event_id"], s["event_id"]] for g, s in pairs],
                   _values(ds, pairs, len(rg), shots, lg))


def recompute(ds: Dataset, ordered, team_id, anchors, scope_events, c=None):
    """Independent recompute: each (regain, shot) pair is re-read from the raw events between them;
    the regains and the team's shots are recounted over the scope with their own loop."""
    c = c or cfg(FAMILY)
    if not anchors or len(anchors) % STRIDE:
        return None, list(anchors)
    pos = {e["event_id"]: k for k, e in enumerate(ordered)}
    xg, bad = [], []
    for g in range(0, len(anchors), STRIDE):
        i, j = anchors[g], anchors[g + 1]
        if i not in pos or j not in pos or pos[j] <= pos[i]:
            bad += [i, j]
            continue
        rg, sh = ordered[pos[i]], ordered[pos[j]]
        between = ordered[pos[i] + 1:pos[j]]
        ok = (rg["event_type"] == "possession_change" and rg["team_id"] == team_id and rg["x_start"] < c["own_half_x"]
              and sh["event_type"] == "shot" and sh["team_id"] == team_id
              and sh["clock_sec"] - rg["clock_sec"] <= c["counter_sec"]
              and not any(e["event_type"] == "possession_change" or (e["event_type"] == "shot" and e["team_id"] == team_id)
                          for e in between))
        if not ok:
            bad += [i, j]
            continue
        xg.append(ds.shots[j]["xg"])
    if bad or not xg:
        return None, bad
    n = sum(1 for e in scope_events if e["event_type"] == "possession_change" and e["team_id"] == team_id
            and e["x_start"] < c["own_half_x"])
    shots = sum(1 for e in scope_events if e["event_type"] == "shot" and e["team_id"] == team_id)
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    k = len(xg)
    vals = dict(amount=k, xg=sum(xg), regains=n, per_100=100 * k / n if n else 0.0, league_per_100=100 * lg,
                team_shots=shots, shot_share=100 * k / shots if shots else 0.0)
    ok = k >= c["min_shots"] and n and k / n >= c["min_rate_vs_league"] * lg
    return (vals, []) if ok else (vals, ["pattern_does_not_hold"])
