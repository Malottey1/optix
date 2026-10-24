"""ctx_press_without_secure_build_up: a pressing figure for a team that pressed hard but, under
pressure near its own goal, completed few of its own passes (pattern pat_pressed_presser): the
press figure alone reads as control.

Applies to: metric ppda, subject a team, scope match or window.
Fires when the pressed presser detector finds the pattern for the team in scope.
Action: context. REQUIRES own_zone_completion and league_own_completion.
"""
from engine.patterns import pressed_presser

from . import RuleResult

RULE_ID = "ctx_press_without_secure_build_up"
REQUIRES = ("own_zone_completion", "league_own_completion")


def check(claim, ctx):
    if claim.get("metric") != "ppda" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = pressed_presser.detect(ctx.ds, ctx.scope.events, ctx.team_id)
    return RuleResult(RULE_ID, f is not None, "context", "ppda.loose_under_pressure_at_the_back" if f else None,
                      dict(f.values) if f else {})
