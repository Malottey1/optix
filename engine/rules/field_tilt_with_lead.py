"""field_tilt_with_lead: high territory while trailing a team that sits deep.

A trailing side often holds most of the final third because the leader has dropped into a deep
block, not because it is on top: it circulates around the box without getting in.
Applies to: metric field_tilt or territorial_stress, subject a team, scope match or window.
Fires when, over the claim's scope:
  * the subject's field tilt is >= MIN_TILT,
  * it was trailing for at least MIN_TRAILING_SHARE of its final-third passes, and
  * its box entries are <= MAX_ENTRY_SHARE of its final-third passes.
A dominant side (level or ahead, or getting into the box) does not fire.
Action: context. REQUIRES box_entries in params (the sentence must say how few got into the box).
"""
from engine import metrics as M
from engine.tables import score_diff

from . import RuleResult

RULE_ID = "field_tilt_with_lead"
MIN_TILT = 0.60
MIN_TRAILING_SHARE = 0.5
MAX_ENTRY_SHARE = 0.15
REQUIRES = ("box_entries",)


def check(claim, ctx):
    if claim.get("metric") not in ("field_tilt", "territorial_stress") or claim["subject"]["kind"] != "team":
        return None
    if claim.get("scope") == "season":
        return None
    tid = ctx.team_id
    ev = ctx.scope.events
    tilt = M.field_tilt(ev, tid)
    f3 = [e for e in ev if e["event_type"] == "pass" and e["outcome"] == "success" and e["team_id"] == tid
          and e["x_start"] >= M.FINAL_THIRD_X]
    trailing = sum(1 for e in f3 if score_diff(e, tid) < 0)
    box = M.box_entries(ev, tid).value
    n = len(f3)
    detail = dict(field_tilt=tilt.value, f3_passes=n, trailing_share=trailing / n if n else 0.0,
                  box_entries=box, box_entry_share=box / n if n else 0.0)
    fired = bool(n and (tilt.value or 0) >= MIN_TILT and detail["trailing_share"] >= MIN_TRAILING_SHARE
                 and detail["box_entry_share"] <= MAX_ENTRY_SHARE)
    return RuleResult(RULE_ID, fired, "context", "field_tilt.trailing_vs_deep_block" if fired else None, detail)
