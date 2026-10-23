"""ctx_crosses_vs_cutbacks: "crosses create the danger" when the cut-backs did.

Applies to: metric crosses, subject a team, scope match or window.
Fires when the cut-back detector (pattern pat_cutback) finds >= MIN_CUTBACKS cut-backs ending in
a shot and their xG per shot is above the xG per shot of the team's cross-assisted shots (or the
crosses led to no shot at all).
Action: context. REQUIRES cutbacks and cutback_xg_per_shot beside the cross numbers.
"""
from engine.patterns import cutback

from . import RuleResult

RULE_ID = "ctx_crosses_vs_cutbacks"
MIN_CUTBACKS = 1
REQUIRES = ("cutbacks", "cutback_xg_per_shot")


def check(claim, ctx):
    if claim.get("metric") != "crosses" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = cutback.detect(ctx.scope.events, ctx.team_id, ctx.ds.passes, ctx.ds.shots)
    fired = bool(f and f.values["amount"] >= MIN_CUTBACKS
                 and (f.values["cross_shots"] == 0 or f.values["xg_per_shot"] > f.values["cross_xg_per_shot"]))
    detail = dict(f.values) if f else {}
    return RuleResult(RULE_ID, fired, "context", "crosses.cutbacks_carried_the_danger" if fired else None, detail)
