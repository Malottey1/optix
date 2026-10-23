"""ctx_fouls_clustered_after_losses: a raw foul count when many of the fouls came straight after
losing the ball in midfield (pattern pat_tactical_fouling; the wording stays observational:
"fouls after losing the ball").

Applies to: metric fouls, subject a team, scope match or window.
Fires when the fouls-after-losses detector finds the pattern for the team in scope.
Action: context. REQUIRES fouls_after_losses and after_loss_share.
"""
from engine.patterns import tactical_fouling

from . import RuleResult

RULE_ID = "ctx_fouls_clustered_after_losses"
REQUIRES = ("fouls_after_losses", "after_loss_share")


def check(claim, ctx):
    if claim.get("metric") != "fouls" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = tactical_fouling.detect(ctx.ds, ctx.scope.events, ctx.team_id)
    return RuleResult(RULE_ID, f is not None, "context", "fouls.after_losing_the_ball" if f else None,
                      dict(f.values) if f else {})
