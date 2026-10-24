"""ctx_low_possession_with_direct_threat: a low share of the passes when the team kept producing
shots within seconds of winning the ball in its own half (pattern pat_direct_transition): the
share alone reads as a side without the ball and without threat.

Applies to: metric possession_pct, subject a team, scope match or window.
Fires when the direct transition detector finds the pattern for the team in scope.
Action: context. REQUIRES transition_shots and transition_xg.
"""
from engine.patterns import direct_transition

from . import RuleResult

RULE_ID = "ctx_low_possession_with_direct_threat"
REQUIRES = ("transition_shots", "transition_xg")


def check(claim, ctx):
    if claim.get("metric") != "possession_pct" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = direct_transition.detect(ctx.ds, ctx.scope.events, ctx.team_id)
    return RuleResult(RULE_ID, f is not None, "context", "possession.shots_after_regains" if f else None,
                      dict(f.values) if f else {})
