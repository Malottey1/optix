"""Fictional teams, their hidden style seeds, and the players that carry planted traps.

Pitch frame (used by every table): x runs 0-100 toward the opponent goal, y runs 0-100 across
the pitch. Every event is stored in the ACTING team's attacking frame, so "left_flank" always
means the left of the team that is attacking. A defender's weak side is therefore also stored
from the attacker's point of view (the mirror gotcha): "weak_lane = left_flank" means attackers
coming down THEIR left find this team's defence soft.

All teams and players are fictional. No real clubs, badges or people.
"""
from __future__ import annotations

from dataclasses import dataclass

LANES = ["left_flank", "left_half_space", "center", "right_half_space", "right_flank"]
LANE_CENTERS = [10, 30, 50, 70, 90]
PITCH_LEN_M = 105.0
PITCH_WID_M = 68.0
FINAL_THIRD_X = 66.7
BOX_X = 84.0
BOX_Y = (22.0, 78.0)


def lane_of(y: float) -> str:
    return LANES[max(0, min(int(y // 20), 4))]


def in_box(x: float, y: float) -> bool:
    return x >= BOX_X and BOX_Y[0] <= y <= BOX_Y[1]


@dataclass(frozen=True)
class TeamSpec:
    team_id: str
    code: str
    name: str
    style_seed: str            # hidden ground truth, used to generate AND to test recovery
    lane_weights: tuple        # where forward passes are sent (attacker POV), sums to 1
    weak_lane: str | None      # lane (attacker POV) where this team's DEFENCE is soft
    att: float                 # attacking strength around 1.0
    dfn: float                 # defensive strength around 1.0
    press: float               # 0-1, how hard it presses when out of possession
    tempo: float               # seconds per action
    directness: float          # 0-1 chance a pass is forward
    sit_deep: float            # 0-1, how deep it drops once it leads (defensive block only)
    attacking_output: float    # chance-creation volume around 1.0, independent of sit_deep
    counter: float             # 0-1, chance a won ball becomes a fast counter
    shot_spam: float           # 0-1, tendency to shoot from distance vs a deep block
    weak_strength: float = 1.0 # scales the weak-lane bonus (1.0 = the original 5-team plant)
    archetype: str = ""        # full league only: the archetype the team was generated from
    formation: str = "4-3-3"   # see data_gen/squads.py


TEAMS = [
    # lane_weights, weak_lane, att, dfn, press, tempo, directness, sit_deep, attacking_output, counter, shot_spam
    TeamSpec("t_aur", "AUR", "Aurelia Rovers", "left-heavy counter, protects a lead by sitting deep",
             (0.38, 0.22, 0.20, 0.12, 0.08), None, 1.05, 1.00, 0.40, 4.0, 0.62, 0.85, 0.90, 0.50, 0.0,
             formation="4-2-3-1"),
    TeamSpec("t_nor", "NOR", "Northgate Town", "slow possession, soft against attacks down the attacker's left, shoots from range when chasing",
             (0.15, 0.22, 0.26, 0.22, 0.15), "left_flank", 1.06, 0.97, 0.30, 6.0, 0.35, 0.15, 1.50, 0.15, 0.8,
             weak_strength=1.5, formation="4-3-3"),
    TeamSpec("t_cal", "CAL", "Calder Athletic", "high press, central play",
             (0.10, 0.20, 0.40, 0.20, 0.10), None, 1.08, 1.06, 0.90, 4.5, 0.58, 0.30, 1.25, 0.50, 0.0,
             formation="4-3-3"),
    TeamSpec("t_ves", "VES", "Veston United", "wing play down both flanks",
             (0.30, 0.15, 0.10, 0.15, 0.30), None, 1.03, 1.00, 0.50, 5.0, 0.50, 0.40, 1.25, 0.30, 0.0,
             formation="4-2-3-1"),
    TeamSpec("t_har", "HAR", "Harbor Wanderers", "direct long-ball, shoots early and often",
             (0.20, 0.20, 0.20, 0.20, 0.20), "right_flank", 0.97, 0.95, 0.45, 3.8, 0.80, 0.50, 0.85, 0.45, 0.5,
             formation="4-4-2"),
]
TEAM_BY_ID = {t.team_id: t for t in TEAMS}

# Planted player traits keyed by (team code, role).
PLAYER_TRAITS = {
    # NOR right winger: high pass volume (a top-3 forward passer season-wide, not a runaway
    # leader), forward passes almost all end wide, rarely crosses.
    ("NOR", "right_winger"): dict(usage=1.4, cross_mult=0.15, wide_forward=True,
                                  trap_flag="volume_passer"),
    # NOR left winger: takes every corner, little open-play creativity (rarely on the ball, rarely
    # crosses), so his chances created stay corner-led even though NOR now creates more overall.
    ("NOR", "left_winger"): dict(usage=0.4, cross_mult=0.5, set_piece_taker=True,
                                 trap_flag="corner_specialist"),
    ("AUR", "striker"): dict(finishing=1.15),
    ("CAL", "striker"): dict(finishing=1.10),
}

# Applied on top of PLAYER_TRAITS for the showcase match only, so the demo shows the strong,
# unmistakable version of a trap while the season keeps the realistic one.
SHOWCASE_PLAYER_TRAITS = {
    ("NOR", "right_winger"): dict(usage=3.8),
    ("NOR", "left_winger"): dict(delivery=1.4),
}
