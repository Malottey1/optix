"""Season-level calibration targets for the synthetic league.

These were written down BEFORE the simulator was tuned, so the simulator is fitted to them and not
the other way round. Tolerances are wide on purpose: a season is only 40 matches, so a home-win
share can swing by ten points on luck alone. Deliberately NOT encoded: streak rules, "no scoreline
above 2-2" or anything else that only shows up in tiny samples.

Targets are checked on plain aggregates of the generated tables (matches, shots, passes), never on
simulator internals, so they test what a consumer of the data actually sees.
"""
from __future__ import annotations

# name -> dict(target, lo, hi, unit, definition). lo/hi are inclusive bounds.
TARGETS = {
    "home_win_share": dict(target=0.38, lo=0.23, hi=0.53, unit="share of matches",
                           definition="matches won by the home team / matches"),
    "draw_share": dict(target=0.30, lo=0.15, hi=0.45, unit="share of matches",
                       definition="drawn matches / matches"),
    "away_win_share": dict(target=0.32, lo=0.17, hi=0.47, unit="share of matches",
                           definition="matches won by the away team / matches"),
    "goals_per_match": dict(target=2.7, lo=2.2, hi=3.2, unit="goals",
                            definition="mean of home_score + away_score"),
    "one_goal_or_less_share": dict(target=0.70, lo=0.55, hi=0.85, unit="share of matches",
                                   definition="matches with |home_score - away_score| <= 1 / matches"),
    "shots_per_match": dict(target=24.0, lo=22.0, hi=26.0, unit="shots",
                            definition="rows in shots.csv / matches (both teams)"),
    "corners_per_match": dict(target=10.5, lo=8.0, hi=13.0, unit="corners",
                              definition="passes with pass_type == corner / matches (both teams)"),
}


def season_stats(matches: list[dict], shots: list[dict], passes: list[dict]) -> dict:
    """Measure every calibration metric from table rows (dicts, values may be str or int)."""
    n = len(matches)
    hs = [int(m["home_score"]) for m in matches]
    as_ = [int(m["away_score"]) for m in matches]
    return {
        "home_win_share": sum(h > a for h, a in zip(hs, as_)) / n,
        "draw_share": sum(h == a for h, a in zip(hs, as_)) / n,
        "away_win_share": sum(h < a for h, a in zip(hs, as_)) / n,
        "goals_per_match": (sum(hs) + sum(as_)) / n,
        "one_goal_or_less_share": sum(abs(h - a) <= 1 for h, a in zip(hs, as_)) / n,
        "shots_per_match": len(shots) / n,
        "corners_per_match": sum(1 for p in passes if p["pass_type"] == "corner") / n,
    }


def check(stats: dict) -> dict:
    """Per-metric result: measured value, bounds and whether it sits inside them."""
    return {k: dict(measured=round(stats[k], 3), target=t["target"], lo=t["lo"], hi=t["hi"],
                    passed=bool(t["lo"] <= stats[k] <= t["hi"]))
            for k, t in TARGETS.items()}
