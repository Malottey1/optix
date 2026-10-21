"""ppda_alone: a pressing claim backed only by PPDA.

On this event data PPDA (and ball-won height) can rank a non-pressing team level with a pressing
one: CAL, the planted high-press team, has PPDA 5.68 against VES's 5.57 (docs/engine.md, "Pressing:
why ball-won height and PPDA mislead for CAL"). Pressure events per opponent pass separate them.
Applies to: metric ppda. Fires unless the claim's params carry press_intensity (so the sentence
shows it beside PPDA). Action: context. REQUIRES press_intensity, which by definition a fired
claim lacks: a PPDA-only claim is blocked until the Analyst adds press intensity.
"""
from . import RuleResult

RULE_ID = "ppda_alone"
REQUIRES = ("press_intensity",)


def check(claim, ctx):
    if claim.get("metric") != "ppda":
        return None
    fired = "press_intensity" not in (claim.get("params") or {})
    return RuleResult(RULE_ID, fired, "context", "ppda.read_with_press_intensity" if fired else None, {})
