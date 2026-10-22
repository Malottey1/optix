"""Insight builder: a Published claim -> one timed insight (contracts/insight.schema.json).

Every number in an insight comes from the verified claim (value, supporting_values) or from an
engine function over the ingested events (event coordinates, the rhythm and momentum series).
The insight says WHAT and WHEN; the dashboard owns the widget for each insight_type.
"""
from __future__ import annotations

from engine import flow as F
from engine import threat as T
from engine.tables import baseline_of, match_events
from engine.zones import FINAL_THIRD_X, in_box, lane_bounds

DURATION_SEC = {"matchup_mismatch": 20, "perimeter_lock": 15, "threat_pass": 10, "momentum_shift": 12,
                "rhythm_wave": 15, "volume_vs_value": 15, "set_piece_inflation": 15, "player_focus": 12,
                "milestone": 8, "recap_line": 12}
SERIES_LEN = 15
MAX_POINTS = 15


def insight_type(pub) -> str:
    """Final semantic type: what the verified claim turned out to say, not only what was asked."""
    c, rules = pub.result.claim, pub.result.claim["verification"]["rule_ids"]
    if "field_tilt_with_lead" in rules:
        return "perimeter_lock"
    if "set_piece_inflation" in rules:
        return "set_piece_inflation"
    if "shot_spam" in rules or "wide_forward_passes" in rules:
        return "volume_vs_value"
    if c["metric"] == "xg":
        return "recap_line"
    return pub.result.proposal.insight_type


def _metrics(c) -> dict:
    out = {c["metric"]: c["value"]["amount"]}
    out.update(c.get("supporting_values") or {})
    return out


def _point(e, kind=None, value=None):
    return {"event_id": e["event_id"], "x": e["x_start"], "y": e["y_start"], "x_end": e["x_end"],
            "y_end": e["y_end"], "kind": kind or e["event_type"], "value": value}


def payload(pub, view, kind: str, match_id: str) -> dict:
    c = pub.result.claim
    by_id = {e["event_id"]: e for e in (baseline_of(view).events if c["scope"] == "season" else view.events)}
    pts = [by_id[i] for i in c["evidence_event_ids"] if i in by_id][:MAX_POINTS]
    p = {"metrics": _metrics(c), "confidence": c["value"].get("confidence")}
    if kind == "matchup_mismatch":
        lo, hi = lane_bounds(c["params"]["lane"])
        p["focus"] = {"x_min": FINAL_THIRD_X, "x_max": 100.0, "y_min": lo, "y_max": hi}
        p["metrics"] = {k: c["params"][k] for k in ("attack_share", "league_share", "concede_completion",
                                                     "league_completion")} | {"lane": c["params"]["lane"]}
        p["points"] = [_point(e, "entry") for e in pts]       # season entries into the lane
    elif kind == "perimeter_lock":
        p["focus"] = {"x_min": FINAL_THIRD_X, "x_max": 100.0, "y_min": 0.0, "y_max": 100.0}
        p["points"] = [_point(e, "box_entry" if in_box(e["x_end"], e["y_end"]) else "pass") for e in pts]
    elif kind == "threat_pass":
        e = by_id[c["params"]["pass_event_id"]]
        p["points"] = [_point(e, "threat_pass", c["value"]["amount"])]
        p["focus"] = {"x_min": max(0.0, min(e["x_start"], e["x_end"]) - 10), "x_max": 100.0,
                      "y_min": max(0.0, min(e["y_start"], e["y_end"]) - 15),
                      "y_max": min(100.0, max(e["y_start"], e["y_end"]) + 15)}
    elif kind == "momentum_shift":
        m = view.matches[match_id]
        evs = match_events(view)[match_id]
        sign = 1 if c["subject"]["id"] == m["home_team_id"] else -1
        series = F.momentum(evs, view.shots, T.xt_grid(view), m["home_team_id"], m["away_team_id"]).value
        # up to the claim's window end: the triggering event can land a minute later after a long stoppage
        p["series"] = [round(sign * v, 1) for t, v in series if t <= c["window"]["to_sec"]][-SERIES_LEN:]
    elif kind == "rhythm_wave":
        evs = match_events(view)[match_id]
        p["series"] = F.rhythm(evs, end_minute=c["window"]["to_sec"] // 60, length=SERIES_LEN).value
    elif kind in ("volume_vs_value", "set_piece_inflation", "player_focus", "milestone") and pts:
        p["points"] = [_point(e) for e in pts if e["event_type"] in ("pass", "shot")]
    return p


def build_insight(pub, view, match_id: str, n: int, latency_ms: int | None) -> dict:
    c = pub.result.claim
    kind = insight_type(pub)
    m = view.matches[match_id]
    primary = c["subject"]["team_code"]
    if c["metric"] == "zone_mismatch":
        secondary = c["params"]["defender"]
    else:
        tid = view.players[c["subject"]["id"]]["team_id"] if c["subject"]["kind"] == "player" else c["subject"]["id"]
        opp = m["away_team_id"] if tid == m["home_team_id"] else m["home_team_id"]
        secondary = view.code(opp)
    ver = c["verification"]
    ins = {
        "insight_id": f"ins_{n:04d}",
        "match_id": match_id,
        "clock": {"start_sec": int(pub.result.proposal.trigger_clock), "duration_sec": DURATION_SEC.get(kind, 12),
                  "emitted_latency_ms": latency_ms},
        "insight_type": kind,
        "teams": {"primary": primary, "secondary": secondary},
        "player_ids": [c["subject"]["id"]] if c["subject"]["kind"] == "player" else [],
        "claim_id": c["claim_id"],
        "evidence_event_ids": list(c["evidence_event_ids"]),
        "verification_status": ver["status"],
        "context_chip": ({"standard_metric": c["metric"], "standard_value": c["value"]["amount"],
                          "note_key": ver["context_note"]} if ver["status"] == "published_with_context" else None),
        "payload": payload(pub, view, kind, match_id),
        "text": pub.text.as_contract(),
    }
    return ins
