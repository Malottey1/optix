"""ctx_low_volume_high_quality: a "quiet game" claim about a forward whose few touches included
clear chances (pattern pat_starved_finisher). Low involvement is not a poor performance here.

Applies to: metric player_touches, subject a player, scope match or window.
Fires when the starved-finisher detector finds the pattern for the player in scope.
Action: block (the claim misleads whatever context is added; the pattern claim says it instead).
"""
from engine.patterns import starved_finisher

from . import RuleResult

RULE_ID = "ctx_low_volume_high_quality"
REQUIRES = ()


def check(claim, ctx):
    if claim.get("metric") != "player_touches" or claim["subject"]["kind"] != "player" or claim["scope"] == "season":
        return None
    pid = claim["subject"]["id"]
    found = [f for f in starved_finisher.detect(ctx.ds, ctx.scope.events, ctx.team_id) if f.player_id == pid]
    return RuleResult(RULE_ID, bool(found), "block", "touches.few_but_clear_chances" if found else None,
                      dict(found[0].values) if found else {})
