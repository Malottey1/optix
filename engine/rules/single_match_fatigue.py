"""single_match_fatigue: block fatigue diagnoses drawn from one match.

There is no tracking data (distance, speed), so fatigue can only be inferred from event proxies,
and one match is far too small a sample to separate tiredness from game state or tactics.
Applies to: claims whose template_key starts with "fatigue." or whose params name a "fatigue"
diagnosis. Fires when scope is "match" or "window". Action: block.
"""
from . import RuleResult

RULE_ID = "single_match_fatigue"


def check(claim, ctx):
    key = claim.get("template_key") or ""
    params = claim.get("params") or {}
    if not (key.startswith("fatigue.") or params.get("diagnosis") == "fatigue"):
        return None
    fired = claim.get("scope") in ("match", "window")
    return RuleResult(RULE_ID, fired, "block", "fatigue.single_match_not_supported" if fired else None, {})
