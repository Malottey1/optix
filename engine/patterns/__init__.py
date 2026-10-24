"""Tactical pattern library: deterministic detectors over event data, each with an independent
recompute that the Verifier uses (it never calls the detector).

A pattern claim's metric is its family id (pat_*). Its evidence is the ordered anchor events of
every instance (config and docstrings per module); the recompute walks the raw events from those
anchors, re-checks every condition and recounts every number. docs/patterns.md has the catalogue.
"""
from __future__ import annotations

from engine.tables import Dataset, match_events

from . import (bait_switch, counter_press, cutback, direct_transition, elastic_low_block, flank_isolation,
               press_resistant, pressed_presser, rest_defence, set_piece_dependence, starved_finisher,
               tactical_fouling)
from .config import CONFIG, FAMILIES, FULL_MATCH_ONLY, ICONS, enabled
from .helpers import Finding

MODULES = {m.FAMILY: m for m in (bait_switch, cutback, flank_isolation, elastic_low_block, counter_press,
                                  rest_defence, starved_finisher, tactical_fouling, set_piece_dependence,
                                  direct_transition, press_resistant, pressed_presser)}
PLAYER_FAMILIES = ("pat_starved_finisher", "pat_press_resistant")
# team families whose detector takes (ds, events, team_id) and whose recompute takes the scope
SCOPE_FAMILIES = ("pat_counter_press", "pat_rest_defence", "pat_tactical_fouling", "pat_direct_transition")
WINDOW_FAMILIES = ("pat_elastic_low_block",)       # the finding carries its own window

# claim units and the numbers each family carries (value.amount is the first)
UNITS = {f: "count" for f in FAMILIES}
VALUE_KEYS = {
    "pat_bait_switch": ("amount", "build_passes", "build_seconds", "switch_m", "shots", "xg", "build_side_share",
                        "finish_side_share", "build_left"),
    "pat_cutback": ("amount", "shots", "xg", "xg_per_shot", "cross_shots", "cross_xg_per_shot"),
    "pat_flank_isolation": ("amount", "seconds", "f3_passes", "f3_share", "shots", "xg"),
    "pat_elastic_low_block": ("amount", "opp_tilt", "opp_shots", "outside_share", "xg_per_shot", "opp_momentum",
                              "minutes", "median_xg", "block_line"),
    "pat_counter_press": ("amount", "losses", "rate", "league_rate", "median_regain_sec", "regain_x"),
    "pat_rest_defence": ("amount", "xg", "losses", "per_100_losses", "league_per_100", "tilt"),
    "pat_starved_finisher": ("amount", "shots", "unpressured_shots", "xg", "xg_per_touch", "touch_line",
                             "league_xg_per_touch"),
    "pat_tactical_fouling": ("amount", "losses", "rate", "league_rate", "shots_after_fouls", "shots_after_other",
                             "other_losses"),
    "pat_set_piece_dependence": ("amount", "set_piece_xg", "open_play_xg", "npxg", "share", "league_share"),
    "pat_direct_transition": ("amount", "xg", "regains", "per_100", "league_per_100", "team_shots", "shot_share"),
    "pat_press_resistant": ("amount", "pressured", "completion", "team_completion", "pass_completion"),
    "pat_pressed_presser": ("amount", "own_passes", "own_completion", "league_own_completion", "press_intensity",
                            "league_press_line"),
}


def detect_team(ds: Dataset, match_id: str, team_id: str, upto: int | None = None, families=None) -> list:
    """Findings for one team in one match (events up to `upto` seconds, or all)."""
    evs = [e for e in match_events(ds)[match_id] if upto is None or e["clock_sec"] <= upto]
    out = []
    for fam in families or FAMILIES:
        if families is None and not enabled(fam):
            continue
        m = MODULES[fam]
        if fam == "pat_elastic_low_block":
            f = m.detect(ds, match_id, team_id, upto)
        elif fam in SCOPE_FAMILIES or fam in ("pat_set_piece_dependence", "pat_pressed_presser"):
            f = m.detect(ds, evs, team_id)
        elif fam in PLAYER_FAMILIES:
            out += m.detect(ds, evs, team_id)
            continue
        else:
            f = m.detect(evs, team_id, ds.passes, ds.shots)
        if f is not None:
            out.append(f)
    return out


def detect_match(ds: Dataset, match_id: str, upto: int | None = None, families=None) -> list:
    m = ds.matches[match_id]
    return [f for tid in (m["home_team_id"], m["away_team_id"])
            for f in detect_team(ds, match_id, tid, upto, families)]


_POS: dict = {}


def _by_id(ds):
    key = id(ds)
    if _POS.get(key, (None,))[0] is not ds:
        _POS[key] = (ds, {e["event_id"]: e for e in ds.events})
    return _POS[key][1]


def recompute(ds: Dataset, family: str, match_id: str, subject: dict, anchors: list, scope_events: list,
              window: tuple | None):
    """The Verifier's independent recompute of a pattern claim: (values or None, bad anchor ids)."""
    m = MODULES[family]
    ordered = match_events(ds)[match_id]
    by_id = _by_id(ds)
    if family in PLAYER_FAMILIES:
        return m.recompute(ds, subject["id"], anchors, scope_events)
    tid = subject["id"]
    if family == "pat_elastic_low_block":
        return m.recompute(ds, match_id, tid, window, anchors)
    if family in SCOPE_FAMILIES:
        return m.recompute(ds, ordered, tid, anchors, scope_events)
    if family in ("pat_set_piece_dependence", "pat_pressed_presser"):
        return m.recompute(ds, tid, anchors, scope_events)
    if family == "pat_bait_switch":
        return m.recompute(by_id, ordered, ds.passes, ds.shots, tid, anchors)
    return m.recompute(by_id, ordered, ds.passes, ds.shots, tid, anchors, scope_events)


__all__ = ["CONFIG", "FAMILIES", "Finding", "MODULES", "UNITS", "VALUE_KEYS", "detect_match", "detect_team",
           "recompute", "enabled", "FULL_MATCH_ONLY", "ICONS"]
