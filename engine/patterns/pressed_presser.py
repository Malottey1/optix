"""P11 Pressed presser (family pat_pressed_presser).

Definition, for a team in one scope:
  * it presses hard: its press intensity (pressure events per opponent pass, engine metric
    press_intensity) is at or above the league's press_pctl quantile of team-match values;
  * its own passes under pressure that start in its own defensive zone (x < own_x) number
    >= min_own_passes and are completed at or below the league's completion_pctl quantile of
    team-match values (team-matches with >= min_own_passes such passes).
PPDA is not used: on this feed it ranks a non-pressing side level with a pressing one (rule
ppda_alone, docs/engine.md); press intensity is the engine's measure of the press.
Anchors: all the team's own-zone passes under pressure in the scope, in order.
Numbers: those passes not completed, the passes, their completion and the league line (%), the
team's press intensity and the league line.
Known limits: says how the team's own passes under pressure ended, not why; under_pressure does not
say how many opponents pressed.
"""
from __future__ import annotations

from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league, quantile

FAMILY = "pat_pressed_presser"


def _press(events, team_id):
    opp_passes = sum(1 for e in events if e["event_type"] == "pass" and e["opponent_team_id"] == team_id)
    pressures = sum(1 for e in events if e["event_type"] == "pressure" and e["team_id"] == team_id)
    return pressures / opp_passes if opp_passes else 0.0


def _own(events, team_id, c):
    return [e for e in events if e["event_type"] == "pass" and e["team_id"] == team_id and e["under_pressure"]
            and e["x_start"] < c["own_x"]]


def league_lines(base: Dataset, c=None) -> tuple:
    """(press intensity line, own-zone completion line) over the baseline's team-matches."""
    c = c or cfg(FAMILY)
    press, comp = [], []
    for mid, evs in match_events(base).items():
        m = base.matches[mid]
        for tid in (m["home_team_id"], m["away_team_id"]):
            press.append(_press(evs, tid))
            own = _own(evs, tid, c)
            if len(own) >= c["min_own_passes"]:
                comp.append(sum(e["outcome"] == "success" for e in own) / len(own))
    return quantile(press, c["press_pctl"]), quantile(comp, c["completion_pctl"])


def lines(ds, c=None):
    return league(ds, FAMILY + ":lines", lambda b: league_lines(b, c))


def _values(own, press, ln):
    ok = sum(e["outcome"] == "success" for e in own)
    return dict(amount=len(own) - ok, own_passes=len(own), own_completion=100 * ok / len(own) if own else 0.0,
                league_own_completion=100 * ln[1], press_intensity=press, league_press_line=ln[0])


def _holds(v, c) -> bool:
    return (v["own_passes"] >= c["min_own_passes"] and v["press_intensity"] >= v["league_press_line"]
            and v["own_completion"] <= v["league_own_completion"])


def detect(ds: Dataset, events, team_id, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    own = _own(events, team_id, c)
    v = _values(own, _press(events, team_id), lines(ds, c))
    if not _holds(v, c):
        return None
    return Finding(FAMILY, team_id, [[e["event_id"] for e in own]], v)


def recompute(ds: Dataset, team_id, anchors, scope_events, c=None):
    """Independent recompute from the scope: the anchors must be exactly the team's own-zone passes
    under pressure, in order; completion and press intensity are recounted with their own loop."""
    c = c or cfg(FAMILY)
    ids = {e["event_id"]: e for e in scope_events}
    bad = [i for i in anchors if i not in ids or ids[i]["event_type"] != "pass" or ids[i]["team_id"] != team_id
           or not ids[i]["under_pressure"] or ids[i]["x_start"] >= c["own_x"]]
    own, opp, prs = [], 0, 0
    for e in scope_events:
        if e["event_type"] == "pass" and e["team_id"] == team_id and e["under_pressure"] and e["x_start"] < c["own_x"]:
            own.append(e)
        elif e["event_type"] == "pass" and e["opponent_team_id"] == team_id:
            opp += 1
        elif e["event_type"] == "pressure" and e["team_id"] == team_id:
            prs += 1
    if bad:
        return None, bad
    if list(anchors) != [e["event_id"] for e in own]:
        return None, sorted(set(anchors) ^ {e["event_id"] for e in own}) or ["evidence_out_of_order"]
    v = _values(own, prs / opp if opp else 0.0, lines(ds, c))
    return (v, []) if _holds(v, c) else (v, ["pattern_does_not_hold"])
