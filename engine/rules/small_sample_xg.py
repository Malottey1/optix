"""small_sample_xg: an xG figure from too few shots to mean much.

Applies to: metric xg or npxg with scope match or window. Fires when the subject has fewer than
MIN_SHOTS shots in scope: a single big chance can dominate the total. Season claims do not fire.
Action: context (show the shot count beside the xG).
"""
from . import RuleResult

RULE_ID = "small_sample_xg"
MIN_SHOTS = 8


def check(claim, ctx):
    if claim.get("metric") not in ("xg", "npxg") or claim.get("scope") == "season":
        return None
    n = ctx.values["shots"]
    fired = n < MIN_SHOTS
    return RuleResult(RULE_ID, fired, "context", "xg.small_sample" if fired else None, dict(shots=n))
