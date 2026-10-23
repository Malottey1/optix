"""P2 Cutback (family pat_cutback).

Definition, within one possession of the team:
  * a delivery: a completed pass, or a carry, ending in the wide goal-line zone (x >= 94 and
    y <= 25 or y >= 75);
  * within delivery_within actions: a completed backward pass (x_end <= x_start - min_back_x)
    ending in the apex zone (x 82-92, y 38-62): the cut-back;
  * a shot within shot_within actions after the cut-back.
Anchors per instance: delivery, cut-back, shot.
Numbers: cut-backs, their shots and xG, xG per shot; the same for the team's shots assisted by a
cross (passes table pass_type == "cross") in the same scope, for the comparison.
Known limits: a cut-back is read from where passes start and end; the feed has no body
orientation or defender positions.
"""
from __future__ import annotations

from .config import cfg
from .helpers import Finding, completed_pass, in_apex, in_goal_line_wide, possessions

FAMILY = "pat_cutback"
STRIDE = 3


def _delivery(e) -> bool:
    if e["event_type"] == "carry":
        return in_goal_line_wide(e["x_end"], e["y_end"])
    return completed_pass(e) and in_goal_line_wide(e["x_end"], e["y_end"])


def _cut(e, c) -> bool:
    return completed_pass(e) and e["x_end"] <= e["x_start"] - c["min_back_x"] and in_apex(e["x_end"], e["y_end"])


def cross_shots(events, team_id, passes, shots):
    """The team's shots whose assist pass is a cross (shots table assist_event_id)."""
    out = []
    for e in events:
        if e["event_type"] == "shot" and e["team_id"] == team_id:
            a = shots[e["event_id"]]["assist_event_id"]
            if a and a in passes and passes[a]["pass_type"] == "cross":
                out.append(e)
    return out


def detect(events, team_id, passes, shots, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    inst = []
    for poss in possessions(events, team_id):
        k = 0
        while k < len(poss):
            if not _delivery(poss[k]):
                k += 1
                continue
            hit = None
            for j in range(k + 1, min(k + 1 + c["delivery_within"], len(poss))):
                if _cut(poss[j], c):
                    for m in range(j + 1, min(j + 1 + c["shot_within"], len(poss))):
                        if poss[m]["event_type"] == "shot":
                            hit = (j, m)
                            break
                    break
            if hit:
                inst.append([poss[k]["event_id"], poss[hit[0]]["event_id"], poss[hit[1]]["event_id"]])
                k = hit[1] + 1
            else:
                k += 1
    if len(inst) < c["min_instances"]:
        return None
    return Finding(FAMILY, team_id, inst, _values([shots[i[2]]["xg"] for i in inst],
                                                   cross_shots(events, team_id, passes, shots), shots))


def _values(cut_xg, crosses, shots):
    cx = [shots[e["event_id"]]["xg"] for e in crosses]
    return dict(amount=len(cut_xg), shots=len(cut_xg), xg=sum(cut_xg),
                xg_per_shot=sum(cut_xg) / len(cut_xg) if cut_xg else 0.0,
                cross_shots=len(cx), cross_xg_per_shot=sum(cx) / len(cx) if cx else 0.0)


def recompute(by_id, ordered, passes, shots, team_id, anchors, scope_events, c=None):
    """Independent recompute from the anchors: re-checks each delivery / cut-back / shot triple
    against the raw events between them, then recounts; cross shots come from the scope."""
    c = c or cfg(FAMILY)
    if not anchors or len(anchors) % STRIDE:
        return None, list(anchors)
    pos = {e["event_id"]: n for n, e in enumerate(ordered)}
    xgs, bad = [], []
    for g in range(0, len(anchors), STRIDE):
        d, cb, sh = (by_id.get(i) for i in anchors[g:g + STRIDE])
        if None in (d, cb, sh) or any(x["team_id"] != team_id for x in (d, cb, sh)):
            bad += anchors[g:g + STRIDE]
            continue
        acts = [e for e in ordered[pos[d["event_id"]]:pos[sh["event_id"]] + 1]
                if e["team_id"] == team_id and e["event_type"] in ("pass", "carry", "dribble", "shot")]
        ids = [e["event_id"] for e in acts]
        same = all(e["possession_id"] == d["possession_id"] for e in acts)
        de_ok = (d["event_type"] in ("pass", "carry") and (d["event_type"] == "carry" or d["outcome"] == "success")
                 and d["x_end"] >= 94 and (d["y_end"] <= 25 or d["y_end"] >= 75))
        cb_ok = (cb["event_type"] == "pass" and cb["outcome"] == "success" and cb["x_end"] <= cb["x_start"] - c["min_back_x"]
                 and 82 <= cb["x_end"] <= 92 and 38 <= cb["y_end"] <= 62)
        gaps_ok = (cb["event_id"] in ids and 0 < ids.index(cb["event_id"]) <= c["delivery_within"]
                   and 0 < ids.index(sh["event_id"]) - ids.index(cb["event_id"]) <= c["shot_within"])
        if not (same and de_ok and cb_ok and gaps_ok and sh["event_type"] == "shot"):
            bad += anchors[g:g + STRIDE]
            continue
        xgs.append(shots[sh["event_id"]]["xg"])
    if bad or not xgs:
        return None, bad
    cx = [shots[e["event_id"]]["xg"] for e in scope_events if e["event_type"] == "shot" and e["team_id"] == team_id
          and shots[e["event_id"]]["assist_event_id"] in passes
          and passes[shots[e["event_id"]]["assist_event_id"]]["pass_type"] == "cross"]
    return dict(amount=len(xgs), shots=len(xgs), xg=sum(xgs), xg_per_shot=sum(xgs) / len(xgs),
                cross_shots=len(cx), cross_xg_per_shot=sum(cx) / len(cx) if cx else 0.0), []
