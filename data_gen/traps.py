"""Ground-truth trap detectors.

These are deliberately simple and independent of the future `engine/`: they exist to prove the
generator really planted each trap, and to record the evidence event IDs in ground_truth.json.
The engine must later rediscover the same traps through its own metrics.
"""
from __future__ import annotations

from collections import Counter

from .config import FINAL_THIRD_X, TEAM_BY_ID, in_box, lane_of


def _ok_pass(e):
    return e["event_type"] == "pass" and e["outcome"] == "success"


def first_goal(events, team_id):
    goals = [e for e in events if e["event_type"] == "shot" and e["outcome"] == "goal"]
    gs = [e for e in goals if e["team_id"] == team_id]
    return gs[0] if gs else None


def lead_window(events, leader_id, other_id):
    """(start_sec, end_sec) of the first spell in which `leader_id` leads, or None."""
    sc = {leader_id: 0, other_id: 0}
    start = None
    for e in events:
        if e["event_type"] == "shot" and e["outcome"] == "goal":
            sc[e["team_id"]] += 1
            lead = sc[leader_id] - sc[other_id]
            if lead >= 1 and start is None:
                start = e["clock_sec"]
            elif lead < 1 and start is not None:
                return start, e["clock_sec"]
    return (start, events[-1]["clock_sec"]) if start is not None else None


def field_tilt_spell(events, window, chaser_id, min_f3=100, min_tilt=0.68, max_entry_share=0.15):
    """Field-tilt trap test on one time window (start_sec, end_sec] for the chasing team.

    Fires only when all three hold: the chaser has most of the final-third passes (tilt), enough
    volume to mean something, AND few of those passes enter the box. The last gate is what
    separates "pinned back by a deep block" from genuine dominance: a dominant side also has high
    tilt but keeps getting into the box, so it must not fire.
    """
    s, t = window
    f3 = [e for e in events if _ok_pass(e) and s < e["clock_sec"] <= t and e["x_start"] >= FINAL_THIRD_X]
    chaser = [e for e in f3 if e["team_id"] == chaser_id]
    tilt = len(chaser) / max(1, len(f3))
    entries = [e for e in chaser if in_box(e["x_end"], e["y_end"]) and not in_box(e["x_start"], e["y_start"])]
    perimeter = [e for e in chaser if not in_box(e["x_end"], e["y_end"])]
    return dict(window_sec=[s, t], chaser_field_tilt=round(tilt, 3), chaser_f3_passes=len(chaser),
                chaser_box_entries=len(entries), chaser_perimeter_passes=len(perimeter),
                evidence_event_ids=[e["event_id"] for e in perimeter[:12]] + [e["event_id"] for e in entries[:3]],
                passed=bool(tilt >= min_tilt and len(chaser) >= min_f3
                            and len(entries) <= max_entry_share * len(chaser)))


def field_tilt_trap(events, leader_id, chaser_id, min_len=1500):
    """The trap over the leader's first lead spell, if it lasts at least `min_len` seconds."""
    w = lead_window(events, leader_id, chaser_id)
    if not w or w[1] - w[0] < min_len:
        return None
    return field_tilt_spell(events, w, chaser_id)


def shot_spam_trap(events, shots, team_id, low_xg=0.08):
    mine = [s for s in shots if s["team_id"] == team_id]
    low = [s for s in mine if s["xg"] <= low_xg]
    return dict(shots=len(mine), low_xg_shots=len(low),
                mean_xg=round(sum(s["xg"] for s in mine) / max(1, len(mine)), 3),
                total_xg=round(sum(s["xg"] for s in mine), 2),
                evidence_event_ids=[s["event_id"] for s in low[:20]],
                passed=bool(len(low) >= 12 and len(low) >= 0.75 * len(mine)))


def volume_passer_trap(events, passes, player_id, wide_min=0.8):
    counts, wide = Counter(), Counter()
    by_event = {e["event_id"]: e for e in events}
    for pid, p in passes.items():
        e = by_event[pid]
        if e["outcome"] != "success" or not p["is_forward"]:
            continue
        counts[p["passer_id"]] += 1
        if lane_of(e["y_end"]) in ("left_flank", "right_flank"):
            wide[p["passer_id"]] += 1
    n = counts[player_id]
    rank = sorted(counts.values(), reverse=True).index(n) + 1 if n else None
    share = wide[player_id] / n if n else 0.0
    ev = [pid for pid, p in passes.items() if p["passer_id"] == player_id and p["is_forward"]
          and by_event[pid]["outcome"] == "success"][:15]
    return dict(forward_passes=n, rank_in_match=rank, wide_share=round(share, 3),
                evidence_event_ids=ev, passed=bool(rank is not None and rank == 1 and share >= wide_min and n >= 25))


def corner_specialist_trap(events, passes, player_id):
    by_event = {e["event_id"]: e for e in events}
    kp = [pid for pid, p in passes.items() if p["passer_id"] == player_id and p["is_key_pass"]]
    corner = [k for k in kp if passes[k]["pass_type"] == "corner"]
    op = [k for k in kp if passes[k]["pass_type"] != "corner"]
    return dict(chances_created=len(kp), from_corners=len(corner), open_play=len(op),
                evidence_event_ids=corner[:10],
                passed=bool(len(corner) >= 4 and len(corner) >= 2 * len(op)))


def flank_attack_trap(events, attacker_id, defender_id):
    """Attacker's final-third progression by lane vs the lane the defender is soft in."""
    weak = TEAM_BY_ID[defender_id].weak_lane
    f3 = [e for e in events if _ok_pass(e) and e["team_id"] == attacker_id
          and e["x_start"] < FINAL_THIRD_X <= e["x_end"]]
    lanes = Counter(lane_of(e["y_end"]) for e in f3)
    n = sum(lanes.values())
    share = (lanes["left_flank"] + lanes["left_half_space"]) / n if n else 0
    return dict(entries_into_final_third=n, left_side_share=round(share, 3), defender_weak_lane=weak,
                evidence_event_ids=[e["event_id"] for e in f3 if lane_of(e["y_end"]) == "left_flank"][:12],
                passed=bool(n >= 10 and share >= 0.5 and weak == "left_flank"))


def trap_margins(checks: dict) -> dict:
    """Relative margin by which each showcase trap clears each of its thresholds.

    Returns {"trap.metric": dict(value, threshold, kind, margin)} where kind is ">=" or "<=" and
    margin is value/threshold - 1 (for >=) or 1 - value/threshold (for <=). A margin of 0.10 means
    the value clears its threshold by 10%.
    """
    ft, ss = checks["field_tilt_while_leading"], checks["shot_spam"]
    vp, cs = checks["volume_passer"], checks["corner_specialist"]
    fl = checks["one_flank_vs_weak_lane"]
    rows = {
        "field_tilt_while_leading.chaser_field_tilt": (ft["chaser_field_tilt"], 0.68, ">="),
        "field_tilt_while_leading.chaser_f3_passes": (ft["chaser_f3_passes"], 100, ">="),
        "field_tilt_while_leading.box_entry_share": (
            ft["chaser_box_entries"] / max(1, ft["chaser_f3_passes"]), 0.15, "<="),
        "shot_spam.low_xg_shots": (ss["low_xg_shots"], 12, ">="),
        "shot_spam.low_xg_share": (ss["low_xg_shots"] / max(1, ss["shots"]), 0.75, ">="),
        "volume_passer.forward_passes": (vp["forward_passes"], 25, ">="),
        "volume_passer.rank_in_match": (vp["rank_in_match"] or 99, 1, "<="),
        "volume_passer.wide_share": (vp["wide_share"], 0.8, ">="),
        "corner_specialist.from_corners": (cs["from_corners"], 4, ">="),
        "corner_specialist.corner_vs_open_play": (cs["from_corners"], max(1, 2 * cs["open_play"]), ">="),
        "one_flank_vs_weak_lane.entries_into_final_third": (fl["entries_into_final_third"], 10, ">="),
        "one_flank_vs_weak_lane.left_side_share": (fl["left_side_share"], 0.5, ">="),
    }
    out = {}
    for k, (v, t, kind) in rows.items():
        m = v / t - 1 if kind == ">=" else 1 - v / t
        # rank is categorical: rank 1 is required exactly, so it gets full margin
        if k == "volume_passer.rank_in_match":
            m = 1.0 if v == 1 else -1.0
        out[k] = dict(value=round(v, 3), threshold=t, kind=kind, margin=round(m, 3))
    return out
