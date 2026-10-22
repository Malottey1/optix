"""field_tilt_with_lead: high territory while trailing a team that sits deep.

A trailing side often holds most of the final third because the leader has dropped into a deep
block, not because it is on top: it circulates around the box without getting in.
Applies to: metric field_tilt or territorial_stress, subject a team, scope match or window.
Fires when, over the claim's scope:
  * the subject's field tilt is >= MIN_TILT,
  * it was trailing for at least MIN_TRAILING_SHARE of its final-third passes, and
  * while it was trailing, its box entries were <= MAX_ENTRY_SHARE of its final-third passes, and
  * it did not clearly out-create an average chaser: its non-penalty xG from real chances (shots
    above shot_spam.LOW_XG) in scope, against what an average side makes from such chances in
    the same time in the same game states (metrics.chaser_threat), is at or below the league's
    THREAT_PCTL quantile of that ratio over scopes of the same length in which the subject
    trailed for at least half the time (metrics.chaser_threat_line).
The entry share is taken over the trailing part of the scope only: the deep block acts only
while the subject trails, so box entries from level spells (often early in the match) would
otherwise dilute the pattern in a full-match claim.
The caveat says "territory, not threat"; a chaser that made clearly more from real chances than
an average chaser was a threat, so the caveat would mislead the other way. Speculative shots are
left out of the threat measure on purpose: twenty 0.05 shots add up to 1.0 xG without making a
side dangerous, and a chaser circulating around a deep block shoots from range (the shot_spam
pattern). With no league line (under 20 reference scopes) this condition is skipped.
A dominant side (level or ahead, getting into the box while trailing, or creating clearly more
than an average chaser) does not fire.
Action: context. REQUIRES box_entries in params (the sentence must say how few got into the box).
"""
from engine import metrics as M
from engine.tables import baseline_of, score_diff

from . import RuleResult
from .shot_spam import LOW_XG

RULE_ID = "field_tilt_with_lead"
MIN_TILT = 0.60
MIN_TRAILING_SHARE = 0.5
MAX_ENTRY_SHARE = 0.18
THREAT_PCTL = 0.75
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
    trailing_box = M.box_entries([e for e in ev if score_diff(e, tid) < 0], tid).value
    n = len(f3)
    detail = dict(field_tilt=tilt.value, f3_passes=n, trailing_share=trailing / n if n else 0.0,
                  box_entries=box, box_entry_share=box / n if n else 0.0, trailing_f3_passes=trailing,
                  trailing_box_entries=trailing_box,
                  trailing_box_entry_share=trailing_box / trailing if trailing else 0.0)
    league = baseline_of(ctx.ds)
    threat = M.chaser_threat(ev, ctx.ds.shots, tid, M.state_npxg_rates(league, LOW_XG), LOW_XG)
    w = ctx.scope.window
    line = M.chaser_threat_line(league, None if w is None else w[1] - w[0], THREAT_PCTL, LOW_XG)
    detail.update(chance_npxg=threat.detail["npxg"], expected_chance_npxg=threat.detail["expected"],
                  threat_ratio=threat.value, threat_line=line)
    quiet = line is None or threat.value is None or threat.value <= line
    fired = bool(n and (tilt.value or 0) >= MIN_TILT and detail["trailing_share"] >= MIN_TRAILING_SHARE
                 and detail["trailing_box_entry_share"] <= MAX_ENTRY_SHARE and quiet)
    return RuleResult(RULE_ID, fired, "context", "field_tilt.trailing_vs_deep_block" if fired else None, detail)
