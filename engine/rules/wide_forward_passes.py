"""wide_forward_passes: forward-pass volume that goes wide and rarely reaches danger.

Applies to: metric forward_passes, subject a player. Fires when at least MIN_PASSES forward passes
are in scope, at least MIN_WIDE_SHARE end on a flank and the pass quality ratio (share into
high-threat central cells vs the league) is <= MAX_QUALITY_RATIO.
Action: context (show pass quality beside the count).
"""
from . import RuleResult

RULE_ID = "wide_forward_passes"
MIN_PASSES = 15
MIN_WIDE_SHARE = 0.70
MAX_QUALITY_RATIO = 0.5


def check(claim, ctx):
    if claim.get("metric") != "forward_passes" or claim["subject"]["kind"] != "player":
        return None
    v = ctx.values
    n = v["amount"]
    wide = v["wide_count"] / n if n else 0.0
    fired = n >= MIN_PASSES and wide >= MIN_WIDE_SHARE and v["pass_quality_ratio"] <= MAX_QUALITY_RATIO
    return RuleResult(RULE_ID, fired, "context", "forward_passes.wide_low_threat" if fired else None,
                      dict(forward_passes=n, wide_share=wide, pass_quality_ratio=v["pass_quality_ratio"]))
