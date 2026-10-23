"""ctx_dominance_with_transition_exposure: a dominance claim for a side that conceded shots on the
counter while it held the territory (pattern pat_rest_defence). Numbers only; never "reckless".

Applies to: metric field_tilt, subject a team, scope match or window. Stands down when
field_tilt_with_lead fires on the same claim.
Fires when the rest-defence detector finds the pattern for the subject inside the claim's scope.
Action: context. REQUIRES counter_shots_conceded and counter_xg_conceded.
"""
from engine.patterns import rest_defence

from . import RuleResult, field_tilt_with_lead

RULE_ID = "ctx_dominance_with_transition_exposure"
REQUIRES = ("counter_shots_conceded", "counter_xg_conceded")


def check(claim, ctx):
    if claim.get("metric") != "field_tilt" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    lead = field_tilt_with_lead.check(claim, ctx)
    if lead is not None and lead.fired:
        return RuleResult(RULE_ID, False, "context", None, {"stood_down_for": "field_tilt_with_lead"})
    f = rest_defence.detect(ctx.ds, ctx.scope.events, ctx.team_id)
    fired = f is not None and f.window is None          # the pattern over the claim's own scope
    return RuleResult(RULE_ID, fired, "context", "field_tilt.counters_conceded" if fired else None,
                      dict(f.values) if f else {})
