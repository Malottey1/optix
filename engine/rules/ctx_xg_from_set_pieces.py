"""ctx_xg_from_set_pieces: a team's xG total when most of its non-penalty xG came from set pieces
(pattern pat_set_piece_dependence): the total alone reads as open-play threat.

Applies to: metric xg or npxg, subject a team, scope match or window.
Fires when the set-piece dependence detector finds the pattern for the team in scope.
Action: context. REQUIRES set_piece_xg and set_piece_xg_share.
"""
from engine.patterns import set_piece_dependence

from . import RuleResult

RULE_ID = "ctx_xg_from_set_pieces"
REQUIRES = ("set_piece_xg", "set_piece_xg_share")


def check(claim, ctx):
    if claim.get("metric") not in ("xg", "npxg") or claim["subject"]["kind"] != "team" or claim["scope"] == "season":
        return None
    f = set_piece_dependence.detect(ctx.ds, ctx.scope.events, ctx.team_id)
    return RuleResult(RULE_ID, f is not None, "context", "xg.mostly_set_pieces" if f else None,
                      dict(f.values) if f else {})
