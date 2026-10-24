"""ctx_tilt_without_access: territorial dominance read as control while the opponent held a low
block that let it have the ball outside the box (pattern pat_elastic_low_block).

Applies to: metric field_tilt, subject a team (the side with the territory), scope match or
window. Stands down when field_tilt_with_lead fires on the same claim (that rule already gives the
caveat, with its own wording).
Fires when the low-block detector finds a spell of the OPPONENT inside the claim's window
(overlapping it by >= MIN_OVERLAP_SEC). Any overlap counts: a 600-second floor let a 463-second
overlap through unqualified (tests/test_pattern_claims.py, after the Tier 2 plants changed the data).
Action: context. REQUIRES team_shots, outside_shot_share and team_xg_per_shot.
"""
from engine.patterns import elastic_low_block

from . import RuleResult, field_tilt_with_lead

RULE_ID = "ctx_tilt_without_access"
MIN_OVERLAP_SEC = 1
REQUIRES = ("team_shots", "outside_shot_share", "team_xg_per_shot")


def check(claim, ctx):
    if claim.get("metric") != "field_tilt" or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    lead = field_tilt_with_lead.check(claim, ctx)
    if lead is not None and lead.fired:
        return RuleResult(RULE_ID, False, "context", None, {"stood_down_for": "field_tilt_with_lead"})
    mid = ctx.scope.match_id
    m = ctx.ds.matches[mid]
    opp = m["away_team_id"] if ctx.team_id == m["home_team_id"] else m["home_team_id"]
    w = ctx.scope.window
    f = elastic_low_block.detect(ctx.ds, mid, opp, upto=w[1] if w else None)
    spells = (f.detail["spells"] if f else [])
    overlap = max((min(b, w[1]) - max(a, w[0]) for a, b in spells), default=0) if w else (MIN_OVERLAP_SEC if f else 0)
    fired = overlap >= MIN_OVERLAP_SEC
    return RuleResult(RULE_ID, fired, "context", "field_tilt.low_block_outside_box" if fired else None,
                      dict(spells=spells, overlap_sec=overlap))
