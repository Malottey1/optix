"""Test helper (reads ground truth, so it lives with the tests, never in engine/): the planted cases
the match-level Verifier rules are scored on, and whether each one is detectable at all.

A (match, team) case is PLANTED when its trap is in the ground truth and the trap had time to act:
  * shot_spam: the subject is a planted shot-spam team and trailed for >= TRAILING_SEC (the trap
    only acts while trailing a side that sits deep);
  * field_tilt_with_lead: the opponent is a planted sit-deep team and the subject trailed for
    >= TRAILING_SEC.
A planted spam (or sit-deep) team's match that did not trail that long is left out of every count.
Every other (match, team) pair is a NON-TRAP case.

A planted case is a TRUE CASE for recall only if the trap left a detectable trace in the events
while the subject was trailing (the "trailing spell"). Otherwise it is BELOW DETECTION and a miss
is acceptable:
  * shot_spam: fewer than MIN_SPELL_SHOTS non-penalty shots while trailing (the rule needs a
    dozen shots before a share of low-quality shots means anything), or a low-xG share while
    trailing no higher than the league's trailing share (the trap did not show in this match);
  * field_tilt_with_lead: fewer than MIN_SPELL_F3 completed final-third passes while trailing, or
    a field tilt while trailing below MIN_SPELL_TILT (the trailing side never held the territory
    the claim would describe).
Recall is reported both ways: over true cases (pinned by the tests) and over all planted cases.
"""
from engine import metrics as M
from engine.rules import shot_spam
from engine.tables import match_events, score_diff

TRAILING_SEC = 2700
MIN_SPELL_SHOTS = shot_spam.MIN_SHOTS
MIN_SPELL_F3 = 30
MIN_SPELL_TILT = 0.60
RULE_TRAP = {"shot_spam": ("xg", "shot_spam", "subject"),
             "field_tilt_with_lead": ("field_tilt", "sit_deep_when_leading", "opponent")}


def trailing_sec(evs, tid):
    total, prev = 0, None
    for e in evs:
        if prev is not None and score_diff(prev, tid) < 0:
            total += e["clock_sec"] - prev["clock_sec"]
        prev = e
    return total


def spell(ds, evs, tid) -> dict:
    """What the subject did while trailing (events in its attacking frame)."""
    tr = [e for e in evs if score_diff(e, tid) < 0]
    xg = [ds.shots[e["event_id"]]["xg"] for e in tr if e["event_type"] == "shot" and e["team_id"] == tid
          and ds.shots[e["event_id"]]["shot_type"] != "penalty"]
    f3 = [e for e in tr if e["event_type"] == "pass" and e["outcome"] == "success" and e["x_start"] >= M.FINAL_THIRD_X]
    own = sum(1 for e in f3 if e["team_id"] == tid)
    return dict(shots=len(xg), low_xg_shots=sum(1 for x in xg if x <= shot_spam.LOW_XG), xg=sum(xg),
                f3_passes=own, field_tilt=own / len(f3) if f3 else 0.0,
                box_entries=M.box_entries(tr, tid).value)


def league_trailing_low_share(ds) -> float:
    n = low = 0
    for e in ds.events:
        if e["event_type"] == "shot" and score_diff(e, e["team_id"]) < 0:
            s = ds.shots[e["event_id"]]
            if s["shot_type"] != "penalty":
                n += 1
                low += s["xg"] <= shot_spam.LOW_XG
    return low / n if n else 0.0


def below_detection(rule, sp, league_low) -> str | None:
    """Why a planted case is below detection, or None if it is a true case."""
    if rule == "shot_spam":
        if sp["shots"] < MIN_SPELL_SHOTS:
            return f"fewer than {MIN_SPELL_SHOTS} non-penalty shots while trailing"
        if sp["low_xg_shots"] / sp["shots"] <= league_low:
            return "low-xG share while trailing not above the league's"
        return None
    if sp["f3_passes"] < MIN_SPELL_F3:
        return f"fewer than {MIN_SPELL_F3} final-third passes while trailing"
    if sp["field_tilt"] < MIN_SPELL_TILT:
        return f"field tilt while trailing below {MIN_SPELL_TILT:.0%}"
    return None


def cases(ds, gt):
    """Every (rule, match, team) case: dict(rule, metric, match_id, team_id, planted, reason, spell).
    planted is None for a planted team's match that is left out (did not trail long enough)."""
    code = {t["team_id"]: t["code"] for t in ds.teams.values()}
    traps = {c: {x["trap"] for x in v} for c, v in gt["team_traps"].items()}
    league_low = league_trailing_low_share(ds)
    out = []
    for mid, evs in match_events(ds).items():
        m = ds.matches[mid]
        for tid, opp in ((m["home_team_id"], m["away_team_id"]), (m["away_team_id"], m["home_team_id"])):
            trailed = trailing_sec(evs, tid) >= TRAILING_SEC
            for rule, (metric, trap, who) in RULE_TRAP.items():
                owner = tid if who == "subject" else opp
                planted = trap in traps.get(code[owner], ())
                if planted and not trailed:
                    planted = None
                sp = spell(ds, evs, tid) if planted else None
                out.append(dict(rule=rule, metric=metric, match_id=mid, team_id=tid, planted=planted, spell=sp,
                                reason=below_detection(rule, sp, league_low) if planted else None))
    return out


def drop_match_caches(league):
    """The stream builds a new dataset view per event, and the engine's per-dataset caches would
    keep every view of every match alive across a league. Keep only the league's entries."""
    from engine import claims as C
    from engine import metrics as Mx
    from engine import tables as T
    from engine import verifier as V
    C._SUBSETS.clear()
    for cache in (T._INDEX, V._EV, Mx._THREAT):
        for k in [k for k, v in cache.items() if v[0] is not league]:
            del cache[k]


def pipeline_claims(ds, match_id) -> dict:
    """Stream one match of `ds` through the agents (agents/orchestrator.py, league baselines from
    ds) and return {(team_id, metric): [dict(window, rules)]} for its xg and field_tilt claims, one
    entry per attempt-1 window in proposal order; rules = every rule fired on any attempt."""
    from agents.orchestrator import Orchestrator
    from engine import claims as C
    orc = Orchestrator(C._subset(ds, match_id), match_id)
    seen = {}
    check = orc.verifier.check

    def spy(p, state):
        r = check(p, state)
        c = p.claim
        if c["metric"] in ("xg", "field_tilt"):
            w = (c["window"]["from_sec"], c["window"]["to_sec"])
            lst = seen.setdefault((c["subject"]["id"], c["metric"]), [])
            if c["verification"]["attempt"] == 1:
                lst.append(dict(window=w, rules=set()))
            next(x for x in lst if x["window"] == w)["rules"].update(r.verdict.rule_ids)
        return r
    orc.verifier.check = spy
    orc.run()
    return seen
