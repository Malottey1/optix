"""P3 Flank Isolation (family pat_flank_isolation).

Definition: a window of `window` consecutive completed passes by the team inside one possession
(carries between them allowed) in which >= strip_share have both ends in the SAME outermost strip
(y < 15 or y > 85) and none ends in the central lane (40 <= y < 60). Overlapping or touching
windows in one possession merge into one spell.
Anchors per spell: its first and last pass.
Numbers: spells, their seconds (total), the share of the team's final-third passes (passes that
start at x >= 66.7) played inside spells, and the shots and xG later in those possessions.
Known limits: says the ball stayed on the touchline; it cannot show 1v1s, overlaps or off-ball
runs (no tracking data), and claims none.
"""
from __future__ import annotations

from .config import cfg
from .helpers import Finding, completed_pass, in_central_lane, outer_strip, possessions

FAMILY = "pat_flank_isolation"
STRIDE = 2


def _window_ok(ws, c):
    strips = [outer_strip(e["y_start"]) if outer_strip(e["y_start"]) == outer_strip(e["y_end"]) else None for e in ws]
    best = max(sum(1 for s in strips if s == "left"), sum(1 for s in strips if s == "right"))
    return best / len(ws) >= c["strip_share"] and not any(in_central_lane(e["y_end"]) for e in ws)


def detect(events, team_id, passes, shots, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    n = c["window"]
    spells = []                       # (possession actions, first pass index, last pass index)
    for poss in possessions(events, team_id):
        ps = [e for e in poss if e["event_type"] != "carry"]
        cur = None
        for i in range(0, len(ps) - n + 1):
            ws = ps[i:i + n]
            if not all(completed_pass(e) for e in ws) or not _window_ok(ws, c):
                continue
            if cur and i <= cur[1] + 1:
                cur[1] = i + n - 1
            else:
                if cur:
                    spells.append((poss, ps[cur[0]], ps[cur[1]]))
                cur = [i, i + n - 1]
        if cur:
            spells.append((poss, ps[cur[0]], ps[cur[1]]))
    if len(spells) < c["min_windows"]:
        return None
    inside = set()
    later = []
    secs = 0
    for poss, a, b in spells:
        ia, ib = poss.index(a), poss.index(b)
        inside |= {e["event_id"] for e in poss[ia:ib + 1] if e["event_type"] == "pass"}
        later += [e for e in poss[ia:] if e["event_type"] == "shot"]
        secs += b["clock_sec"] - a["clock_sec"]
    f3 = [e for e in events if completed_pass(e) and e["team_id"] == team_id and e["x_start"] >= 66.7]
    f3_in = sum(1 for e in f3 if e["event_id"] in inside)
    return Finding(FAMILY, team_id, [[a["event_id"], b["event_id"]] for _, a, b in spells],
                   dict(amount=len(spells), seconds=secs, f3_passes=len(f3),
                        f3_share=100 * f3_in / len(f3) if f3 else 0.0,
                        shots=len(later), xg=sum(shots[e["event_id"]]["xg"] for e in later)))


def recompute(by_id, ordered, passes, shots, team_id, anchors, scope_events, c=None):
    """Independent recompute: for each (first, last) pair, takes the team's passes between them,
    re-checks every 10-pass window inside, and recounts seconds, final-third share and shots."""
    c = c or cfg(FAMILY)
    if not anchors or len(anchors) % STRIDE:
        return None, list(anchors)
    pos = {e["event_id"]: k for k, e in enumerate(ordered)}
    inside, later, secs, n_sp, bad = set(), [], 0, 0, []
    n = c["window"]
    for g in range(0, len(anchors), STRIDE):
        a, b = by_id.get(anchors[g]), by_id.get(anchors[g + 1])
        if a is None or b is None or a["team_id"] != team_id or b["team_id"] != team_id or pos[b["event_id"]] < pos[a["event_id"]]:
            bad += anchors[g:g + 2]
            continue
        seg = [e for e in ordered[pos[a["event_id"]]:pos[b["event_id"]] + 1]
               if e["team_id"] == team_id and e["event_type"] in ("pass", "carry", "dribble", "shot")]
        ps = [e for e in seg if e["event_type"] != "carry"]
        ok = (len(ps) >= n and all(e["possession_id"] == a["possession_id"] for e in seg)
              and all(e["event_type"] == "pass" and e["outcome"] == "success" for e in ps))
        if ok:
            # every pass of the spell lies in at least one qualifying window
            covered = set()
            for i in range(0, len(ps) - n + 1):
                ws = ps[i:i + n]
                lefts = sum(1 for e in ws if e["y_start"] < 15 and e["y_end"] < 15)
                rights = sum(1 for e in ws if e["y_start"] > 85 and e["y_end"] > 85)
                if max(lefts, rights) / n >= c["strip_share"] and not any(40 <= e["y_end"] < 60 for e in ws):
                    covered |= set(range(i, i + n))
            ok = covered == set(range(len(ps)))
        if not ok:
            bad += anchors[g:g + 2]
            continue
        n_sp += 1
        inside |= {e["event_id"] for e in ps}
        secs += b["clock_sec"] - a["clock_sec"]
        later += [e for e in ordered[pos[a["event_id"]]:] if e["possession_id"] == a["possession_id"]
                  and e["team_id"] == team_id and e["event_type"] == "shot"]
    if bad or not n_sp:
        return None, bad
    f3 = [e for e in scope_events if e["event_type"] == "pass" and e["outcome"] == "success"
          and e["team_id"] == team_id and e["x_start"] >= 66.7]
    return dict(amount=n_sp, seconds=secs, f3_passes=len(f3),
                f3_share=100 * sum(1 for e in f3 if e["event_id"] in inside) / len(f3) if f3 else 0.0,
                shots=len(later), xg=sum(shots[e["event_id"]]["xg"] for e in later)), []
