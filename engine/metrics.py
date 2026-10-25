"""Deterministic event metrics. Pure functions over loaded tables (see engine/tables.py).

Every function returns a `MetricResult`: the value AND the evidence event IDs behind it, plus the
sample size. The Verifier's context rules refer to the "Known limits" in each docstring.

Common arguments
    events   list of event rows (any number of matches; both teams' events)
    passes   event_id -> pass row          shots   event_id -> shot row
    team_id  the team the metric is about; None means every team (league aggregate)
    window   optional (from_sec, to_sec), inclusive, match clock in seconds
    state    optional game state of `team_id` at the event: "leading" / "level" / "trailing" or a
             contract bracket ("leading_1", "leading_2plus", "trailing_1", "trailing_2plus")

All coordinates are in the acting team's attacking frame (see engine/zones.py).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .tables import BRACKETS3, bracket3, bracket5, match_events, score_diff
from .zones import FINAL_THIRD_X, LANES, WIDE_LANES, in_box, lane_of

FORWARD_GAIN = 8.0          # data dictionary: a pass is forward if it gains >= 8 x units
XG_BANDS = ((0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 1.01))
BALL_WINNING = ("tackle", "interception")
PPDA_ACTIONS = ("tackle", "interception", "foul")      # the standard PPDA defensive actions


@dataclass(frozen=True)
class MetricResult:
    value: object                       # number, or dict for split metrics
    evidence_event_ids: tuple = ()
    sample_size: int = 0
    sd: float | None = None             # per-observation standard deviation, for mean metrics
    detail: dict = field(default_factory=dict)


# ---------- selection helpers ----------

def _state_ok(e, team_id, state) -> bool:
    if state is None:
        return True
    diff = score_diff(e, team_id)
    return (bracket3(diff) if state in BRACKETS3 else bracket5(diff)) == state


def _in_scope(e, team_id, window, state, state_team=None) -> bool:
    if window is not None and not (window[0] <= e["clock_sec"] <= window[1]):
        return False
    st = state_team or team_id
    if state is not None and st is None:
        raise ValueError("a game-state filter needs a team")
    return _state_ok(e, st, state)


def _acting(events, team_id, window=None, state=None, etype=None):
    """Events performed by `team_id` (or anyone if None) in scope."""
    for e in events:
        if etype is not None and e["event_type"] != etype:
            continue
        if team_id is not None and e["team_id"] != team_id:
            continue
        if _in_scope(e, e["team_id"] if team_id is None else team_id, window, state):
            yield e


def _completed_passes(events, team_id, window=None, state=None):
    return (e for e in _acting(events, team_id, window, state, "pass") if e["outcome"] == "success")


def _is_entry(e) -> bool:
    return e["x_start"] < FINAL_THIRD_X <= e["x_end"]


def _mean_sd(xs):
    n = len(xs)
    if n == 0:
        return None, None
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
    return m, sd


# ---------- territory ----------

def final_third_passes(events, team_id, window=None, state=None) -> MetricResult:
    """Completed passes that START in the final third (x >= 66.7).

    Inputs: events; team_id; optional window and game state.
    Value: count. Evidence: the passes.
    Known limits: counts circulation, not threat; a team pinned outside a deep block piles these
    up without getting closer to goal (pair with box_entries). Carries are not in the data.
    """
    ids = [e["event_id"] for e in _completed_passes(events, team_id, window, state)
           if e["x_start"] >= FINAL_THIRD_X]
    return MetricResult(len(ids), tuple(ids), len(ids))


def final_third_entries(events, team_id, window=None, state=None, conceded=False) -> MetricResult:
    """Completed passes that start outside and end inside the final third, split by end lane.

    Inputs: events; team_id; optional window and game state; conceded=True counts entries made
    BY OPPONENTS of team_id (game state still from team_id's point of view).
    Value: total entries. detail["lanes"]: lane -> count; detail["lane_ids"]: lane -> event IDs.
    Lanes are from the attacker's point of view, also for conceded entries.
    Known limits: pass entries only (no carries); a lane share describes where a side goes, not
    how dangerous it is; conceded shares mix every opponent's own lane preferences.
    """
    lanes = {l: [] for l in LANES}
    for e in events:
        if e["event_type"] != "pass" or e["outcome"] != "success" or not _is_entry(e):
            continue
        if conceded:
            if e["opponent_team_id"] != team_id or not _in_scope(e, team_id, window, state):
                continue
        else:
            if team_id is not None and e["team_id"] != team_id:
                continue
            if not _in_scope(e, e["team_id"] if team_id is None else team_id, window, state):
                continue
        lanes[lane_of(e["y_end"])].append(e["event_id"])
    ids = [i for l in LANES for i in lanes[l]]
    return MetricResult(len(ids), tuple(ids), len(ids),
                        detail=dict(lanes={l: len(v) for l, v in lanes.items()}, lane_ids=lanes))


def box_entries(events, team_id, window=None, state=None) -> MetricResult:
    """Completed passes from outside the box that end inside it (x >= 84, 22 <= y <= 78).

    Inputs: events; team_id; optional window and game state.
    Value: count. Evidence: the passes.
    Known limits: pass entries only (dribbles into the box are not logged); a cross that is
    completed counts the same as a cut-back.
    """
    ids = [e["event_id"] for e in _completed_passes(events, team_id, window, state)
           if in_box(e["x_end"], e["y_end"]) and not in_box(e["x_start"], e["y_start"])]
    return MetricResult(len(ids), tuple(ids), len(ids))


def field_tilt(events, team_id, window=None, state=None) -> MetricResult:
    """Share of all final-third passes in the team's matches that belong to the team.

    Definition: team final_third_passes / (team + opponents' final_third_passes), over events in
    scope; the game-state filter uses team_id's state for both sides.
    Inputs: events; team_id; optional window and game state.
    Value: ratio 0-1. Evidence: the team's final-third passes. detail: both counts.
    Known limits: says who holds territory, not who threatens. A side trailing a team that sits
    deep shows high tilt with few box entries (rule field_tilt_with_lead). Small windows give
    noisy ratios; check sample_size.
    """
    if team_id is None:
        raise ValueError("field tilt needs a team (league-wide tilt is 0.5 by construction)")
    own = final_third_passes(events, team_id, window, state)
    opp_ids = [e["event_id"] for e in events
               if e["event_type"] == "pass" and e["outcome"] == "success"
               and e["opponent_team_id"] == team_id and e["x_start"] >= FINAL_THIRD_X
               and _in_scope(e, team_id, window, state)]
    total = own.value + len(opp_ids)
    return MetricResult(own.value / total if total else None, own.evidence_event_ids, total,
                        detail=dict(team_f3_passes=own.value, opponent_f3_passes=len(opp_ids)))


# ---------- shooting ----------

def _team_shots(events, shots, team_id, window, state):
    return [(e, shots[e["event_id"]]) for e in _acting(events, team_id, window, state, "shot")]


def xg_sum(events, shots, team_id, window=None, state=None) -> MetricResult:
    """Sum of shot xG.

    Inputs: events; shots table; team_id; optional window and game state.
    Value: xG sum. Evidence: the shots. detail: shots and mean xG per shot.
    Known limits: the xG model is the data's own (distance, angle, header, set piece). Many
    low-quality shots can add up to a big total (rule shot_spam); a single match is a small
    sample (rule small_sample_xg).
    """
    rows = _team_shots(events, shots, team_id, window, state)
    total = sum(s["xg"] for _, s in rows)
    return MetricResult(total, tuple(e["event_id"] for e, _ in rows), len(rows),
                        detail=dict(shots=len(rows), xg_per_shot=total / len(rows) if rows else None))


def npxg_sum(events, shots, team_id, window=None, state=None) -> MetricResult:
    """Non-penalty xG: xg_sum excluding shots with shot_type == "penalty".

    Known limits: as xg_sum. Set-piece shots (corners, direct free kicks) are included, as in the
    standard definition.
    """
    rows = [(e, s) for e, s in _team_shots(events, shots, team_id, window, state)
            if s["shot_type"] != "penalty"]
    total = sum(s["xg"] for _, s in rows)
    return MetricResult(total, tuple(e["event_id"] for e, _ in rows), len(rows),
                        detail=dict(shots=len(rows), xg_per_shot=total / len(rows) if rows else None))


_THREAT: dict = {}


def state_npxg_rates(ds, min_xg: float = 0.0) -> dict:
    """League non-penalty xG per team-second in each game state, from shots with xG > min_xg.

    Definition: for every match and both teams, the seconds between consecutive events are booked
    to the team's state at the earlier event (bracket3: leading / level / trailing); every
    non-penalty shot's xG (above min_xg) to the shooter's state. rate = npxG / team-seconds.
    Inputs: a dataset (the league baseline); min_xg (0 = every shot). Value: {state: rate}.
    Cached per (dataset, min_xg).
    Known limits: one league rate per state; a strong side chasing a weak one is expected to make
    no more than an average chaser.
    """
    key = (id(ds), "rates", min_xg)
    if key not in _THREAT:
        xg, sec = defaultdict(float), defaultdict(float)
        for mid, evs in match_events(ds).items():
            for tid in (ds.matches[mid]["home_team_id"], ds.matches[mid]["away_team_id"]):
                for prev, e in zip(evs, evs[1:]):
                    sec[bracket3(score_diff(prev, tid))] += e["clock_sec"] - prev["clock_sec"]
                for e in evs:
                    s = ds.shots.get(e["event_id"]) if e["event_type"] == "shot" and e["team_id"] == tid else None
                    if s and s["shot_type"] != "penalty" and s["xg"] > min_xg:
                        xg[bracket3(score_diff(e, tid))] += s["xg"]
        _THREAT[key] = (ds, {k: xg[k] / sec[k] for k in sec if sec[k]})
    return _THREAT[key][1]


def chaser_threat(events, shots, team_id, rates, min_xg: float = 0.0) -> MetricResult:
    """The team's non-penalty xG in scope (shots with xG > min_xg) against what an average side
    would make in the same time in the same game states.

    Definition: ratio = npxG / expected, expected = sum over consecutive events in scope of
    (seconds to the next event) x rates[team's state at the earlier event] (state_npxg_rates).
    Inputs: events in scope (in order); shots table; team_id; the league rates (built with the
    same min_xg); min_xg. Value: ratio (None if expected is 0). detail: npxg, expected, seconds,
    trailing_seconds.
    Known limits: xG is the only threat measure; a ratio over a short scope is noisy. With
    min_xg 0 a pile of speculative shots counts as threat (twenty 0.05 shots make 1.0 xG); a
    min_xg at the low-xG line counts only real chances.
    """
    npxg = expected = sec = trailing = 0.0
    for prev, e in zip(events, events[1:]):
        dt = e["clock_sec"] - prev["clock_sec"]
        st = bracket3(score_diff(prev, team_id))
        expected += rates.get(st, 0.0) * dt
        sec += dt
        trailing += dt if st == "trailing" else 0
    ids = []
    for e in events:
        if (e["event_type"] == "shot" and e["team_id"] == team_id and shots[e["event_id"]]["shot_type"] != "penalty"
                and shots[e["event_id"]]["xg"] > min_xg):
            npxg += shots[e["event_id"]]["xg"]
            ids.append(e["event_id"])
    return MetricResult(npxg / expected if expected else None, tuple(ids), len(ids),
                        detail=dict(npxg=npxg, expected=expected, seconds=sec, trailing_seconds=trailing))


def chaser_threat_line(ds, length_sec: int | None, pctl: float = 0.75, min_xg: float = 0.0,
                       step_sec: int = 900) -> float | None:
    """The pctl quantile of chaser_threat over league scopes of the same kind in which the subject
    trailed for at least half the time: full matches (length_sec None), or windows of length_sec
    ending every step_sec and at full time.

    Inputs: the league dataset; scope length; quantile; min_xg as in chaser_threat. Value: the
    ratio at that quantile, or None when fewer than 20 such scopes exist. Cached per argument set.
    Known limits: the reference pools every team; game state is matched only through the rates.
    """
    key = (id(ds), "line", length_sec, pctl, min_xg)
    if key not in _THREAT:
        rates = state_npxg_rates(ds, min_xg)
        ratios = []
        for mid, evs in match_events(ds).items():
            end = evs[-1]["clock_sec"]
            spans = [(0, end)] if length_sec is None else \
                [(t - length_sec, t) for t in list(range(length_sec, end, step_sec)) + [end] if t >= length_sec]
            for tid in (ds.matches[mid]["home_team_id"], ds.matches[mid]["away_team_id"]):
                for a, b in spans:
                    r = chaser_threat([e for e in evs if a <= e["clock_sec"] <= b], ds.shots, tid, rates, min_xg)
                    d = r.detail
                    if r.value is not None and d["seconds"] and d["trailing_seconds"] >= 0.5 * d["seconds"]:
                        ratios.append(r.value)
        ratios.sort()
        _THREAT[key] = (ds, ratios[int(pctl * (len(ratios) - 1))] if len(ratios) >= 20 else None)
    return _THREAT[key][1]


def shots_by_xg_band(events, shots, team_id, window=None, state=None, bands=XG_BANDS) -> MetricResult:
    """Shot counts per xG band, lower bound inclusive: 0-0.05, 0.05-0.10, 0.10-0.20, 0.20-0.40, 0.40+.

    Inputs: events; shots table; team_id; optional window, game state and custom bands.
    Value: dict band label -> count. detail["band_ids"]: band label -> shot event IDs.
    Known limits: bands hide how close a shot was to an edge; use with xg_sum.
    """
    out = {}
    for lo, hi in bands:
        label = f"{lo:.2f}-{min(hi, 1.0):.2f}"
        out[label] = [e["event_id"] for e, s in _team_shots(events, shots, team_id, window, state)
                      if lo <= s["xg"] < hi]
    ids = [i for v in out.values() for i in v]
    return MetricResult({k: len(v) for k, v in out.items()}, tuple(ids), len(ids),
                        detail=dict(band_ids=out))


def goals(events, shots, player_id) -> MetricResult:
    """Goals scored by a player: their shots whose shots-table shot_result is "goal".

    Inputs: events (any scope, e.g. the season); shots table; player_id.
    Value: count. Evidence: the goal events.
    Known limits: the data has no own goals, so every goal belongs to the shooter; a count says
    nothing about chance quality (see xg_sum).
    """
    ids = tuple(e["event_id"] for e in events if e["event_type"] == "shot" and e["player_id"] == player_id
                and shots[e["event_id"]]["shot_result"] == "goal")
    return MetricResult(len(ids), ids, len(ids))


def assists(events, shots, player_id) -> MetricResult:
    """Assists by a player: goals whose shots-table assist_event_id is an event by that player
    (the pass or carry the data credits as the assist).

    Inputs: events (any scope); shots table; player_id.
    Value: count. Evidence: the assisting events.
    Known limits: only the data's own assist link counts (no second assists); an assist count
    depends on the finisher, see chances_created for the chances a player made.
    """
    by_id = {e["event_id"]: e for e in events}
    ids = tuple(s["assist_event_id"] for e in events if e["event_type"] == "shot"
                and (s := shots[e["event_id"]])["shot_result"] == "goal" and s["assist_event_id"]
                and by_id.get(s["assist_event_id"], {}).get("player_id") == player_id)
    return MetricResult(len(ids), ids, len(ids))


# ---------- passing ----------

def forward_passes_wide_share(events, team_id=None, player_id=None, window=None, state=None) -> MetricResult:
    """Completed forward passes (x gain >= 8) and the share of them that end in a wide lane.

    Inputs: events; team_id and/or player_id; optional window and game state.
    Value: count of completed forward passes. detail: wide_count, wide_share, wide_ids.
    Known limits: volume is not value: forward passes into the channel that never enter the box
    inflate the count (rule wide_forward_passes). Pass destination only, not receiver position.
    """
    fwd, wide = [], []
    for e in _completed_passes(events, team_id, window, state):
        if player_id is not None and e["player_id"] != player_id:
            continue
        if e["x_end"] - e["x_start"] >= FORWARD_GAIN:
            fwd.append(e["event_id"])
            if lane_of(e["y_end"]) in WIDE_LANES:
                wide.append(e["event_id"])
    return MetricResult(len(fwd), tuple(fwd), len(fwd),
                        detail=dict(wide_count=len(wide), wide_share=len(wide) / len(fwd) if fwd else None,
                                    wide_ids=tuple(wide)))


INVOLVEMENT_TYPES = ("pass", "carry", "dribble", "shot", "duel", "tackle", "interception", "clearance",
                     "block", "ball_recovery", "pressure", "foul", "save", "claim")


def involvement(events, player_id, team_id=None, window=None, state=None) -> MetricResult:
    """Actions credited to one player: every event of a type in INVOLVEMENT_TYPES (on-ball actions,
    duels, pressures, fouls, goalkeeper saves and claims) with the player as the actor.

    Inputs: events; player_id; optional team_id, window and game state.
    Value: count. detail: share of the team's actions of those types in the same scope (None if
    team_id is not given). Evidence: the events.
    Known limits: event data only, so it counts what the player did with or near the ball, not
    off-ball movement or distance covered. Minutes played are not in the data, so this is not
    per 90; a substitute's count is not comparable with a starter's.
    """
    mine, team_n = [], 0
    for e in _acting(events, team_id, window, state):
        if e["event_type"] not in INVOLVEMENT_TYPES:
            continue
        team_n += 1
        if e["player_id"] == player_id:
            mine.append(e["event_id"])
    return MetricResult(len(mine), tuple(mine), len(mine),
                        detail=dict(team_share=len(mine) / team_n if team_id is not None and team_n else None))


def pass_completion(events, player_id=None, team_id=None, window=None, state=None) -> MetricResult:
    """Share of attempted passes that were completed (outcome "success").

    Inputs: events; player_id and/or team_id; optional window and game state.
    Value: completed / attempted (None if no passes). detail: attempted, completed.
    Known limits: a safe sideways passer completes more than a creative one; pair with forward
    passes and pass_quality_ratio before reading it as quality.
    """
    att = [e for e in _acting(events, team_id, window, state, "pass") if player_id is None or e["player_id"] == player_id]
    done = [e["event_id"] for e in att if e["outcome"] == "success"]
    return MetricResult(len(done) / len(att) if att else None, tuple(done), len(att),
                        detail=dict(attempted=len(att), completed=len(done)))


def forward_passes_by_player(events, team_id=None, window=None, state=None) -> MetricResult:
    """Completed forward passes per player, highest first.

    Value: list of (player_id, count) sorted by count desc then id. Evidence: all counted passes.
    Known limits: as forward_passes_wide_share; minutes played are not in the data, so this is
    not per 90.
    """
    per = defaultdict(list)
    for e in _completed_passes(events, team_id, window, state):
        if e["x_end"] - e["x_start"] >= FORWARD_GAIN:
            per[e["player_id"]].append(e["event_id"])
    ranked = sorted(((p, len(v)) for p, v in per.items()), key=lambda t: (-t[1], t[0]))
    ids = [i for v in per.values() for i in v]
    return MetricResult(ranked, tuple(ids), len(ids))


def chances_created(events, passes, team_id=None, player_id=None, window=None, state=None) -> MetricResult:
    """Key passes (passes directly followed by a shot), split open play vs set piece.

    Definition: set piece = pass_type "corner" or event play_pattern "set_piece"; everything else
    is open play.
    Inputs: events; passes table; team_id and/or player_id; optional window and game state.
    Value: total key passes. detail: open_play, set_piece counts and their IDs.
    Known limits: a corner taker racks up chances without open-play creativity (rule
    set_piece_inflation); key passes ignore the quality of the resulting shot (see xa).
    """
    op, sp = [], []
    for e in _acting(events, team_id, window, state, "pass"):
        if player_id is not None and e["player_id"] != player_id:
            continue
        p = passes[e["event_id"]]
        if not p["is_key_pass"]:
            continue
        (sp if p["pass_type"] == "corner" or e["play_pattern"] == "set_piece" else op).append(e["event_id"])
    ids = op + sp
    return MetricResult(len(ids), tuple(ids), len(ids),
                        detail=dict(open_play=len(op), set_piece=len(sp),
                                    open_play_ids=tuple(op), set_piece_ids=tuple(sp)))


def chances_by_player(events, passes, team_id=None, window=None, state=None) -> MetricResult:
    """Key passes per player, highest first (same definition as chances_created).

    Value: list of (player_id, count) sorted by count desc then id. Evidence: all key passes.
    Known limits: as chances_created; open play and set pieces are counted together.
    """
    per = defaultdict(list)
    for e in _acting(events, team_id, window, state, "pass"):
        if passes[e["event_id"]]["is_key_pass"]:
            per[e["player_id"]].append(e["event_id"])
    ranked = sorted(((p, len(v)) for p, v in per.items()), key=lambda t: (-t[1], t[0]))
    ids = [i for v in per.values() for i in v]
    return MetricResult(ranked, tuple(ids), len(ids))


# ---------- defending / style ----------

def ball_won_height(events, team_id, window=None, state=None) -> MetricResult:
    """Mean x (0 own goal .. 100 opponent goal) where the team wins the ball by a won tackle or an
    interception (a lost tackle did not win it).

    Inputs: events; team_id (None = league); optional window and game state.
    Value: mean x. sd: per-event standard deviation. Evidence: the ball-winning events.
    Known limits: event-based proxy, not player positions. Loose-ball recoveries after shots and
    corners are excluded (they say where the ball dropped, not where it was won). It mostly
    reflects where the OPPONENT plays: a pinned-back side wins the ball low whatever it does, and
    on this data it does not single out the pressing team (use press_intensity for that).
    """
    rows = list(e for e in _acting(events, team_id, window, state) if e["event_type"] in BALL_WINNING
                and not (e["event_type"] == "tackle" and e["outcome"] != "success"))
    m, sd = _mean_sd([e["x_start"] for e in rows])
    return MetricResult(m, tuple(e["event_id"] for e in rows), len(rows), sd=sd)


def _sequences(events, team_id, window, state):
    """(match_id, sequence_id, team_id) -> chronological list of the team's pass events."""
    seqs = defaultdict(list)
    for e in _acting(events, team_id, window, state, "pass"):
        seqs[(e["match_id"], e["sequence_id"], e["team_id"])].append(e)
    return seqs


def tempo(events, team_id, window=None, state=None) -> MetricResult:
    """Mean seconds between consecutive passes by the same team in the same sequence.

    Inputs: events; team_id (None = league); optional window and game state.
    Value: seconds. sd: per-gap standard deviation. Evidence: the second pass of each gap.
    Known limits: clock is whole seconds; ignores time spent on dead balls and carries.
    """
    gaps, ids = [], []
    for evs in _sequences(events, team_id, window, state).values():
        for a, b in zip(evs, evs[1:]):
            gaps.append(b["clock_sec"] - a["clock_sec"])
            ids.append(b["event_id"])
    m, sd = _mean_sd(gaps)
    return MetricResult(m, tuple(ids), len(gaps), sd=sd)


def directness(events, team_id, window=None, state=None) -> MetricResult:
    """Share of attempted open-play passes that go forward (x gain >= 8). Corners excluded.

    Inputs: events; team_id (None = league); optional window and game state.
    Value: ratio 0-1. Evidence: the forward passes.
    Known limits: a team protecting a lead also clears long, which reads as direct.
    """
    n, fwd = 0, []
    for e in _acting(events, team_id, window, state, "pass"):
        if e["play_pattern"] == "set_piece":
            continue
        n += 1
        if e["x_end"] - e["x_start"] >= FORWARD_GAIN:
            fwd.append(e["event_id"])
    return MetricResult(len(fwd) / n if n else None, tuple(fwd), n)


def counter_share(events, team_id, window=None, state=None) -> MetricResult:
    """Share of the team's passing sequences that are counter-attacks (play_pattern "counter").

    Inputs: events; team_id (None = league); optional window and game state.
    Value: ratio 0-1; sample = sequences with at least one pass. Evidence: first pass of each
    counter sequence.
    Known limits: relies on the play_pattern label in the feed.
    """
    seqs = _sequences(events, team_id, window, state)
    ctr = [evs[0]["event_id"] for evs in seqs.values() if any(e["play_pattern"] == "counter" for e in evs)]
    return MetricResult(len(ctr) / len(seqs) if seqs else None, tuple(ctr), len(seqs))


def passes_per_sequence(events, team_id, window=None, state=None) -> MetricResult:
    """Mean number of passes (attempted) per passing sequence.

    Inputs: events; team_id (None = league); optional window and game state.
    Value: passes. sd: per-sequence standard deviation. Evidence: first pass of each sequence.
    Known limits: a long sequence can be patient build-up or sterile circulation; read with
    tempo and box_entries.
    """
    seqs = _sequences(events, team_id, window, state)
    m, sd = _mean_sd([len(v) for v in seqs.values()])
    return MetricResult(m, tuple(v[0]["event_id"] for v in seqs.values()), len(seqs), sd=sd)


def chances_conceded_by_lane(events, team_id, window=None, state=None) -> MetricResult:
    """Shots conceded, split by the lane of the opponent's last final-third entry in that sequence.

    Definition: for every opponent shot, the end lane (attacker POV) of the opponent's most recent
    completed final-third entry pass in the same sequence. Shots with no such entry (corners,
    sequences that started in the final third) are counted in detail["no_entry"] only.
    Inputs: events (chronological within each match); team_id = the DEFENDING team; optional
    window and game state (team_id's point of view).
    Value: shots with an entry lane. detail["lanes"]: lane -> count; detail["lane_ids"]: lane ->
    shot event IDs.
    Known limits: small samples (roughly 5 per match); the entry lane is where the move got in,
    not where the shot was taken.
    """
    lanes = {l: [] for l in LANES}
    last, none = {}, 0
    for e in events:
        if e["opponent_team_id"] != team_id:
            continue
        key = (e["match_id"], e["sequence_id"])
        if e["event_type"] == "pass" and e["outcome"] == "success" and _is_entry(e):
            last[key] = lane_of(e["y_end"])
        elif e["event_type"] == "shot" and _in_scope(e, team_id, window, state):
            if key in last:
                lanes[last[key]].append(e["event_id"])
            else:
                none += 1
    ids = [i for l in LANES for i in lanes[l]]
    return MetricResult(len(ids), tuple(ids), len(ids),
                        detail=dict(lanes={l: len(v) for l, v in lanes.items()}, lane_ids=lanes, no_entry=none))


def entry_completion_by_lane(events, team_id, window=None, state=None, conceded=True) -> MetricResult:
    """Completion rate of final-third entry passes by end lane: completed / attempted.

    Definition: an attempted entry is any pass (completed or not) from x < 66.7 to x_end >= 66.7.
    conceded=True (default) counts entries attempted BY OPPONENTS of team_id (how easily a defence
    lets teams in down each lane); conceded=False counts team_id's own entries. Lanes are from the
    attacker's point of view. Game state is team_id's.
    Inputs: events; team_id; optional window, game state; conceded.
    Value: overall completion rate. detail["lanes"]: lane -> {attempted, completed, rate};
    detail["lane_ids"]: lane -> completed entry IDs; detail["lane_attempt_ids"]: lane -> all IDs.
    Known limits: a failed pass's end point is where it was aimed/intercepted, so "lane" of a failed
    entry is approximate; the rate mixes every opponent's quality (a defence that faces strong
    attacks more often looks softer); needs a few hundred attempts per lane to see a 5-6 pp effect.
    """
    att = {l: [] for l in LANES}
    done = {l: [] for l in LANES}
    for e in events:
        if e["event_type"] != "pass" or not _is_entry(e):
            continue
        if conceded:
            if e["opponent_team_id"] != team_id or not _in_scope(e, team_id, window, state):
                continue
        elif e["team_id"] != team_id or not _in_scope(e, team_id, window, state):
            continue
        lane = lane_of(e["y_end"])
        att[lane].append(e["event_id"])
        if e["outcome"] == "success":
            done[lane].append(e["event_id"])
    n = sum(len(v) for v in att.values())
    k = sum(len(v) for v in done.values())
    lanes = {l: dict(attempted=len(att[l]), completed=len(done[l]),
                     rate=len(done[l]) / len(att[l]) if att[l] else None) for l in LANES}
    return MetricResult(k / n if n else None, tuple(i for l in LANES for i in done[l]), n,
                        detail=dict(lanes=lanes, lane_ids=done, lane_attempt_ids=att))


def press_intensity(events, team_id, window=None, state=None) -> MetricResult:
    """Pressure events applied per opponent pass attempted.

    Inputs: events; team_id (None = league); optional window and game state (pressing team's POV).
    Value: ratio. sample_size: opponent passes. Evidence: the pressure events.
    Known limits: counts pressure attempts, not success; the feed logs at most one pressure per
    opponent action. A team that leads and sits deep presses less by design.
    """
    n, ids = 0, []
    for e in events:
        if e["event_type"] == "pass" and (team_id is None or e["opponent_team_id"] == team_id):
            if _in_scope(e, e["opponent_team_id"] if team_id is None else team_id, window, state):
                n += 1
        elif e["event_type"] == "pressure" and (team_id is None or e["team_id"] == team_id):
            if _in_scope(e, e["team_id"] if team_id is None else team_id, window, state):
                ids.append(e["event_id"])
    return MetricResult(len(ids) / n if n else None, tuple(ids), n)


def ppda(events, team_id, window=None, state=None) -> MetricResult:
    """Passes allowed per defensive action (standard PPDA; lower = more intense press).

    Definition: opponent passes attempted with x_start < 60 (their own 60%) divided by the team's
    tackles (won or lost), interceptions and fouls with x_start >= 40 (the same zone in the team's
    own frame). Pressure events are not defensive actions in this definition.
    Inputs: events; team_id; optional window and game state.
    Value: ratio. sample_size: defensive actions. Evidence: the defensive actions.
    Known limits: must not be read alone (rule ppda_alone): it misses pressing that forces a
    bad pass without a tackle, which is most of what a high press does in this feed; use
    press_intensity alongside.
    """
    passes_allowed, acts = 0, []
    for e in events:
        if (e["event_type"] == "pass" and e["opponent_team_id"] == team_id and e["x_start"] < 60
                and _in_scope(e, team_id, window, state)):
            passes_allowed += 1
        elif (e["event_type"] in PPDA_ACTIONS and e["team_id"] == team_id and e["x_start"] >= 40
              and _in_scope(e, team_id, window, state)):
            acts.append(e["event_id"])
    return MetricResult(passes_allowed / len(acts) if acts else None, tuple(acts), len(acts),
                        detail=dict(passes_allowed=passes_allowed))


# ---------- comparison helpers ----------

def z_proportion(p: float | None, p0: float | None, n: int) -> float | None:
    """z of an observed share p on n trials against a reference share p0 (normal approximation)."""
    if p is None or p0 is None or n == 0 or p0 <= 0 or p0 >= 1:
        return None
    return (p - p0) / math.sqrt(p0 * (1 - p0) / n)


def z_mean(m: float | None, m0: float | None, sd0: float | None, n: int) -> float | None:
    """z of an observed mean on n observations against a reference mean with per-observation sd0."""
    if m is None or m0 is None or not sd0 or n == 0:
        return None
    return (m - m0) / (sd0 / math.sqrt(n))


def wilson_interval(hits: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for a share hits/n. Stays inside [0, 1] and behaves at small n,
    unlike the normal approximation."""
    if n == 0:
        return None
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# Confidence labels for a share compared with a baseline share (see docs/engine.md):
#   high   n >= 200, interval half-width <= 5 pp, and the interval excludes the baseline
#   medium n >= 50 and the interval excludes the baseline
#   low    anything else (small sample, or the baseline sits inside the interval)
CONF_HIGH_N, CONF_HIGH_HALF_WIDTH, CONF_MEDIUM_N = 200, 0.05, 50


def share_confidence(hits: int, n: int, baseline: float | None) -> str:
    iv = wilson_interval(hits, n)
    if iv is None or baseline is None:
        return "low"
    excludes = baseline < iv[0] or baseline > iv[1]
    if n >= CONF_HIGH_N and (iv[1] - iv[0]) / 2 <= CONF_HIGH_HALF_WIDTH and excludes:
        return "high"
    if n >= CONF_MEDIUM_N and excludes:
        return "medium"
    return "low"


CONFIDENCE_ORDER = ("low", "medium", "high")


def min_confidence(*labels: str) -> str:
    return min(labels, key=CONFIDENCE_ORDER.index)


def mean_interval(m: float | None, sd: float | None, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """Normal-approximation 95% interval for a mean of n observations with per-observation sd."""
    if m is None or sd is None or n == 0:
        return None
    half = z * sd / math.sqrt(n)
    return m - half, m + half


def interval_confidence(interval, baseline, n: int, rel_half_width: float | None = None) -> str:
    """Confidence label for a mean (or any value with an interval) against a baseline:
    high = n >= 200, interval excludes the baseline and (if given) half-width <= rel_half_width of
    the value; medium = n >= 50 and the interval excludes the baseline; low otherwise."""
    if interval is None or baseline is None:
        return "low"
    lo, hi = interval
    excludes = baseline < lo or baseline > hi
    narrow = True
    if rel_half_width is not None:
        mid = (lo + hi) / 2
        narrow = mid != 0 and (hi - lo) / 2 <= rel_half_width * abs(mid)
    if n >= CONF_HIGH_N and excludes and narrow:
        return "high"
    if n >= CONF_MEDIUM_N and excludes:
        return "medium"
    return "low"
