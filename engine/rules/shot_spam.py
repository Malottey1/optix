"""shot_spam: a big shot count or xG total built from many low-quality shots.

Applies to: metric xg or npxg, subject a team. Fires when the subject has at least MIN_SHOTS shots
in scope, at least MIN_LOW_SHARE of them have xG <= LOW_XG, and mean xG per shot <= MAX_MEAN_XG.
Action: context (publish with xG per shot beside the total).
"""
from . import RuleResult

RULE_ID = "shot_spam"
MIN_SHOTS = 10
LOW_XG = 0.08
MIN_LOW_SHARE = 0.75
MAX_MEAN_XG = 0.07


def check(claim, ctx):
    if claim.get("metric") not in ("xg", "npxg") or claim["subject"]["kind"] != "team":
        return None
    v = ctx.values
    n = v["shots"]
    low_share = v["low_xg_shots"] / n if n else 0.0
    fired = n >= MIN_SHOTS and low_share >= MIN_LOW_SHARE and v["xg_per_shot"] <= MAX_MEAN_XG
    return RuleResult(RULE_ID, fired, "context", "xg.volume_of_low_quality_shots" if fired else None,
                      dict(shots=n, low_share=low_share, xg_per_shot=v["xg_per_shot"]))
