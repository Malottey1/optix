"""shot_spam: a big shot count or xG total built from many low-quality shots.

Applies to: metric xg or npxg, subject a team. Fires when the subject has at least MIN_SHOTS
non-penalty shots in scope, at least MIN_LOW_SHARE of them have xG <= LOW_XG, and their mean xG is
<= MAX_MEAN_XG. Penalties are left out of all three: a penalty's xG is fixed (about 0.78) and says
nothing about shot selection, so one penalty would lift the mean of a dozen speculative shots over
the cap and hide the pattern.
Action: context. REQUIRES shots and xg_per_shot in params.
"""
from . import RuleResult

RULE_ID = "shot_spam"
MIN_SHOTS = 12
LOW_XG = 0.08
MIN_LOW_SHARE = 0.65
MAX_MEAN_XG = 0.08
REQUIRES = ("shots", "xg_per_shot")


def check(claim, ctx):
    if claim.get("metric") not in ("xg", "npxg") or claim["subject"]["kind"] != "team":
        return None
    tid = ctx.team_id
    shots = ctx.ds.shots
    xg = [shots[e["event_id"]]["xg"] for e in ctx.scope.events
          if e["event_type"] == "shot" and e["team_id"] == tid and shots[e["event_id"]]["shot_type"] != "penalty"]
    n = len(xg)
    low_share = sum(1 for x in xg if x <= LOW_XG) / n if n else 0.0
    mean = sum(xg) / n if n else 0.0
    fired = n >= MIN_SHOTS and low_share >= MIN_LOW_SHARE and mean <= MAX_MEAN_XG
    return RuleResult(RULE_ID, fired, "context", "xg.volume_of_low_quality_shots" if fired else None,
                      dict(shots=ctx.values["shots"], non_penalty_shots=n, low_share=low_share,
                           non_penalty_xg_per_shot=mean, xg_per_shot=ctx.values["xg_per_shot"]))
