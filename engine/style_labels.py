"""Style labels for a team, derived from its style profile (engine/profiles.py) by fixed rules.

A label is shown only when the metric differs from the league average clearly enough:
  * the 95% interval of the team's value excludes the league average (confidence medium or high,
    see metrics.share_confidence / metrics.interval_confidence), and
  * the difference is at least MIN_SHARE_PP percentage points for a share, or MIN_MEAN_REL of the
    league average for a mean.
Otherwise the label is "league-typical". Every label carries its rule as text, and the numbers it
was decided on, so the dashboard can show the rule next to the label.

Known limits: labels compare a team with the league it plays in (the five-team season is a small
league, so "high press" means higher than these four opponents). They describe the season so far,
all game states pooled; a team that changes shape when leading is described by profiles.bracket_shift.
"""
from __future__ import annotations

MIN_SHARE_PP = 3.0
MIN_MEAN_REL = 0.05

# label id -> (profile metric, label when above the league, label when below, what the metric is)
LABELS = {
    "tempo": ("tempo_sec_per_pass", "Slow build-up", "Quick tempo", "mean seconds between consecutive passes in a sequence"),
    "press": ("press_intensity", "High press", "Low press", "pressure events per opponent pass attempted"),
    "directness": ("directness", "Direct", "Patient", "share of open-play passes that go forward (x gain >= 8)"),
    "territory": ("field_tilt", "Territorial", "Cedes territory",
                  "share of all final-third passes in its matches that are its own"),
    "counter": ("counter_share", "Counter-attacking", "Few counters",
                "share of its passing sequences that are counter-attacks"),
}


def _rule_text(metric_desc: str, above: str, below: str, kind: str) -> str:
    gap = f"at least {MIN_SHARE_PP:g} percentage points" if kind == "pp" else f"at least {MIN_MEAN_REL:.0%}"
    return (f"{above} / {below}: {metric_desc}, {gap} above / below the league average, with a 95% interval "
            f"that excludes the league average. Otherwise league-typical.")


def style_labels(profile: dict) -> list[dict]:
    """[{id, metric, label, direction ("above" / "below" / "typical"), rule, value, league, effect,
    effect_unit, interval, confidence, n}] for one team_style_profile (bracket "all")."""
    out = []
    for lid, (metric, above, below, desc) in LABELS.items():
        m = profile["metrics"][metric]
        kind = m["effect_unit"]
        clear = m["confidence"] in ("medium", "high") and m["effect"] is not None
        if clear:
            big = abs(m["effect"]) >= MIN_SHARE_PP if kind == "pp" else (
                m["league"] and abs(m["effect"]) >= MIN_MEAN_REL * abs(m["league"]))
            clear = bool(big)
        direction = "typical" if not clear else "above" if m["effect"] > 0 else "below"
        out.append(dict(id=lid, metric=metric,
                        label={"above": above, "below": below, "typical": "League-typical"}[direction],
                        direction=direction, rule=_rule_text(desc, above, below, kind),
                        value=m["value"], league=m["league"], effect=m["effect"], effect_unit=kind,
                        interval=m["interval"], confidence=m["confidence"], n=m["n"]))
    return out
