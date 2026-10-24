"""P16 Press-resistant passer (family pat_press_resistant; subject = a player).

Definition, for an outfield player (`positions`) in one scope: his passes with under_pressure = 1.
A finding needs >= min_pressured such passes, a completion rate on them >= min_completion, and
>= min_gap above the completion of his team-mates' passes under pressure in the same scope.
Anchors: all his passes under pressure in the scope, in order (completed and not).
Numbers: completed passes under pressure, passes under pressure, his completion under pressure,
the team-mates' completion under pressure, his completion on all passes (%).
Known limits: under_pressure is the feed's flag for a pressure event on the passer; it does not say
how close or how many opponents. Ten passes is a small sample, hence the gap and floor together.
"""
from __future__ import annotations

from engine.tables import Dataset

from .config import cfg
from .helpers import Finding

FAMILY = "pat_press_resistant"


def _rows(events, team_id):
    """player -> (pressured passes, completed), and the team's totals, and all passes per player."""
    pr, allp = {}, {}
    for e in events:
        if e["event_type"] != "pass" or e["team_id"] != team_id or not e["player_id"]:
            continue
        a = allp.setdefault(e["player_id"], [0, 0])
        a[0] += 1
        a[1] += e["outcome"] == "success"
        if e["under_pressure"]:
            r = pr.setdefault(e["player_id"], [])
            r.append(e)
    return pr, allp


def _values(mine, others_n, others_ok, all_n, all_ok):
    ok = sum(e["outcome"] == "success" for e in mine)
    return dict(amount=ok, pressured=len(mine), completion=100 * ok / len(mine) if mine else 0.0,
                team_completion=100 * others_ok / others_n if others_n else 0.0,
                pass_completion=100 * all_ok / all_n if all_n else 0.0)


def _holds(v, c) -> bool:
    return (v["pressured"] >= c["min_pressured"] and v["completion"] >= 100 * c["min_completion"]
            and v["completion"] - v["team_completion"] >= 100 * c["min_gap"])


def detect(ds: Dataset, events, team_id, c=None) -> list:
    c = c or cfg(FAMILY)
    pr, allp = _rows(events, team_id)
    tot_n = sum(len(v) for v in pr.values())
    tot_ok = sum(sum(e["outcome"] == "success" for e in v) for v in pr.values())
    out = []
    for pid in sorted(pr):
        if ds.players[pid]["position"] not in c["positions"]:
            continue
        mine = pr[pid]
        ok = sum(e["outcome"] == "success" for e in mine)
        v = _values(mine, tot_n - len(mine), tot_ok - ok, *allp[pid])
        if _holds(v, c):
            out.append(Finding(FAMILY, team_id, [[e["event_id"] for e in mine]], v, player_id=pid))
    return out


def recompute(ds: Dataset, player_id, anchors, scope_events, c=None):
    """Independent recompute from the scope: the anchors must be exactly the player's passes under
    pressure, in order; his and his team-mates' completion are recounted with their own loop."""
    c = c or cfg(FAMILY)
    team_id = ds.players[player_id]["team_id"]
    ids = {e["event_id"]: e for e in scope_events}
    bad = [i for i in anchors if i not in ids or ids[i]["event_type"] != "pass" or ids[i]["player_id"] != player_id
           or not ids[i]["under_pressure"]]
    mine, on, ok_o = [], 0, 0
    n_all = ok_all = 0
    for e in scope_events:
        if e["event_type"] != "pass" or e["team_id"] != team_id:
            continue
        if e["player_id"] == player_id:
            n_all += 1
            ok_all += e["outcome"] == "success"
            if e["under_pressure"]:
                mine.append(e)
        elif e["under_pressure"]:
            on += 1
            ok_o += e["outcome"] == "success"
    if bad:
        return None, bad
    if list(anchors) != [e["event_id"] for e in mine]:
        return None, sorted(set(anchors) ^ {e["event_id"] for e in mine}) or ["evidence_out_of_order"]
    v = _values(mine, on, ok_o, n_all, ok_all)
    return (v, []) if _holds(v, c) else (v, ["pattern_does_not_hold"])
