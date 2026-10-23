"""P6 Rest Defence (family pat_rest_defence).

Definition: a team with field tilt >= min_tilt concedes shots within counter_sec seconds of the
opponent winning the ball (the opponent's possession_change) in the opponent's own half (x <
own_half_x in the opponent's frame). Only the first shot after each such regain counts. A finding
needs >= min_counter_shots such shots, both the tilt and the shots measured over the whole scope,
or else over the rolling window (window_sec, step step_sec) with the most such shots.
Anchors per instance: the opponent's regain, the opponent's shot.
Numbers: counter shots conceded, their xG, the team's own losses (opponent regains anywhere), counter
shots per 100 losses and the league rate, the team's field tilt.
Known limits: numbers only; the feed has no positions off the ball, so it cannot say who was
missing or why ("reckless" or any judgement is never written).
"""
from __future__ import annotations

from engine.metrics import field_tilt
from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league, losses

FAMILY = "pat_rest_defence"
STRIDE = 2


def counter_shots(evs, team_id, c):
    """(regain, shot) pairs: the opponent's first shot within counter_sec of winning the ball in its
    own half."""
    out = []
    idx = {e["event_id"]: k for k, e in enumerate(evs)}
    for g in losses(evs, team_id):
        if g["x_start"] >= c["own_half_x"]:
            continue
        k = idx[g["event_id"]] + 1
        while k < len(evs) and evs[k]["clock_sec"] <= g["clock_sec"] + c["counter_sec"]:
            e = evs[k]
            if e["event_type"] == "possession_change":
                break
            if e["event_type"] == "shot" and e["team_id"] == g["team_id"]:
                out.append((g, e))
                break
            k += 1
    return out


def league_rate(base: Dataset, c=None) -> float:
    """Counter shots conceded per own loss, over the league."""
    c = c or cfg(FAMILY)
    hits = total = 0
    for mid, evs in match_events(base).items():
        m = base.matches[mid]
        for tid in (m["home_team_id"], m["away_team_id"]):
            hits += len(counter_shots(evs, tid, c))
            total += len(losses(evs, tid))
    return hits / total if total else 0.0


def _holds(evs, team_id, c):
    tilt = field_tilt(evs, team_id).value or 0.0
    if tilt < c["min_tilt"]:
        return None
    pairs = counter_shots(evs, team_id, c)
    return (tilt, pairs) if len(pairs) >= c["min_counter_shots"] else None


def detect(ds: Dataset, events, team_id, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    window = None
    hit = _holds(events, team_id, c)
    if hit is None and events:
        best = None
        t0, t1 = events[0]["clock_sec"], events[-1]["clock_sec"]
        t = t0
        while t + c["window_sec"] <= t1:
            w = [e for e in events if t <= e["clock_sec"] <= t + c["window_sec"]]
            h = _holds(w, team_id, c)
            if h and (best is None or len(h[1]) > len(best[1][1])):
                best = ((t, t + c["window_sec"]), h, w)
            t += c["step_sec"]
        if best is None:
            return None
        window, hit, events = best
    if hit is None:
        return None
    tilt, pairs = hit
    n = len(losses(events, team_id))
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    return Finding(FAMILY, team_id, [[g["event_id"], s["event_id"]] for g, s in pairs],
                   dict(amount=len(pairs), xg=sum(ds.shots[s["event_id"]]["xg"] for _, s in pairs),
                        losses=n, per_100_losses=100 * len(pairs) / n if n else 0.0, league_per_100=100 * lg,
                        tilt=100 * tilt), window=window)


def recompute(ds: Dataset, ordered, team_id, anchors, scope_events, c=None):
    """Independent recompute: each (regain, shot) pair is re-read from the raw events between them;
    tilt and losses are recounted over the scope with their own loops."""
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
        ok = (rg["event_type"] == "possession_change" and rg["opponent_team_id"] == team_id and rg["x_start"] < c["own_half_x"]
              and sh["event_type"] == "shot" and sh["team_id"] == rg["team_id"]
              and sh["clock_sec"] - rg["clock_sec"] <= c["counter_sec"]
              and not any(e["event_type"] in ("possession_change", "shot") for e in between))
        if not ok:
            bad += [i, j]
            continue
        xg.append(ds.shots[j]["xg"])
    if bad or not xg:
        return None, bad
    own = sum(1 for e in scope_events if e["event_type"] == "pass" and e["outcome"] == "success"
              and e["team_id"] == team_id and e["x_start"] >= 66.7)
    opp = sum(1 for e in scope_events if e["event_type"] == "pass" and e["outcome"] == "success"
              and e["opponent_team_id"] == team_id and e["x_start"] >= 66.7)
    n = sum(1 for e in scope_events if e["event_type"] == "possession_change" and e["opponent_team_id"] == team_id)
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    return dict(amount=len(xg), xg=sum(xg), losses=n, per_100_losses=100 * len(xg) / n if n else 0.0,
                league_per_100=100 * lg, tilt=100 * own / (own + opp) if own + opp else 0.0), []
