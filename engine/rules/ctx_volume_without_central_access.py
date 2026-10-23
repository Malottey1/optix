"""ctx_volume_without_central_access: final-third volume read as pressure when much of it was
played along one touchline (pattern pat_flank_isolation).

Applies to: metric final_third_passes, subject a team, scope match or window.
Fires when the flank-isolation detector finds >= 1 spell and the spells hold >= MIN_SHARE % of
the team's final-third passes.
Action: context. REQUIRES isolation_spells, isolation_share and box_entries.
"""
from engine.patterns import flank_isolation

from . import RuleResult

RULE_ID = "ctx_volume_without_central_access"
MIN_SHARE = 10.0
REQUIRES = ("isolation_spells", "isolation_share", "box_entries")


def check(claim, ctx):
    if claim.get("metric") != "final_third_passes" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = flank_isolation.detect(ctx.scope.events, ctx.team_id, ctx.ds.passes, ctx.ds.shots)
    fired = bool(f and f.values["f3_share"] >= MIN_SHARE)
    return RuleResult(RULE_ID, fired, "context", "f3_volume.touchline_spells" if fired else None,
                      dict(f.values) if f else {})
