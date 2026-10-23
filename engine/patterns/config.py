"""Pattern thresholds and zones (docs/patterns.md has the same table, with the reasons).

Every coordinate is in the ACTING team's attacking frame (engine/zones.py): x 0-100 toward the
opponent goal, y 0-100 across with y = 0 the attacker's left touchline. Lanes are 20 wide in y.
An opponent's event is flipped (100 - x, 100 - y) before it is compared with a team's own frame.

`enabled` is the experimental switch: a pattern whose hold-out recall is below 0.60 or whose
false-positive rate on unplanted team-matches is above 8% after tuning is set enabled=False and is
left out of the demo stream (docs/patterns.md, "Status").
"""
from __future__ import annotations

from engine.zones import BOX_X, BOX_Y, FINAL_THIRD_X, MIDDLE_THIRD_X  # noqa: F401  (re-exported)

# ---------- zones (attacker POV) ----------
MIDDLE_THIRD = (33.0, 67.0)          # brief: middle third x 33-67
APEX = (82.0, 92.0, 38.0, 62.0)      # x_min, x_max, y_min, y_max: the zone a cut-back is played into
GOAL_LINE_X = 94.0                   # goal-line zone x >= 94
GOAL_LINE_WIDE = (25.0, 75.0)        # ... and wide: y <= 25 or y >= 75
OUTER_STRIP = (15.0, 85.0)           # outermost flank strip: y < 15 or y > 85
SIDE_LEFT_MAX, SIDE_RIGHT_MIN = 40.0, 60.0   # a side = flank plus half-space (y < 40 or y >= 60)
CENTRAL_LANE = (40.0, 60.0)


CONFIG = {
    "pat_bait_switch": dict(
        enabled=True, min_build=15, side_share=0.70, max_build_m=20.0, max_gap_actions=2,
        min_switch_m=25.0, min_switch_dy=40.0, finish_within=3, min_instances=1),
    "pat_cutback": dict(
        enabled=True, delivery_within=2, min_back_x=5.0, shot_within=2, min_instances=1),
    "pat_flank_isolation": dict(
        enabled=True, window=10, strip_share=0.75, min_windows=1),
    "pat_elastic_low_block": dict(
        enabled=True, window_sec=900, step_sec=300, min_opp_tilt=0.65, min_outside_share=0.70,
        min_opp_shots=3, block_pctl=0.75, max_momentum=50.0, min_spell_sec=900),
    "pat_counter_press": dict(
        enabled=True, regain_sec=4, min_pressures=2, min_regains=2, min_rate_vs_league=1.5),
    "pat_rest_defence": dict(
        enabled=True, min_tilt=0.60, counter_sec=10, own_half_x=50.0, min_counter_shots=2, window_sec=1800,
        step_sec=300),
    "pat_starved_finisher": dict(
        enabled=True, touches_pctl=0.25, max_touches=15, min_unpressured_shots=2, xg_per_touch_mult=5.0,
        positions=("FW",)),
    "pat_tactical_fouling": dict(
        enabled=True, foul_sec=5, transition_sec=10, min_fouls=3, min_rate_vs_league=2.5),
}

FAMILIES = tuple(CONFIG)
# the registry icon of each family (web/src/icons); the frontend owns the mapping, this is for docs
ICONS = {f: "pattern-" + f[4:].replace("_", "-") for f in FAMILIES}


def cfg(family: str) -> dict:
    return CONFIG[family]


def enabled(family: str) -> bool:
    return bool(CONFIG[family]["enabled"])
