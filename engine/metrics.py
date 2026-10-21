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

from .tables import BRACKETS3, bracket3, bracket5, score_diff
from .zones import FINAL_THIRD_X, LANES, WIDE_LANES, in_box, lane_of

FORWARD_GAIN = 8.0          # data dictionary: a pass is forward if it gains >= 8 x units
XG_BANDS = ((0.0, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 1.01))
BALL_WINNING = ("tackle", "interception")


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

    Known limits: as xg_sum. The synthetic data currently has no penalties, so npxG equals xG;
    set-piece shots (corners) are included, as in the standard definition.
    """
    rows = [(e, s) for e, s in _team_shots(events, shots, team_id, window, state)
            if s["shot_type"] != "penalty"]
    total = sum(s["xg"] for _, s in rows)
    return MetricResult(total, tuple(e["event_id"] for e, _ in rows), len(rows),
                        detail=dict(shots=len(rows), xg_per_shot=total / len(rows) if rows else None))


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


# ---------- defending / style ----------

def ball_won_height(events, team_id, window=None, state=None) -> MetricResult:
    """Mean x (0 own goal .. 100 opponent goal) where the team wins the ball by tackle or interception.

    Inputs: events; team_id (None = league); optional window and game state.
    Value: mean x. sd: per-event standard deviation. Evidence: the ball-winning events.
    Known limits: event-based proxy, not player positions. Loose-ball recoveries after shots and
    corners are excluded (they say where the ball dropped, not where it was won). It mostly
    reflects where the OPPONENT plays: a pinned-back side wins the ball low whatever it does, and
    on this data it does not single out the pressing team (use press_intensity for that).
    """
    rows = list(e for e in _acting(events, team_id, window, state) if e["event_type"] in BALL_WINNING)
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
    tackles and interceptions with x_start >= 40 (the same zone in the team's own frame).
    Pressure events are not defensive actions in this definition.
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
        elif (e["event_type"] in BALL_WINNING and e["team_id"] == team_id and e["x_start"] >= 40
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
