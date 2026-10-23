"""P5 Counter-Press (family pat_counter_press).

Definition: the team loses the ball (helpers.losses) in its attacking third (x >= 66.7 in its
frame) and wins it back (its own possession_change) within regain_sec seconds, with >=
min_pressures of its pressure events in between, applied in the opponent's defensive third (x >=
66.7 in the team's frame).
A finding needs >= min_regains such regains and a regain rate (regains per attacking-third loss)
>= min_rate_vs_league x the league rate.
Anchors per instance: the loss (opponent possession_change) and the regain (own possession_change).
Numbers: regains, attacking-third losses, rate (%), league rate (%), median seconds to regain,
mean regain x.
Known limits: pressure events are attempts, not proof that the press caused the turnover; the
claim says what was recorded in sequence, never why.
"""
from __future__ import annotations

from statistics import mean, median

from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league, loss_x, losses

FAMILY = "pat_counter_press"
STRIDE = 2


def _regains(evs, team_id, c):
    """(loss, regain, pressures) for each attacking-third loss regained under the rule; and the
    number of attacking-third losses."""
    out, n = [], 0
    idx = {e["event_id"]: k for k, e in enumerate(evs)}
    for lo in losses(evs, team_id):
        if loss_x(lo) < 66.7:
            continue
        n += 1
        k = idx[lo["event_id"]] + 1
        press = []
        while k < len(evs) and evs[k]["clock_sec"] <= lo["clock_sec"] + c["regain_sec"]:
            e = evs[k]
            if e["team_id"] == team_id and e["event_type"] == "pressure" and e["x_start"] >= 66.7:
                press.append(e)
            if e["event_type"] == "possession_change":
                if e["team_id"] == team_id and len(press) >= c["min_pressures"]:
                    out.append((lo, e, press))
                break
            k += 1
    return out, n


def league_rate(base: Dataset, c=None) -> float:
    c = c or cfg(FAMILY)
    hits = total = 0
    for mid, evs in match_events(base).items():
        m = base.matches[mid]
        for tid in (m["home_team_id"], m["away_team_id"]):
            r, n = _regains(evs, tid, c)
            hits += len(r)
            total += n
    return hits / total if total else 0.0


def detect(ds: Dataset, events, team_id, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    r, n = _regains(events, team_id, c)
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    if len(r) < c["min_regains"] or not n or len(r) / n < c["min_rate_vs_league"] * lg:
        return None
    return Finding(FAMILY, team_id, [[lo["event_id"], g["event_id"]] for lo, g, _ in r],
                   dict(amount=len(r), losses=n, rate=100 * len(r) / n, league_rate=100 * lg,
                        median_regain_sec=median(g["clock_sec"] - lo["clock_sec"] for lo, g, _ in r),
                        regain_x=mean(g["x_start"] for _, g, _ in r)))


def recompute(ds: Dataset, ordered, team_id, anchors, scope_events, c=None):
    """Independent recompute: each (loss, regain) pair is re-read from the raw events between them
    (no other possession change between, regain in time, pressures counted again); attacking-third
    losses are recounted over the scope."""
    c = c or cfg(FAMILY)
    if not anchors or len(anchors) % STRIDE:
        return None, list(anchors)
    pos = {e["event_id"]: k for k, e in enumerate(ordered)}
    rows, bad = [], []
    for g in range(0, len(anchors), STRIDE):
        i, j = anchors[g], anchors[g + 1]
        if i not in pos or j not in pos or pos[j] <= pos[i]:
            bad += [i, j]
            continue
        lo, rg = ordered[pos[i]], ordered[pos[j]]
        between = ordered[pos[i] + 1:pos[j]]
        n_press = sum(1 for e in between if e["team_id"] == team_id and e["event_type"] == "pressure"
                      and e["x_start"] >= 66.7)
        ok = (lo["event_type"] == "possession_change" and lo["opponent_team_id"] == team_id and 100 - lo["x_start"] >= 66.7
              and rg["event_type"] == "possession_change" and rg["team_id"] == team_id
              and rg["clock_sec"] - lo["clock_sec"] <= c["regain_sec"] and n_press >= c["min_pressures"]
              and not any(e["event_type"] == "possession_change" for e in between))
        if not ok:
            bad += [i, j]
            continue
        rows.append((rg["clock_sec"] - lo["clock_sec"], rg["x_start"]))
    if bad or not rows:
        return None, bad
    n = sum(1 for e in scope_events if e["event_type"] == "possession_change" and e["opponent_team_id"] == team_id
            and 100 - e["x_start"] >= 66.7)
    secs = sorted(r[0] for r in rows)
    k = len(secs)
    med = secs[k // 2] if k % 2 else (secs[k // 2 - 1] + secs[k // 2]) / 2
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    return dict(amount=len(rows), losses=n, rate=100 * len(rows) / n if n else 0.0, league_rate=100 * lg,
                median_regain_sec=med, regain_x=sum(r[1] for r in rows) / len(rows)), []
