"""causal_red_card: block claims that a red card caused an outcome.

Applies to: metric red_card_segment_delta, or any claim whose template_key/params mention a red
card. Fires when the claim is causal (claim_type "causal", or a template_key containing "caused"
or "because"). Descriptive per-segment rates ("shots per 10 minutes before and after the card")
pass. Action: block.
"""
from . import RuleResult

RULE_ID = "causal_red_card"
CAUSAL_WORDS = ("caused", "because", "due_to", "cost")


def check(claim, ctx):
    key = (claim.get("template_key") or "").lower()
    mentions = claim.get("metric") == "red_card_segment_delta" or "red_card" in key or any(
        "red_card" in str(k).lower() for k in (claim.get("params") or {}))
    if not mentions:
        return None
    causal = claim.get("claim_type") == "causal" or any(w in key for w in CAUSAL_WORDS)
    return RuleResult(RULE_ID, causal, "block", "red_card.descriptive_only" if causal else None, {})
