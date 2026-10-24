"""Claim objects from metrics: one compute function per claim metric, used by both sides.

The Analyst builds a claim by calling `build_claim(metric, ...)`: it computes the values with the
metric functions, rounds them with the fixed rounding table, and attaches evidence IDs. The
Verifier recomputes the same values from the claim's own fields (scope, match, window, subject,
params) with `compute(metric, ...)` and compares within the rounding tolerance. Nothing here
writes prose; numbers come only from engine/ metric code.

Rounding (decimal places): amounts by unit in AMOUNT_DP, supporting values by key in SUPPORT_DP
(default 1). The Verifier's tolerance is half the last rounding step.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import flow as F
from . import metrics as M
from . import threat as T
from .matchup import lane_matchup
from .tables import Dataset, baseline_of, bracket5, match_events, score_diff, team_events
from .zones import FINAL_THIRD_X, LANES, WIDE_LANES, in_box, lane_of

SIDE_LANES = {"left": ("left_flank", "left_half_space"), "right": ("right_half_space", "right_flank")}

AMOUNT_DP = {"percent": 1, "ratio": 2, "xg": 2, "xt": 3, "count": 0, "seconds": 0,
             "per_min": 2, "score_0_100": 1, "per_10min": 2, "m_per_s": 1}
SUPPORT_DP = {"xg_per_shot": 3, "cluster_xg": 2, "open_play_xa": 2, "set_piece_xa": 2,
              "pass_quality_ratio": 2, "press_intensity": 3, "league_xg_per_shot": 3,
              # pattern and naive-claim values (engine/patterns)
              "xg": 2, "cross_xg_per_shot": 3, "cutback_xg_per_shot": 3, "xg_per_touch": 3,
              "league_xg_per_touch": 4, "median_xg": 3, "team_xg_per_shot": 3, "counter_xg_conceded": 2,
              "cross_xg": 2, "set_piece_xg": 2, "transition_xg": 2}
INT_KEYS = {"shots", "low_xg_shots", "team_f3_passes", "opponent_f3_passes", "box_entries", "open_play",
            "set_piece", "passes_allowed", "defensive_actions", "cluster_start_sec", "cluster_end_sec",
            "spell_events", "spell_start_sec", "concede_sample_size", "completion_attempts", "wide_count",
            "pass_count", "minutes",
            # pattern and naive-claim values (engine/patterns)
            "losses", "other_losses", "shots_after_fouls", "shots_after_other", "unpressured_shots", "opp_shots",
            "f3_passes", "build_left", "seconds", "cross_shots", "entries", "cutbacks", "cutback_shots",
            "regains_4s", "fouls_after_losses", "counter_shots_conceded", "isolation_spells", "team_shots",
            "transition_shots", "pressured_passes", "own_zone_passes"}
MAX_EVIDENCE = 15
PATTERN_MAX_EVIDENCE = 240          # a pattern claim keeps every anchor (the recompute starts from them)


def rnd(value: float, dp: int):
    return int(round(value)) if dp == 0 else round(float(value), dp)


def support_dp(key: str) -> int:
    return 0 if key in INT_KEYS else SUPPORT_DP.get(key, 1)


def tolerance(dp: int) -> float:
    return 0.5 * 10 ** (-dp) + 1e-9


@dataclass
class Scope:
    ds: Dataset
    events: list                 # events in scope (season, one match, or a window of it)
    match_id: str | None
    window: tuple | None


def resolve_scope(ds: Dataset, scope: str, match_id: str | None = None, window: dict | tuple | None = None) -> Scope:
    if scope == "season":
        return Scope(ds, ds.events, match_id, None)
    evs = match_events(ds).get(match_id)
    if evs is None:
        raise KeyError(f"match {match_id!r} not in dataset")
    if scope == "match":
        return Scope(ds, evs, match_id, None)
    w = (window["from_sec"], window["to_sec"]) if isinstance(window, dict) else tuple(window)
    return Scope(ds, [e for e in evs if w[0] <= e["clock_sec"] <= w[1]], match_id, w)


def _pct(v):
    return None if v is None else 100 * v


def _team_of(ds, subject):
    return subject["id"] if subject["kind"] == "team" else ds.players[subject["id"]]["team_id"]


def _team_scope_events(sc: Scope, team_id):
    return team_events(sc.ds, team_id) if sc.match_id is None and sc.window is None else sc.events


# ---------- compute functions: (scope, subject, params) -> (values dict, evidence predicate) ----------

def _field_tilt(sc, subject, params):
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    tilt, box = M.field_tilt(ev, tid), M.box_entries(ev, tid)
    f3 = tilt.detail["team_f3_passes"]
    vals = dict(amount=_pct(tilt.value), team_f3_passes=f3, opponent_f3_passes=tilt.detail["opponent_f3_passes"],
                box_entries=box.value, box_entry_share=_pct(box.value / f3) if f3 else 0.0)
    if params.get("with_access"):          # rule ctx_tilt_without_access: where the shots came from
        sh = [e for e in ev if e["event_type"] == "shot" and e["team_id"] == tid]
        out = [e for e in sh if not in_box(e["x_start"], e["y_start"])]
        xg = sum(sc.ds.shots[e["event_id"]]["xg"] for e in sh)
        vals.update(team_shots=len(sh), outside_shot_share=_pct(len(out) / len(sh)) if sh else 0.0,
                    team_xg_per_shot=xg / len(sh) if sh else 0.0)
    if params.get("with_transition"):      # rule ctx_dominance_with_transition_exposure
        from .patterns import rest_defence as RD
        pairs = RD.counter_shots(ev, tid, RD.cfg(RD.FAMILY))
        vals.update(counter_shots_conceded=len(pairs),
                    counter_xg_conceded=sum(sc.ds.shots[s_["event_id"]]["xg"] for _, s_ in pairs))
    return vals, lambda e: (e["team_id"] == tid and e["event_type"] == "pass" and e["outcome"] == "success"
                            and (e["x_start"] >= FINAL_THIRD_X or in_box(e["x_end"], e["y_end"])))


def _xg(sc, subject, params, non_penalty=False):
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    r = (M.npxg_sum if non_penalty else M.xg_sum)(ev, sc.ds.shots, tid)
    low = sum(1 for i in r.evidence_event_ids if sc.ds.shots[i]["xg"] <= 0.08)
    vals = dict(amount=r.value, shots=r.sample_size, low_xg_shots=low,
                xg_per_shot=r.value / r.sample_size if r.sample_size else 0.0)
    if params.get("with_set_piece_split"):   # rule ctx_xg_from_set_pieces: non-penalty set-piece xG
        np_ = [e for e in ev if e["event_type"] == "shot" and e["team_id"] == tid
               and sc.ds.shots[e["event_id"]]["shot_type"] != "penalty"]
        npxg = sum(sc.ds.shots[e["event_id"]]["xg"] for e in np_)
        sp = sum(sc.ds.shots[e["event_id"]]["xg"] for e in np_ if e["play_pattern"] == "set_piece")
        vals.update(set_piece_xg=sp, set_piece_xg_share=_pct(sp / npxg) if npxg else 0.0)
    return vals, lambda e: e["event_type"] == "shot" and e["team_id"] == tid


def _chances(sc, subject, params):
    pid = subject["id"] if subject["kind"] == "player" else None
    tid = _team_of(sc.ds, subject)
    ev = _team_scope_events(sc, tid)
    c = M.chances_created(ev, sc.ds.passes, tid, pid)
    xa = F.xa_split(ev, sc.ds.passes, tid, pid)
    vals = dict(amount=c.value, open_play=c.detail["open_play"], set_piece=c.detail["set_piece"],
                set_piece_share=_pct(c.detail["set_piece"] / c.value) if c.value else 0.0,
                open_play_xa=xa.detail["open_play_xa"], set_piece_xa=xa.detail["set_piece_xa"])
    return vals, lambda e: (e["event_type"] == "pass" and e["team_id"] == tid and (pid is None or e["player_id"] == pid)
                            and sc.ds.passes[e["event_id"]]["is_key_pass"] == 1)


def _forward_passes(sc, subject, params):
    pid = subject["id"]
    tid = _team_of(sc.ds, subject)
    ev = _team_scope_events(sc, tid)
    fw = M.forward_passes_wide_share(ev, tid, pid)
    grid = T.xt_grid(sc.ds)
    q = T.pass_quality_ratio(ev, grid, pid, team_id=tid, league_share=T.league_forward_share(sc.ds))
    vals = dict(amount=fw.value, wide_count=fw.detail["wide_count"],
                wide_share=_pct(fw.detail["wide_share"]) if fw.value else 0.0,
                pass_quality_ratio=q.value if q.value is not None else 0.0)
    return vals, lambda e: (e["event_type"] == "pass" and e["player_id"] == pid and e["outcome"] == "success"
                            and e["x_end"] - e["x_start"] >= M.FORWARD_GAIN)


def _ppda(sc, subject, params):
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    r = M.ppda(ev, tid)
    vals = dict(amount=r.value or 0.0, passes_allowed=r.detail["passes_allowed"], defensive_actions=r.sample_size)
    if params.get("with_press_intensity"):
        vals["press_intensity"] = M.press_intensity(ev, tid).value or 0.0
    if params.get("with_own_zone"):         # rule ctx_press_without_secure_build_up
        from .patterns import pressed_presser as PP
        c = PP.cfg(PP.FAMILY)
        own = PP._own(ev, tid, c)
        ok = sum(e["outcome"] == "success" for e in own)
        vals.update(own_zone_passes=len(own), own_zone_completion=_pct(ok / len(own)) if own else 0.0,
                    league_own_completion=_pct(PP.lines(sc.ds, c)[1]))
    return vals, lambda e: e["team_id"] == tid and e["event_type"] in M.PPDA_ACTIONS and e["x_start"] >= 40


def _shot_cluster(sc, subject, params):
    tid = subject["id"]
    r = F.shot_clusters(sc.events, sc.ds.shots, tid)
    best = r.detail["clusters"][0] if r.detail["clusters"] else None
    vals = dict(amount=r.value, cluster_xg=best["xg"] if best else 0.0,
                cluster_start_sec=best["start_sec"] if best else 0, cluster_end_sec=best["end_sec"] if best else 0)
    return vals, lambda e: e["event_type"] == "shot" and e["team_id"] == tid


def _territorial(sc, subject, params):
    tid = subject["id"]
    r = F.territorial_stress(sc.events, tid)
    best = r.detail["spells"][0] if r.detail["spells"] else None
    vals = dict(amount=r.value, spell_events=best["n_events"] if best else 0,
                spell_start_sec=best["start_sec"] if best else 0, box_entries=M.box_entries(sc.events, tid).value)
    return vals, lambda e: e["team_id"] == tid and e["event_type"] in F.ON_BALL and e["x_start"] >= 50


def _momentum(sc, subject, params):
    tid = subject["id"]
    m = sc.ds.matches[sc.match_id]
    full = match_events(sc.ds)[sc.match_id]
    r = F.momentum(full, sc.ds.shots, T.xt_grid(sc.ds), m["home_team_id"], m["away_team_id"])
    sign = 1 if tid == m["home_team_id"] else -1
    series = dict(r.value)
    lo, hi = sc.window

    def at(t):
        keys = [k for k in series if k <= t]
        return sign * series[max(keys)] if keys else 0.0

    vals = dict(amount=at(hi), momentum_before=at(lo))
    return vals, lambda e: e["event_type"] in ("shot", "pass")


def _rhythm(sc, subject, params):
    end_minute = sc.window[1] // 60 if sc.window else None
    full = match_events(sc.ds)[sc.match_id]
    r = F.rhythm(full, end_minute=end_minute)
    vals = dict(amount=sum(r.value) / len(r.value), minutes=len(r.value))
    return vals, lambda e: e["event_type"] == "possession_change"


def _xt_added(sc, subject, params):
    pid = params["pass_event_id"]
    e = next((x for x in sc.events if x["event_id"] == pid), None)
    grid = T.xt_grid(sc.ds)
    amt = (T.value_at(grid, e["x_end"], e["y_end"]) - T.value_at(grid, e["x_start"], e["y_start"])) if e else 0.0
    return dict(amount=amt), lambda x: x["event_id"] == pid and x["player_id"] == subject["id"]


def _milestone(sc, subject, params):
    pid = subject["id"]
    n = sum(1 for e in sc.events if e["event_type"] == "pass" and e["outcome"] == "success" and e["player_id"] == pid)
    return dict(amount=n), lambda e: e["event_type"] == "pass" and e["player_id"] == pid and e["outcome"] == "success"


def _zone_mismatch(sc, subject, params):
    ds = sc.ds
    att, dfn = subject["id"], params["defender_id"]
    lane = params["lane"]
    if sc.match_id is not None:
        sub = _subset(ds, sc.match_id)
        m = lane_matchup(sub, att, dfn, baseline_ds=baseline_of(ds))
    else:
        m = lane_matchup(ds, att, dfn)
    v = m["lanes"][lane]
    vals = dict(amount=_pct(v["attack_share"]), baseline_share=_pct(v["league_share"]),
                concede_share=_pct(v["concede_share"]), concede_completion=_pct(v["completion"]),
                league_completion=_pct(v["league_completion"]), attack_effect_pp=v["attack_pp"],
                completion_effect_pp=v["completion_pp"], mismatch_pp=v["mismatch_pp"],
                concede_sample_size=m["n_concede"], completion_attempts=v["n_completion_attempts"])
    return vals, lambda e: (e["event_type"] == "pass" and e["x_start"] < FINAL_THIRD_X <= e["x_end"]
                            and lane_of(e["y_end"]) == lane and (e["team_id"] == att or e["opponent_team_id"] == dfn))


_SUBSETS: dict = {}


def _subset(ds: Dataset, match_id: str) -> Dataset:
    """A one-match view of ds, with ds's baseline (never the match itself)."""
    key = (id(ds), match_id)
    if key not in _SUBSETS:
        evs = match_events(ds)[match_id]
        ids = {e["event_id"] for e in evs}
        sub = Dataset(ds.teams, ds.players, {match_id: ds.matches[match_id]}, evs,
                      {k: v for k, v in ds.passes.items() if k in ids}, {k: v for k, v in ds.shots.items() if k in ids},
                      label=ds.label, baseline=baseline_of(ds))
        _SUBSETS[key] = (ds, sub)
    return _SUBSETS[key][1]


# ---------- naive claims the pattern trap rules check (engine/rules/ctx_*.py) ----------

def _attack_side(sc, subject, params):
    """Share of the team's final-third entries (completed passes from outside into the final third)
    that end on `side` (left = left flank + left half-space). with_finish adds where its shots were
    taken: the share of its shots from the opposite side (y on the other side of the lanes)."""
    tid, side = subject["id"], params["side"]
    ev = _team_scope_events(sc, tid)
    ent = M.final_third_entries(ev, tid)
    on = sum(ent.detail["lanes"][l] for l in SIDE_LANES[side])
    vals = dict(amount=_pct(on / ent.value) if ent.value else 0.0, entries=ent.value)
    if params.get("with_finish"):
        sh = [e for e in ev if e["event_type"] == "shot" and e["team_id"] == tid]
        far = [e for e in sh if (e["y_start"] >= 60 if side == "left" else e["y_start"] < 40)]
        vals.update(team_shots=len(sh), opposite_shot_share=_pct(len(far) / len(sh)) if sh else 0.0)
    lanes = SIDE_LANES[side]
    return vals, lambda e: (e["event_type"] == "pass" and e["team_id"] == tid and e["outcome"] == "success"
                            and e["x_start"] < FINAL_THIRD_X <= e["x_end"] and lane_of(e["y_end"]) in lanes)


def _crosses(sc, subject, params):
    """The team's crosses (passes table pass_type cross), the shots they assisted and their xG.
    with_cutbacks adds the cut-back pattern's shots and xG per shot (engine/patterns/cutback.py)."""
    from .patterns import cutback as CB
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    cr = [e for e in ev if e["event_type"] == "pass" and e["team_id"] == tid
          and sc.ds.passes[e["event_id"]]["pass_type"] == "cross"]
    cs = CB.cross_shots(ev, tid, sc.ds.passes, sc.ds.shots)
    cx = [sc.ds.shots[e["event_id"]]["xg"] for e in cs]
    vals = dict(amount=len(cr), cross_shots=len(cs), cross_xg=sum(cx),
                cross_xg_per_shot=sum(cx) / len(cx) if cx else 0.0)
    if params.get("with_cutbacks"):
        f = CB.detect(ev, tid, sc.ds.passes, sc.ds.shots)
        vals.update(cutbacks=f.values["amount"] if f else 0, cutback_xg_per_shot=f.values["xg_per_shot"] if f else 0.0)
    return vals, lambda e: (e["event_type"] == "pass" and e["team_id"] == tid
                            and sc.ds.passes[e["event_id"]]["pass_type"] == "cross")


def _f3_volume(sc, subject, params):
    """Completed passes that start in the final third (metrics.final_third_passes). with_isolation
    adds the flank-isolation spells and the share of these passes played inside them, and the box
    entries (engine/patterns/flank_isolation.py)."""
    from .patterns import flank_isolation as FI
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    r = M.final_third_passes(ev, tid)
    vals = dict(amount=r.value)
    if params.get("with_isolation"):
        f = FI.detect(ev, tid, sc.ds.passes, sc.ds.shots)
        vals.update(isolation_spells=f.values["amount"] if f else 0, isolation_share=f.values["f3_share"] if f else 0.0,
                    box_entries=M.box_entries(ev, tid).value)
    return vals, lambda e: (e["event_type"] == "pass" and e["team_id"] == tid and e["outcome"] == "success"
                            and e["x_start"] >= FINAL_THIRD_X)


def _f3_losses(sc, subject, params):
    """The team's open-play losses in its attacking third (the opponent's possession_change at
    x <= 33.3 in the opponent's frame). with_regains adds how many it won back within 4 seconds."""
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    lo = [e for e in ev if e["event_type"] == "possession_change" and e["opponent_team_id"] == tid
          and 100 - e["x_start"] >= FINAL_THIRD_X]
    vals = dict(amount=len(lo))
    if params.get("with_regains"):
        pos = {e["event_id"]: k for k, e in enumerate(ev)}
        n = 0
        for e in lo:
            for x in ev[pos[e["event_id"]] + 1:]:
                if x["clock_sec"] > e["clock_sec"] + 4:
                    break
                if x["event_type"] == "possession_change":
                    n += x["team_id"] == tid
                    break
        vals.update(regains_4s=n, regain_share=_pct(n / len(lo)) if lo else 0.0)
    return vals, lambda e: (e["event_type"] == "possession_change" and e["opponent_team_id"] == tid
                            and 100 - e["x_start"] >= FINAL_THIRD_X)


TOUCH_TYPES = ("pass", "carry", "dribble", "shot", "duel")


def _touches(sc, subject, params):
    """A player's touches: his passes, carries, dribbles, shots and duels in scope. with_shots adds
    his shots and their xG."""
    pid = subject["id"]
    mine = [e for e in sc.events if e["player_id"] == pid and e["event_type"] in TOUCH_TYPES]
    vals = dict(amount=len(mine))
    if params.get("with_shots"):
        sh = [e for e in mine if e["event_type"] == "shot"]
        vals.update(shots=len(sh), xg=sum(sc.ds.shots[e["event_id"]]["xg"] for e in sh))
    return vals, lambda e: e["player_id"] == pid and e["event_type"] in TOUCH_TYPES


def _fouls(sc, subject, params):
    """The team's fouls. with_after_losses adds the fouls within 5 seconds of losing the ball in the
    middle third (the definition of engine/patterns/tactical_fouling.py) and their share."""
    from .patterns import tactical_fouling as TF
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    fo = [e for e in ev if e["event_type"] == "foul" and e["team_id"] == tid]
    vals = dict(amount=len(fo))
    if params.get("with_after_losses"):
        rows = TF._mid_losses(ev, tid, TF.cfg(TF.FAMILY))
        n = sum(1 for r in rows if r[1])
        vals.update(fouls_after_losses=n, after_loss_share=_pct(n / len(fo)) if fo else 0.0)
    return vals, lambda e: e["event_type"] == "foul" and e["team_id"] == tid


def _possession(sc, subject, params):
    """The team's share of the passes attempted in scope by both teams (an event-count proxy for
    possession: the feed has no possession clock). with_transition adds the shots taken within
    seconds of winning the ball in the team's own half (the definition of
    engine/patterns/direct_transition.py) and their xG."""
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    passes = [e for e in ev if e["event_type"] == "pass"]
    mine = sum(1 for e in passes if e["team_id"] == tid)
    vals = dict(amount=_pct(mine / len(passes)) if passes else 0.0)
    if params.get("with_transition"):
        from .patterns import direct_transition as DT
        _, pairs = DT.transition_shots(ev, tid, DT.cfg(DT.FAMILY))
        vals.update(transition_shots=len(pairs), transition_xg=sum(sc.ds.shots[s_["event_id"]]["xg"] for _, s_ in pairs))
    return vals, lambda e: e["event_type"] == "pass" and e["team_id"] == tid


def _pass_completion(sc, subject, params):
    """A player's pass completion (completed over attempted passes, %). with_pressure_split adds the
    completion of the player's passes under pressure and of the team-mates' passes under pressure
    (the definition of engine/patterns/press_resistant.py)."""
    pid = subject["id"]
    tid = _team_of(sc.ds, subject)
    ev = _team_scope_events(sc, tid)
    mine = [e for e in ev if e["event_type"] == "pass" and e["player_id"] == pid]
    ok = sum(e["outcome"] == "success" for e in mine)
    vals = dict(amount=_pct(ok / len(mine)) if mine else 0.0)
    if params.get("with_pressure_split"):
        pr = [e for e in mine if e["under_pressure"]]
        mates = [e for e in ev if e["event_type"] == "pass" and e["team_id"] == tid and e["player_id"] != pid
                 and e["under_pressure"]]
        pok = sum(e["outcome"] == "success" for e in pr)
        mok = sum(e["outcome"] == "success" for e in mates)
        vals.update(pressured_passes=len(pr), pressured_completion=_pct(pok / len(pr)) if pr else 0.0,
                    team_pressured_completion=_pct(mok / len(mates)) if mates else 0.0)
    return vals, lambda e: e["event_type"] == "pass" and e["player_id"] == pid and e["outcome"] == "success"


COMPUTE = {
    "field_tilt": _field_tilt,
    "xg": _xg,
    "npxg": lambda sc, s, p: _xg(sc, s, p, non_penalty=True),
    "chances_created": _chances,
    "forward_passes": _forward_passes,
    "ppda": _ppda,
    "shot_cluster_score": _shot_cluster,
    "territorial_stress": _territorial,
    "momentum": _momentum,
    "rhythm_index": _rhythm,
    "xt_added": _xt_added,
    "milestone_count": _milestone,
    "zone_mismatch": _zone_mismatch,
    "attack_side_share": _attack_side,
    "crosses": _crosses,
    "final_third_passes": _f3_volume,
    "final_third_losses": _f3_losses,
    "player_touches": _touches,
    "fouls": _fouls,
    "possession_pct": _possession,
    "pass_completion": _pass_completion,
}
# evidence shown first when a claim cites only MAX_EVIDENCE events: the events that carry the point
EVIDENCE_FIRST = {
    "field_tilt": lambda e: in_box(e["x_end"], e["y_end"]),          # box entries, then other passes
}
UNITS = {"field_tilt": "percent", "xg": "xg", "npxg": "xg", "chances_created": "count", "forward_passes": "count",
         "ppda": "ratio", "shot_cluster_score": "count", "territorial_stress": "seconds", "momentum": "score_0_100",
         "rhythm_index": "per_min", "xt_added": "xt", "milestone_count": "count", "zone_mismatch": "percent",
         "attack_side_share": "percent", "crosses": "count", "final_third_passes": "count",
         "final_third_losses": "count", "player_touches": "count", "fouls": "count", "possession_pct": "percent",
         "pass_completion": "percent"}


def compute(ds: Dataset, metric: str, scope: str, subject: dict, params: dict | None = None,
            match_id: str | None = None, window=None):
    """Recompute (values, evidence predicate) for a claim's fields. Values are unrounded."""
    if metric not in COMPUTE:
        raise KeyError(f"no compute function for metric {metric!r}")
    return COMPUTE[metric](resolve_scope(ds, scope, match_id, window), subject, params or {})


def _game_state(ds, team_id, sc: Scope) -> dict:
    """Score difference for the subject at the end of the scope (the state the claim is read in)."""
    if sc.match_id is None or not sc.events:
        return {"score_diff_for_subject": 0, "bracket": "level"}
    d = score_diff(sc.events[-1], team_id)
    return {"score_diff_for_subject": d, "bracket": bracket5(d)}


def build_claim(ds: Dataset, metric: str, scope: str, subject: dict, *, claim_type: str = "stat",
                template_key: str, params: dict | None = None, match_id: str | None = None,
                window: tuple | None = None, param_values: tuple = (), extra_params: dict | None = None,
                claim_id: str | None = None, zone: dict | None = None, attempt: int = 1,
                baseline: dict | None = None) -> dict:
    """Assemble a pending claim. `param_values` names which computed values the template uses
    (each copied into params, rounded exactly like value/supporting_values); `extra_params` adds
    non-numeric params (team codes, lanes)."""
    params = dict(params or {})
    vals, pred = compute(ds, metric, scope, subject, params, match_id,
                         {"from_sec": window[0], "to_sec": window[1]} if window else None)
    sc = resolve_scope(ds, scope, match_id, {"from_sec": window[0], "to_sec": window[1]} if window else None)
    unit = UNITS[metric]
    amount = rnd(vals["amount"], AMOUNT_DP[unit])
    supporting = {k: rnd(v, support_dp(k)) for k, v in vals.items() if k != "amount" and v is not None}
    team_id = _team_of(ds, subject)
    # a season claim's evidence all comes from the subject team's matches (evidence predicates
    # require the team or player), so scan only those
    source = team_events(ds, team_id) if scope == "season" and team_id and metric != "zone_mismatch" else sc.events
    matched = [e for e in source if pred(e)]
    if metric in EVIDENCE_FIRST:
        first = EVIDENCE_FIRST[metric]
        matched = [e for e in matched if first(e)] + [e for e in matched if not first(e)]
    ev = [e["event_id"] for e in matched]
    rendered = {"attempt": attempt}
    p_out = dict(extra_params or {})
    for k in param_values:
        p_out[k] = amount if k == "amount" else supporting[k]
    code = ds.code(team_id)
    subj = dict(subject, team_code=code) if subject["kind"] == "team" else dict(subject, team_code=code)
    claim = {
        "claim_id": claim_id or f"clm_{metric}_{subject['id']}_{match_id or 'season'}"
                                 + (f"_{window[0]}_{window[1]}" if window else ""),
        "scope": scope,
        "match_id": match_id,
        **({"window": {"from_sec": int(window[0]), "to_sec": int(window[1])}} if window else
           ({"window": {"from_sec": 0, "to_sec": max(e["clock_sec"] for e in sc.events)}} if scope == "match" else {})),
        "claim_type": claim_type,
        "metric": metric,
        "subject": subj,
        "value": {"amount": amount, "unit": unit, **(baseline or {}), "sample_size": len(ev)},
        **({"zone": zone} if zone else {}),
        "game_state": _game_state(ds, team_id, sc),
        "evidence_event_ids": ev[:MAX_EVIDENCE],
        "supporting_values": supporting,
        "template_key": template_key,
        "params": {**p_out, **{k: v for k, v in params.items() if isinstance(v, (str, bool)) or v is None}},
        "verification": {"status": "pending", **rendered},
    }
    return claim


# ---------- pattern claims (engine/patterns) ----------

def build_pattern_claim(ds: Dataset, finding, match_id: str, t_end: int, *, template_key: str,
                        param_values: tuple = ("amount",), extra_params: dict | None = None,
                        claim_id: str | None = None, attempt: int = 1) -> dict:
    """A pending claim from a detector finding. The numbers are the detector's, rounded with the
    same table as every claim; the Verifier recomputes them independently from the evidence anchors
    (engine.patterns.recompute), never by calling the detector."""
    from . import patterns as PAT
    window = tuple(finding.window) if finding.window else (0, t_end)
    sc = resolve_scope(ds, "window", match_id, window)
    subject = ({"kind": "player", "id": finding.player_id} if finding.player_id
               else {"kind": "team", "id": finding.team_id})
    vals = finding.values
    amount = rnd(vals["amount"], AMOUNT_DP[PAT.UNITS[finding.family]])
    supporting = {k: rnd(v, support_dp(k)) for k, v in vals.items() if k != "amount" and v is not None}
    p_out = dict(extra_params or {})
    for k in param_values:
        p_out[k] = amount if k == "amount" else supporting[k]
    ev = finding.evidence
    return {
        "claim_id": claim_id or f"clm_{finding.family}_{subject['id']}_{match_id}_{window[0]}_{window[1]}",
        "scope": "window",
        "match_id": match_id,
        "window": {"from_sec": int(window[0]), "to_sec": int(window[1])},
        "claim_type": "pattern",
        "metric": finding.family,
        "subject": dict(subject, team_code=ds.code(finding.team_id)),
        "value": {"amount": amount, "unit": PAT.UNITS[finding.family], "sample_size": len(ev)},
        "game_state": _game_state(ds, finding.team_id, sc),
        "evidence_event_ids": ev[:PATTERN_MAX_EVIDENCE],
        "supporting_values": supporting,
        "template_key": template_key,
        "params": p_out,
        "verification": {"status": "pending", "attempt": attempt},
    }
