"""causal_claim: block every causal claim.

Event data shows what happened, not why. A claim of type "causal" ("X caused Y") is always blocked;
the descriptive version ("possession fell from 54% to 38% after X") is a different claim type
(descriptive_change) and is allowed. Applies to: claim_type == "causal". Action: block.
"""
from . import RuleResult

RULE_ID = "causal_claim"


def check(claim, ctx):
    if claim.get("claim_type") != "causal":
        return None
    return RuleResult(RULE_ID, True, "block", "causal.not_supported_by_event_data", {})
