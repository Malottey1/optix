"""P1 Bait and Switch (family pat_bait_switch).

Definition, within one possession of the team (actions = its passes, carries, dribbles, shots):
  * a build segment: >= min_build consecutive completed passes, each <= max_build_m metres, of
    which >= side_share start AND end on one side (left = y < 40, right = y >= 60: flank plus
    half-space); carries between the passes do not break the run, anything else does;
  * then, within max_gap_actions actions after the last build pass, one completed pass of
    >= min_switch_m metres with |dy| >= min_switch_dy that ends on the opposite side;
  * then, within finish_within actions after the switch, a shot or a box entry (a completed pass
    from outside into the box).
Anchors per instance (in order): first build pass, last build pass, switch pass, finishing event.
Numbers: instances, build passes and seconds (means), switch distance (mean), shots after switches
(the finishing shots plus any shot later in the same possession) and their xG, the build side and
the share of those shots taken on the opposite side.
Known limits: event data shows where the ball went, not why; "bait" is the source name, never a
claim about intent. Possession boundaries follow the feed's possession_id.
"""
from __future__ import annotations

from statistics import mean

from .config import cfg
from .helpers import OPPOSITE, ON_BALL, Finding, box_entry, completed_pass, possessions, side_of

FAMILY = "pat_bait_switch"
STRIDE = 4


def _side_share(build):
    sides = [side_of(e["y_start"]) for e in build]
    ends = [side_of(e["y_end"]) for e in build]
    best = None
    for s in ("left", "right"):
        n = sum(1 for a, b in zip(sides, ends) if a == s and b == s)
        if best is None or n > best[1]:
            best = (s, n)
    return best[0], best[1] / len(build)


def detect(events, team_id, passes, shots, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    instances = []
    for poss in possessions(events, team_id):
        i = 0
        while i < len(poss):
            # grow a run of short completed passes from i (carries allowed in between)
            run, j = [], i
            while j < len(poss):
                e = poss[j]
                if e["event_type"] == "carry":
                    j += 1
                    continue
                if completed_pass(e) and passes[e["event_id"]]["pass_distance_m"] <= c["max_build_m"]:
                    run.append(e)
                    j += 1
                    continue
                break
            if len(run) < c["min_build"]:
                i = j + 1 if j == i else j
                continue
            side, share = _side_share(run)
            found = None
            if share >= c["side_share"]:
                last_k = poss.index(run[-1])
                for k in range(last_k + 1, min(last_k + 1 + c["max_gap_actions"], len(poss))):
                    s = poss[k]
                    if (completed_pass(s) and passes[s["event_id"]]["pass_distance_m"] >= c["min_switch_m"]
                            and abs(s["y_end"] - s["y_start"]) >= c["min_switch_dy"]
                            and side_of(s["y_end"]) == OPPOSITE[side]):
                        for f in poss[k + 1:k + 1 + c["finish_within"]]:
                            if f["event_type"] == "shot" or box_entry(f):
                                found = (k, f)
                                break
                        break
            if found:
                k, f = found
                instances.append(dict(build=run, side=side, share=share, switch=poss[k], finish=f,
                                      after=[e for e in poss[k + 1:] if e["event_type"] == "shot"]))
                i = poss.index(f) + 1
            else:
                i = j if j > i else i + 1
    if len(instances) < c["min_instances"]:
        return None
    return Finding(FAMILY, team_id, [[x["build"][0]["event_id"], x["build"][-1]["event_id"], x["switch"]["event_id"],
                                      x["finish"]["event_id"]] for x in instances],
                   _values(instances, passes, shots), detail=dict(sides=[x["side"] for x in instances]))


def _values(instances, passes, shots):
    after = [s for x in instances for s in x["after"]]
    opp = [s for x in instances for s in x["after"] if side_of(s["y_start"]) == OPPOSITE[x["side"]]]
    sides = [x["side"] for x in instances]
    return dict(amount=len(instances),
                build_passes=mean(len(x["build"]) for x in instances),
                build_seconds=mean(x["build"][-1]["clock_sec"] - x["build"][0]["clock_sec"] for x in instances),
                switch_m=mean(passes[x["switch"]["event_id"]]["pass_distance_m"] for x in instances),
                shots=len(after), xg=sum(shots[s["event_id"]]["xg"] for s in after),
                build_side_share=100 * mean(x["share"] for x in instances),
                finish_side_share=100 * len(opp) / len(after) if after else 0.0,
                build_left=sum(1 for s in sides if s == "left"))


def recompute(by_id, ordered, passes, shots, team_id, anchors, c=None):
    """Independent recompute from the anchors (never calls detect): walks the match events between
    each instance's first and last build pass, re-checks every condition, recounts the numbers.
    -> (values or None, bad anchor ids)."""
    c = c or cfg(FAMILY)
    if not anchors or len(anchors) % STRIDE:
        return None, list(anchors)
    pos = {e["event_id"]: n for n, e in enumerate(ordered)}
    rows, bad = [], []
    for g in range(0, len(anchors), STRIDE):
        a, b, s, f = (by_id.get(i) for i in anchors[g:g + STRIDE])
        if None in (a, b, s, f) or any(x["team_id"] != team_id for x in (a, b, s, f)):
            bad += anchors[g:g + STRIDE]
            continue
        poss_id = a["possession_id"]
        seg = [e for e in ordered[pos[a["event_id"]]:pos[f["event_id"]] + 1]
               if e["team_id"] == team_id and e["event_type"] in ON_BALL]
        if any(e["possession_id"] != poss_id for e in seg):
            bad.append(f["event_id"])
            continue
        ids = [e["event_id"] for e in seg]
        ib, isw, ifi = ids.index(b["event_id"]), ids.index(s["event_id"]), ids.index(f["event_id"])
        build = [e for e in seg[:ib + 1] if e["event_type"] != "carry"]
        ok_build = (len(build) >= c["min_build"]
                    and all(e["event_type"] == "pass" and e["outcome"] == "success"
                            and passes[e["event_id"]]["pass_distance_m"] <= c["max_build_m"] for e in build))
        left = sum(1 for e in build if e["y_start"] < 40 and e["y_end"] < 40)
        right = sum(1 for e in build if e["y_start"] >= 60 and e["y_end"] >= 60)
        side = "left" if left >= right else "right"
        share = max(left, right) / len(build) if build else 0.0
        far = "right" if side == "left" else "left"
        ok_switch = (0 < isw - ib <= c["max_gap_actions"] and s["event_type"] == "pass" and s["outcome"] == "success"
                     and passes[s["event_id"]]["pass_distance_m"] >= c["min_switch_m"]
                     and abs(s["y_end"] - s["y_start"]) >= c["min_switch_dy"]
                     and (s["y_end"] >= 60 if far == "right" else s["y_end"] < 40))
        ok_finish = 0 < ifi - isw <= c["finish_within"] and (
            f["event_type"] == "shot" or (f["event_type"] == "pass" and f["outcome"] == "success"
                                          and f["x_end"] >= 84 and 22 <= f["y_end"] <= 78
                                          and not (f["x_start"] >= 84 and 22 <= f["y_start"] <= 78)))
        if not (ok_build and share >= c["side_share"] and ok_switch and ok_finish):
            bad += anchors[g:g + STRIDE]
            continue
        later = [e for e in ordered[pos[s["event_id"]] + 1:]
                 if e["possession_id"] == poss_id and e["team_id"] == team_id and e["event_type"] == "shot"]
        rows.append((len(build), b["clock_sec"] - a["clock_sec"], passes[s["event_id"]]["pass_distance_m"],
                     later, side, share))
    if bad or not rows:
        return None, bad
    shots_after = [x for r in rows for x in r[3]]
    opp = [x for r in rows for x in r[3] if (x["y_start"] >= 60 if r[4] == "left" else x["y_start"] < 40)]
    n = len(rows)
    return dict(amount=n, build_passes=sum(r[0] for r in rows) / n, build_seconds=sum(r[1] for r in rows) / n,
                switch_m=sum(r[2] for r in rows) / n, shots=len(shots_after),
                xg=sum(shots[x["event_id"]]["xg"] for x in shots_after),
                build_side_share=100 * sum(r[5] for r in rows) / n,
                finish_side_share=100 * len(opp) / len(shots_after) if shots_after else 0.0,
                build_left=sum(1 for r in rows if r[4] == "left")), []
