"""P7 Starved Finisher (family pat_starved_finisher; subject = a player).

Definition, for a player in `positions` (forwards) in one match:
  * touches (TOUCH_TYPES: his passes, carries, dribbles, shots and duels) at or below the league's
    touches_pctl quantile for his position over full matches, or <= max_touches;
  * >= min_unpressured_shots shots with under_pressure = 0;
  * xG per touch >= xg_per_touch_mult x the league median for his position;
  * xG of all his shots >= min_xg (a few touches and a couple of speculative shots is not the pattern).
Full matches only (full_match_only): the touch lines are full-match lines.
Evidence: his unpressured shots. Numbers: touches, shots, xG, xG per touch, the position's touch
line and median xG per touch.
Known limits: minutes are in lineups.csv but not in the engine tables, so a substitute's touches
are compared with full-match lines (the league lines use players with >= MIN_LINE_TOUCHES touches).
"""
from __future__ import annotations

from collections import defaultdict

from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league, quantile

FAMILY = "pat_starved_finisher"
TOUCH_TYPES = ("pass", "carry", "dribble", "shot", "duel")
MIN_LINE_TOUCHES = 5


def _per_player(evs, shots):
    t, xg, n_sh = defaultdict(int), defaultdict(float), defaultdict(int)
    for e in evs:
        if e["event_type"] in TOUCH_TYPES and e["player_id"]:
            t[e["player_id"]] += 1
            if e["event_type"] == "shot":
                xg[e["player_id"]] += shots[e["event_id"]]["xg"]
                n_sh[e["player_id"]] += 1
    return t, xg, n_sh


def league_lines(base: Dataset, c=None) -> dict:
    """position -> (touch line at touches_pctl, median xG per touch)."""
    c = c or cfg(FAMILY)
    touches, per = defaultdict(list), defaultdict(list)
    for mid, evs in match_events(base).items():
        t, xg, _ = _per_player(evs, base.shots)
        for pid, n in t.items():
            if n < MIN_LINE_TOUCHES:
                continue
            pos = base.players[pid]["position"]
            touches[pos].append(n)
            per[pos].append(xg[pid] / n)
    return {p: (quantile(touches[p], c["touches_pctl"]), quantile(per[p], 0.5)) for p in touches}


def lines(ds, c=None):
    return league(ds, FAMILY + ":lines", lambda b: league_lines(b, c))


def detect(ds: Dataset, events, team_id, c=None) -> list:
    """Every qualifying player of the team in these events (a list of findings)."""
    c = c or cfg(FAMILY)
    ln = lines(ds, c)
    t, xg, _ = _per_player([e for e in events if e["team_id"] == team_id], ds.shots)
    out = []
    for pid in sorted(t):
        pos = ds.players[pid]["position"]
        if pos not in c["positions"] or pos not in ln:
            continue
        line, med = ln[pos]
        free = [e for e in events if e["event_type"] == "shot" and e["player_id"] == pid and not e["under_pressure"]]
        n = t[pid]
        if (n <= line or n <= c["max_touches"]) and len(free) >= c["min_unpressured_shots"] \
                and xg[pid] / n >= c["xg_per_touch_mult"] * med and xg[pid] >= c["min_xg"]:
            out.append(Finding(FAMILY, team_id, [[e["event_id"] for e in free]],
                               dict(amount=n, shots=sum(1 for e in events if e["event_type"] == "shot" and e["player_id"] == pid),
                                    unpressured_shots=len(free), xg=xg[pid], xg_per_touch=xg[pid] / n,
                                    touch_line=line, league_xg_per_touch=med), player_id=pid))
    return out


def recompute(ds: Dataset, player_id, anchors, scope_events, c=None):
    """Independent recompute from the scope: recounts the player's touches, shots and xG; every
    anchor must be one of his unpressured shots in scope."""
    c = c or cfg(FAMILY)
    ids = {e["event_id"]: e for e in scope_events}
    bad = [i for i in anchors if i not in ids or ids[i]["event_type"] != "shot" or ids[i]["player_id"] != player_id
           or ids[i]["under_pressure"]]
    mine = [e for e in scope_events if e["player_id"] == player_id and e["event_type"] in TOUCH_TYPES]
    shots = [e for e in mine if e["event_type"] == "shot"]
    free = [e for e in shots if not e["under_pressure"]]
    xg = sum(ds.shots[e["event_id"]]["xg"] for e in shots)
    pos = ds.players[player_id]["position"]
    line, med = lines(ds, c).get(pos, (None, None))
    if bad or not mine or line is None:
        return None, bad or ["no_touches"]
    n = len(mine)
    vals = dict(amount=n, shots=len(shots), unpressured_shots=len(free), xg=xg, xg_per_touch=xg / n,
                touch_line=line, league_xg_per_touch=med)
    ok = ((n <= line or n <= c["max_touches"]) and len(free) >= c["min_unpressured_shots"]
          and xg / n >= c["xg_per_touch_mult"] * med and xg >= c["min_xg"]
          and list(anchors) == [e["event_id"] for e in free])
    return (vals, []) if ok else (vals, ["pattern_does_not_hold"])
