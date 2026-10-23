"""P8 Fouls after losing the ball (family pat_tactical_fouling; the family id is the source name,
every sentence and label is observational: "fouls after losing the ball").

Definition: a foul by the team within foul_sec seconds of losing the ball (helpers.losses) in the
middle third (33 <= x < 67 in the team's frame), with no other possession change in between. Only
the first such foul per loss counts. A finding needs >= min_fouls and a rate per middle-third loss
>= min_rate_vs_league x the league rate.
Anchors per instance: the loss, the foul.
Numbers: such fouls, middle-third losses, rate and league rate (%), and the opponent's shots
within transition_sec after those fouls against after the middle-third losses that were not
followed by a foul (per 100 losses each).
Known limits: the feed records the foul, not why it was committed; nothing here says a foul was
chosen or "tactical".
"""
from __future__ import annotations

from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league, loss_x, losses

FAMILY = "pat_tactical_fouling"
STRIDE = 2


def _mid_losses(evs, team_id, c):
    """(loss, first foul or None, opponent shots within transition_sec after the foul or loss)."""
    out = []
    idx = {e["event_id"]: k for k, e in enumerate(evs)}
    for lo in losses(evs, team_id):
        if not 33.0 <= loss_x(lo) < 67.0:
            continue
        k = idx[lo["event_id"]] + 1
        foul = None
        while k < len(evs) and evs[k]["clock_sec"] <= lo["clock_sec"] + c["foul_sec"]:
            e = evs[k]
            if e["event_type"] == "possession_change":
                break
            if e["event_type"] == "foul" and e["team_id"] == team_id:
                foul = e
                break
            k += 1
        t0 = (foul or lo)["clock_sec"]
        start = idx[(foul or lo)["event_id"]] + 1
        shots = 0
        for e in evs[start:]:
            if e["clock_sec"] > t0 + c["transition_sec"]:
                break
            if e["event_type"] == "shot" and e["team_id"] == lo["team_id"]:
                shots += 1
        out.append((lo, foul, shots))
    return out


def league_rate(base: Dataset, c=None) -> float:
    c = c or cfg(FAMILY)
    hits = total = 0
    for mid, evs in match_events(base).items():
        m = base.matches[mid]
        for tid in (m["home_team_id"], m["away_team_id"]):
            rows = _mid_losses(evs, tid, c)
            hits += sum(1 for r in rows if r[1])
            total += len(rows)
    return hits / total if total else 0.0


def _values(rows, lg):
    fouled = [r for r in rows if r[1]]
    rest = [r for r in rows if not r[1]]
    n = len(rows)
    return dict(amount=len(fouled), losses=n, rate=100 * len(fouled) / n if n else 0.0, league_rate=100 * lg,
                shots_after_fouls=sum(r[2] for r in fouled), shots_after_other=sum(r[2] for r in rest),
                other_losses=len(rest))


def detect(ds: Dataset, events, team_id, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    rows = _mid_losses(events, team_id, c)
    fouled = [r for r in rows if r[1]]
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    if len(fouled) < c["min_fouls"] or len(fouled) / len(rows) < c["min_rate_vs_league"] * lg:
        return None
    return Finding(FAMILY, team_id, [[lo["event_id"], f["event_id"]] for lo, f, _ in fouled], _values(rows, lg))


def recompute(ds: Dataset, ordered, team_id, anchors, scope_events, c=None):
    """Independent recompute: each (loss, foul) pair is re-read from the raw events between them;
    middle-third losses and the transition shots are recounted over the scope with their own loop."""
    c = c or cfg(FAMILY)
    if not anchors or len(anchors) % STRIDE:
        return None, list(anchors)
    pos = {e["event_id"]: k for k, e in enumerate(ordered)}
    bad, pairs = [], {}
    for g in range(0, len(anchors), STRIDE):
        i, j = anchors[g], anchors[g + 1]
        if i not in pos or j not in pos or pos[j] <= pos[i]:
            bad += [i, j]
            continue
        lo, fo = ordered[pos[i]], ordered[pos[j]]
        between = ordered[pos[i] + 1:pos[j]]
        ok = (lo["event_type"] == "possession_change" and lo["opponent_team_id"] == team_id
              and 33.0 <= 100 - lo["x_start"] < 67.0 and fo["event_type"] == "foul" and fo["team_id"] == team_id
              and fo["clock_sec"] - lo["clock_sec"] <= c["foul_sec"]
              and not any(e["event_type"] == "possession_change" or (e["event_type"] == "foul" and e["team_id"] == team_id)
                          for e in between))
        if not ok:
            bad += [i, j]
            continue
        pairs[i] = fo
    if bad or not pairs:
        return None, bad
    sc = [e for e in scope_events]
    spos = {e["event_id"]: k for k, e in enumerate(sc)}
    n = after_f = after_o = n_o = 0
    for e in sc:
        if not (e["event_type"] == "possession_change" and e["opponent_team_id"] == team_id
                and 33.0 <= 100 - e["x_start"] < 67.0):
            continue
        n += 1
        ref = pairs.get(e["event_id"], e)
        k = spos[ref["event_id"]] + 1
        cnt = 0
        while k < len(sc) and sc[k]["clock_sec"] <= ref["clock_sec"] + c["transition_sec"]:
            cnt += sc[k]["event_type"] == "shot" and sc[k]["team_id"] == e["team_id"]
            k += 1
        if e["event_id"] in pairs:
            after_f += cnt
        else:
            after_o += cnt
            n_o += 1
    lg = league(ds, FAMILY, lambda b: league_rate(b, c))
    return dict(amount=len(pairs), losses=n, rate=100 * len(pairs) / n if n else 0.0, league_rate=100 * lg,
                shots_after_fouls=after_f, shots_after_other=after_o, other_losses=n_o), []
