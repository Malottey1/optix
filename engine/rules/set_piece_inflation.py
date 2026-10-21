"""set_piece_inflation: chances created that mostly come from dead balls.

A set-piece taker racks up key passes from corners without open-play creativity.
Applies to: metric chances_created. Fires when at least MIN_CHANCES chances are in scope and the
set-piece share is >= MIN_SET_PIECE_SHARE. Action: context.
REQUIRES open_play in params (open-play chances beside the total).
"""
from . import RuleResult

RULE_ID = "set_piece_inflation"
MIN_CHANCES = 4
MIN_SET_PIECE_SHARE = 0.5
REQUIRES = ("open_play",)


def check(claim, ctx):
    if claim.get("metric") != "chances_created":
        return None
    v = ctx.values
    n = v["amount"]
    share = v["set_piece"] / n if n else 0.0
    fired = n >= MIN_CHANCES and share >= MIN_SET_PIECE_SHARE
    return RuleResult(RULE_ID, fired, "context", "chances_created.mostly_set_pieces" if fired else None,
                      dict(chances=n, set_piece_share=share))
