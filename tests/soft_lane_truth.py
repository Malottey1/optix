"""Test helper (reads generator output and ground truth, so it lives with the tests, never in engine/).

The TRUE size of a planted soft lane: the generator logs every pass's modelled success probability
(pass_difficulty = 1 - p). The weak-lane bonus added to an entry pass is 0.09 * weak_strength
(0.06 + 0.03 for ending in the final third; data_gen/simulator.py). Removing it gives the probability
the pass would have had without the plant. Passes clamped at the 0.97 ceiling may have had a raw
probability above it, so their true lift is anywhere in [0, bonus]: we report both bounds.
"""
from engine.zones import FINAL_THIRD_X, lane_of

ENTRY_BONUS = 0.09
P_FLOOR, P_CEIL = 0.30, 0.97


def true_soft_lane_effect(ds, team_id, lane, strength) -> dict:
    bonus = ENTRY_BONUS * strength
    lo = hi = 0.0
    n = 0
    for e in ds.events:
        if (e["event_type"] != "pass" or e["opponent_team_id"] != team_id
                or not (e["x_start"] < FINAL_THIRD_X <= e["x_end"]) or lane_of(e["y_end"]) != lane):
            continue
        p = 1 - ds.passes[e["event_id"]]["pass_difficulty"]
        without = max(P_FLOOR, p - bonus)
        n += 1
        hi += p - without
        lo += 0.0 if p >= P_CEIL - 1e-9 else p - without
    return dict(n=n, effect_pp_low=100 * lo / n if n else 0.0, effect_pp_high=100 * hi / n if n else 0.0)
