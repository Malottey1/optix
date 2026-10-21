"""Pitch zones, always from the attacking team's point of view.

Frame: x runs 0-100 from the acting team's own goal toward the opponent goal, y runs 0-100 across
the pitch (0 = the attacker's left touchline). Every event in the data is stored in the acting
team's frame, so "left_flank" always means the left of the team in possession.

A defender's soft side is therefore also expressed from the attacker's point of view: if attackers
coming down THEIR left find a defence soft, that defence is weak in "left_flank" (its own right).
To view a point from the other team's frame use `flip`.

These definitions are kept independent of the generator package on purpose (the engine must not
depend on generator internals); tests check they agree with the data dictionary.
"""
from __future__ import annotations

LANES = ("left_flank", "left_half_space", "center", "right_half_space", "right_flank")
LANE_EDGES = (20.0, 40.0, 60.0, 80.0)          # lane i covers [edge[i-1], edge[i]) in y
WIDE_LANES = ("left_flank", "right_flank")

THIRDS = ("defensive", "middle", "attacking")
MIDDLE_THIRD_X = 33.3
FINAL_THIRD_X = 66.7                            # x >= 66.7 is the final (attacking) third

BOX_X = 84.0                                    # penalty box: x >= 84 and 22 <= y <= 78
BOX_Y = (22.0, 78.0)


def lane_of(y: float) -> str:
    """Lane of a y coordinate (attacker POV). y = 100 falls in right_flank."""
    for name, edge in zip(LANES, LANE_EDGES):
        if y < edge:
            return name
    return LANES[-1]


def third_of(x: float) -> str:
    if x >= FINAL_THIRD_X:
        return "attacking"
    if x >= MIDDLE_THIRD_X:
        return "middle"
    return "defensive"


def in_final_third(x: float) -> bool:
    return x >= FINAL_THIRD_X


def in_box(x: float, y: float) -> bool:
    return x >= BOX_X and BOX_Y[0] <= y <= BOX_Y[1]


def flip(x: float, y: float) -> tuple[float, float]:
    """The same pitch point seen from the other team's attacking frame."""
    return 100.0 - x, 100.0 - y
