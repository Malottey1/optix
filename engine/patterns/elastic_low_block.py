"""P4 Elastic Low Block (family pat_elastic_low_block; subject = the DEFENDING team D).

Definition, over rolling windows of window_sec (step step_sec) inside one period, where A is D's
opponent:
  * A's field tilt (A's share of final-third passes, engine/metrics.field_tilt) >= min_opp_tilt;
  * A took >= min_opp_shots shots, >= min_outside_share of them from outside the box, with xG per
    shot below the league median shot xG;
  * D's blocks + clearances in the window are above the league's block_pctl quantile of that
    count over all team windows of the same length;
  * A's mean engine momentum (engine/flow.momentum, from A's side) over the window is at most
    max_momentum: territory without a run of danger.
Qualifying windows that overlap merge into one spell; a finding is the longest spell (>=
min_spell_sec).
Evidence: D's blocks and clearances and A's shots inside the spell.
Numbers: A's tilt, A's shots, outside-box share, xG per shot (and the league median), D's blocks +
clearances (and the league line), spell minutes.
Known limits: event data has no defensive shape; "low block" names the outcome pattern (A's
territory, long-range shots, D's blocks and clearances), not a formation or a choice.
"""
from __future__ import annotations

from engine import flow as F
from engine import threat as T
from engine.metrics import field_tilt
from engine.tables import Dataset, baseline_of, match_events
from engine.zones import in_box

from .config import cfg
from .helpers import Finding, league, quantile

FAMILY = "pat_elastic_low_block"
DEFENSIVE = ("block", "clearance")


def _windows(evs, c):
    """(period, from, to) windows inside each period."""
    out = []
    for period in sorted({e["period"] for e in evs}):
        pe = [e for e in evs if e["period"] == period]
        t0, t1 = pe[0]["clock_sec"], pe[-1]["clock_sec"]
        t = t0
        while t + c["window_sec"] <= t1:
            out.append((period, t, t + c["window_sec"]))
            t += c["step_sec"]
    return out


def league_lines(base: Dataset, c=None) -> dict:
    """League median shot xG and the block_pctl quantile of a team's blocks + clearances per window."""
    c = c or cfg(FAMILY)
    xgs = [s["xg"] for s in base.shots.values() if s["shot_type"] != "penalty"]
    counts = []
    for mid, evs in match_events(base).items():
        m = base.matches[mid]
        for _, a, b in _windows(evs, c):
            if b - a < c["window_sec"]:
                continue
            for tid in (m["home_team_id"], m["away_team_id"]):
                counts.append(sum(1 for e in evs if a <= e["clock_sec"] <= b and e["team_id"] == tid
                                  and e["event_type"] in DEFENSIVE))
    return dict(median_xg=quantile(xgs, 0.5), block_line=quantile(counts, c["block_pctl"]))


def lines(ds: Dataset, c=None):
    return league(ds, FAMILY + ":lines", lambda b: league_lines(b, c))


def window_values(evs, shots, d_id, a_id, a, b, mom=None):
    """The window's numbers for defender d_id against attacker a_id (shared by detect and the
    rule; the Verifier's recompute uses its own code)."""
    w = [e for e in evs if a <= e["clock_sec"] <= b]
    tilt = field_tilt(w, a_id).value or 0.0
    a_shots = [e for e in w if e["event_type"] == "shot" and e["team_id"] == a_id]
    outside = [e for e in a_shots if not in_box(e["x_start"], e["y_start"])]
    xg = [shots[e["event_id"]]["xg"] for e in a_shots]
    blocks = [e for e in w if e["team_id"] == d_id and e["event_type"] in DEFENSIVE]
    vals = dict(opp_tilt=100 * tilt, opp_shots=len(a_shots),
                outside_share=100 * len(outside) / len(a_shots) if a_shots else 0.0,
                xg_per_shot=sum(xg) / len(xg) if xg else 0.0, blocks_clearances=len(blocks))
    if mom is not None:
        steps = [v for t, v in mom if a <= t <= b]
        vals["opp_momentum"] = sum(steps) / len(steps) if steps else 0.0
    return vals, blocks + a_shots


def _momentum(ds, mid, a_id):
    m = ds.matches[mid]
    r = F.momentum(match_events(ds)[mid], ds.shots, T.xt_grid(ds), m["home_team_id"], m["away_team_id"])
    sign = 1 if a_id == m["home_team_id"] else -1
    return [(t, sign * v) for t, v in r.value]


def qualifies(v, ln, c, span_sec=None) -> bool:
    """All four conditions. Over a merged spell longer than one window, blocks + clearances are
    compared with the line per window length (count x window_sec / span)."""
    rate = v["blocks_clearances"] * c["window_sec"] / span_sec if span_sec else v["blocks_clearances"]
    return (v["opp_tilt"] >= 100 * c["min_opp_tilt"] and v["opp_shots"] >= c["min_opp_shots"]
            and v["outside_share"] >= 100 * c["min_outside_share"] and v["xg_per_shot"] < ln["median_xg"]
            and rate > ln["block_line"] and v.get("opp_momentum", 0.0) <= c["max_momentum"])


def detect(ds: Dataset, match_id: str, d_id: str, upto: int | None = None, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    evs = [e for e in match_events(ds)[match_id] if upto is None or e["clock_sec"] <= upto]
    if not evs:
        return None
    m = ds.matches[match_id]
    a_id = m["away_team_id"] if d_id == m["home_team_id"] else m["home_team_id"]
    ln = lines(ds, c)
    mom = _momentum(ds, match_id, a_id)
    spells = []
    for period, a, b in _windows(evs, c):
        if b - a < c["window_sec"]:
            continue
        v, _ = window_values(evs, ds.shots, d_id, a_id, a, b, mom)
        if not qualifies(v, ln, c):
            continue
        if spells and spells[-1][0] == period and a <= spells[-1][2]:
            spells[-1][2] = b
        else:
            spells.append([period, a, b])
    spells = [s for s in spells if s[2] - s[1] >= c["min_spell_sec"]]
    if not spells:
        return None
    _, a, b = max(spells, key=lambda s: (s[2] - s[1], -s[1]))
    v, ev = window_values(evs, ds.shots, d_id, a_id, a, b, mom)
    if not qualifies(v, ln, c, b - a):
        # the merged spell as a whole falls short: report its first qualifying window instead
        b = a + c["window_sec"]
        v, ev = window_values(evs, ds.shots, d_id, a_id, a, b, mom)
    v = dict(amount=v["blocks_clearances"], **{k: x for k, x in v.items() if k != "blocks_clearances"},
             minutes=(b - a) / 60, median_xg=ln["median_xg"], block_line=ln["block_line"])
    return Finding(FAMILY, d_id, [[e["event_id"] for e in ev]], v, window=(a, b),
                   detail=dict(attacker=a_id, spells=[(s[1], s[2]) for s in spells]))


def recompute(ds: Dataset, match_id: str, d_id: str, window, anchors, c=None):
    """Independent recompute over the claim window: recounts every condition from the raw events
    (its own loops; the league lines are the same league numbers). Every anchor must be one of
    D's blocks or clearances, or one of A's shots, inside the window, and all of them are there."""
    c = c or cfg(FAMILY)
    a, b = window
    m = ds.matches[match_id]
    a_id = m["away_team_id"] if d_id == m["home_team_id"] else m["home_team_id"]
    w = [e for e in match_events(ds)[match_id] if a <= e["clock_sec"] <= b]
    ids = {e["event_id"]: e for e in w}
    bad = [i for i in anchors if i not in ids or not (
        (ids[i]["team_id"] == d_id and ids[i]["event_type"] in DEFENSIVE)
        or (ids[i]["team_id"] == a_id and ids[i]["event_type"] == "shot"))]
    # the evidence is the whole set, in the detector's order: every block and clearance of D in the
    # window, then every shot of A; a missing or extra event is caught here, not only a wrong one
    full = [e["event_id"] for e in w if e["team_id"] == d_id and e["event_type"] in DEFENSIVE] + \
           [e["event_id"] for e in w if e["team_id"] == a_id and e["event_type"] == "shot"]
    if not bad and list(anchors) != full:
        bad = sorted(set(anchors) ^ set(full)) or ["evidence_out_of_order"]
    a_f3 = sum(1 for e in w if e["event_type"] == "pass" and e["outcome"] == "success" and e["team_id"] == a_id
               and e["x_start"] >= 66.7)
    d_f3 = sum(1 for e in w if e["event_type"] == "pass" and e["outcome"] == "success" and e["team_id"] == d_id
               and e["x_start"] >= 66.7)
    sh = [e for e in w if e["event_type"] == "shot" and e["team_id"] == a_id]
    out = sum(1 for e in sh if not (e["x_start"] >= 84 and 22 <= e["y_start"] <= 78))
    blocks = sum(1 for e in w if e["team_id"] == d_id and e["event_type"] in DEFENSIVE)
    xg = sum(ds.shots[e["event_id"]]["xg"] for e in sh)
    mom = _momentum(ds, match_id, a_id)
    steps = [v for t, v in mom if a <= t <= b]
    ln = lines(ds, c)
    vals = dict(amount=blocks, opp_tilt=100 * a_f3 / (a_f3 + d_f3) if a_f3 + d_f3 else 0.0, opp_shots=len(sh),
                outside_share=100 * out / len(sh) if sh else 0.0, xg_per_shot=xg / len(sh) if sh else 0.0,
                opp_momentum=sum(steps) / len(steps) if steps else 0.0, minutes=(b - a) / 60,
                median_xg=ln["median_xg"], block_line=ln["block_line"])
    check = dict(vals, blocks_clearances=blocks)
    if bad or not qualifies(check, ln, c, b - a):
        return (None if bad else vals), bad or ["window_does_not_qualify"]
    return vals, []
