"""ctx_completion_without_pressure_split: a player's pass completion when that player kept the
ball under pressure far better than the team-mates did (pattern pat_press_resistant): one
completion figure hides the split.

Applies to: metric pass_completion, subject a player, scope match or window.
Fires when the press-resistant detector finds the pattern for that player in scope.
Action: context. REQUIRES pressured_completion and team_pressured_completion.
"""
from engine.patterns import press_resistant

from . import RuleResult

RULE_ID = "ctx_completion_without_pressure_split"
REQUIRES = ("pressured_completion", "team_pressured_completion")


def check(claim, ctx):
    if claim.get("metric") != "pass_completion" or claim["subject"]["kind"] != "player" or claim["scope"] == "season":
        return None
    pid = claim["subject"]["id"]
    f = next((x for x in press_resistant.detect(ctx.ds, ctx.scope.events, ctx.team_id) if x.player_id == pid), None)
    return RuleResult(RULE_ID, f is not None, "context", "pass_completion.under_pressure" if f else None,
                      dict(f.values) if f else {})
