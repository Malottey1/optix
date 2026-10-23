"""Shared helpers for the pattern detectors: possession segmentation, zones, losses and league
baselines. Pure functions over loaded tables (engine/tables.py); no detector state.

Definitions used by several patterns
    action          one of the team's on-ball events: pass, carry, dribble, shot (ON_BALL).
    possession      the team's actions with one possession_id, in order. The generator starts a new
                    possession_id whenever the ball changes team, so an opponent's pressure or
                    tackle inside a possession shares its id but is not an action of the team.
    loss            the opponent's `possession_change` event: an open-play turnover (tackle,
                    interception, loose ball, keeper hold or claim). Restarts after the ball went
                    out of play are not losses (the feed has no possession_change for them).
                    Where the ball was lost, in the losing team's frame, is the flip of where the
                    opponent won it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from engine.tables import Dataset, baseline_of, match_events
from engine.zones import in_box

from . import config as K

ON_BALL = ("pass", "carry", "dribble", "shot")


@dataclass
class Finding:
    """One detected pattern for one team (or player) in one scope.

    instances: per instance, its ordered anchor event ids (the evidence the Verifier's independent
    recompute starts from). values: the numbers the claim carries (unrounded). window: the clock
    span the finding covers (None = the scope it was detected in)."""
    family: str
    team_id: str
    instances: list
    values: dict
    player_id: str | None = None
    window: tuple | None = None
    detail: dict = field(default_factory=dict)

    @property
    def evidence(self) -> list:
        out = []
        for inst in self.instances:
            out += [i for i in inst if i not in out]
        return out


def side_of(y: float) -> str:
    """'left' (flank + half-space, y < 40), 'right' (y >= 60) or 'centre'."""
    if y < K.SIDE_LEFT_MAX:
        return "left"
    if y >= K.SIDE_RIGHT_MIN:
        return "right"
    return "centre"


OPPOSITE = {"left": "right", "right": "left"}


def outer_strip(y: float) -> str | None:
    if y < K.OUTER_STRIP[0]:
        return "left"
    if y > K.OUTER_STRIP[1]:
        return "right"
    return None


def in_central_lane(y: float) -> bool:
    return K.CENTRAL_LANE[0] <= y < K.CENTRAL_LANE[1]


def in_apex(x: float, y: float) -> bool:
    x0, x1, y0, y1 = K.APEX
    return x0 <= x <= x1 and y0 <= y <= y1


def in_goal_line_wide(x: float, y: float) -> bool:
    return x >= K.GOAL_LINE_X and (y <= K.GOAL_LINE_WIDE[0] or y >= K.GOAL_LINE_WIDE[1])


def in_middle_third(x: float) -> bool:
    return K.MIDDLE_THIRD[0] <= x < K.MIDDLE_THIRD[1]


def completed_pass(e) -> bool:
    return e["event_type"] == "pass" and e["outcome"] == "success"


def box_entry(e) -> bool:
    return completed_pass(e) and in_box(e["x_end"], e["y_end"]) and not in_box(e["x_start"], e["y_start"])


def end_point(e) -> tuple:
    """Where an action leaves the ball (pass and carry end, else where it happened)."""
    if e["x_end"] is not None and e["event_type"] in ("pass", "carry"):
        return e["x_end"], e["y_end"]
    return e["x_start"], e["y_start"]


def possessions(events, team_id) -> list:
    """The team's possessions in one match: lists of its on-ball actions sharing a possession_id."""
    out, cur, pid = [], [], None
    for e in events:
        if e["team_id"] != team_id or e["event_type"] not in ON_BALL:
            continue
        if e["possession_id"] != pid:
            if cur:
                out.append(cur)
            cur, pid = [], e["possession_id"]
        cur.append(e)
    if cur:
        out.append(cur)
    return out


def losses(events, team_id) -> list:
    """The opponent's possession_change events in these events: the team's open-play losses."""
    return [e for e in events if e["event_type"] == "possession_change" and e["opponent_team_id"] == team_id]


def loss_x(e) -> float:
    """x of a loss in the LOSING team's frame."""
    return 100.0 - e["x_start"]


def by_match(ds: Dataset) -> dict:
    return match_events(ds)


def teams_of(ds: Dataset, match_id: str) -> tuple:
    m = ds.matches[match_id]
    return m["home_team_id"], m["away_team_id"]


# ---------- league baselines (from the season the dataset is compared with) ----------

_BASE: dict = {}


def league(ds: Dataset, key: str, fn):
    """Cache a league-level number per baseline dataset (e.g. the league foul rate after losses)."""
    base = baseline_of(ds)
    k = (id(base), key)
    if k not in _BASE:
        _BASE[k] = (base, fn(base))
    return _BASE[k][1]


def quantile(xs, q: float):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * q
    lo = int(i)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)
