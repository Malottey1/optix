"""ctx_attack_side_vs_finish_side: "attacks mostly down one side" when the shots came from the other.

A team that builds on one side and then switches play (pattern pat_bait_switch) shows a lane share
that points to the build side, while its shots after the switches come from the far side.
Applies to: metric attack_side_share, subject a team, scope match or window.
Fires when, over the claim's scope, the bait-and-switch detector finds >= 1 instance whose build
was on the claimed side and most shots after those switches (> MIN_FAR_SHARE) were taken on the
opposite side.
Action: context. REQUIRES team_shots and opposite_shot_share (the sentence says where the shots
came from, not only where the ball went).
"""
from engine.patterns import bait_switch

from . import RuleResult

RULE_ID = "ctx_attack_side_vs_finish_side"
MIN_FAR_SHARE = 50.0
REQUIRES = ("team_shots", "opposite_shot_share")


def check(claim, ctx):
    if claim.get("metric") != "attack_side_share" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    side = (claim.get("params") or {}).get("side")
    f = bait_switch.detect(ctx.scope.events, ctx.team_id, ctx.ds.passes, ctx.ds.shots)
    on_side = f is not None and ((side == "left") == (f.values["build_left"] * 2 >= f.values["amount"]))
    fired = bool(on_side and f.values["shots"] and f.values["finish_side_share"] > MIN_FAR_SHARE)
    detail = dict(switches=f.values["amount"] if f else 0, finish_side_share=f.values["finish_side_share"] if f else None)
    return RuleResult(RULE_ID, fired, "context", "attack_side.built_one_side_finished_other" if fired else None, detail)
