"""ctx_losses_vs_immediate_regain: "lost the ball N times in the final third" when many of those
balls were won straight back (pattern pat_counter_press).

Applies to: metric final_third_losses, subject a team, scope match or window.
Fires when the counter-press detector finds the pattern for the team in scope.
Action: context. REQUIRES regains_4s and regain_share.
"""
from engine.patterns import counter_press

from . import RuleResult

RULE_ID = "ctx_losses_vs_immediate_regain"
REQUIRES = ("regains_4s", "regain_share")


def check(claim, ctx):
    if claim.get("metric") != "final_third_losses" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = counter_press.detect(ctx.ds, ctx.scope.events, ctx.team_id)
    return RuleResult(RULE_ID, f is not None, "context", "losses.won_back_at_once" if f else None,
                      dict(f.values) if f else {})
