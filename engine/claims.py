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

AMOUNT_DP = {"percent": 1, "ratio": 2, "xg": 2, "xt": 3, "count": 0, "seconds": 0,
             "per_min": 2, "score_0_100": 1, "per_10min": 2, "m_per_s": 1}
SUPPORT_DP = {"xg_per_shot": 3, "cluster_xg": 2, "open_play_xa": 2, "set_piece_xa": 2,
              "pass_quality_ratio": 2, "press_intensity": 3, "league_xg_per_shot": 3}
INT_KEYS = {"shots", "low_xg_shots", "team_f3_passes", "opponent_f3_passes", "box_entries", "open_play",
            "set_piece", "passes_allowed", "defensive_actions", "cluster_start_sec", "cluster_end_sec",
            "spell_events", "spell_start_sec", "concede_sample_size", "completion_attempts", "wide_count",
            "pass_count", "minutes"}
MAX_EVIDENCE = 15


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
    return vals, lambda e: (e["team_id"] == tid and e["event_type"] == "pass" and e["outcome"] == "success"
                            and (e["x_start"] >= FINAL_THIRD_X or in_box(e["x_end"], e["y_end"])))


def _xg(sc, subject, params, non_penalty=False):
    tid = subject["id"]
    ev = _team_scope_events(sc, tid)
    r = (M.npxg_sum if non_penalty else M.xg_sum)(ev, sc.ds.shots, tid)
    low = sum(1 for i in r.evidence_event_ids if sc.ds.shots[i]["xg"] <= 0.08)
    vals = dict(amount=r.value, shots=r.sample_size, low_xg_shots=low,
                xg_per_shot=r.value / r.sample_size if r.sample_size else 0.0)
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
    return vals, lambda e: e["team_id"] == tid and e["event_type"] in M.BALL_WINNING and e["x_start"] >= 40


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
}
UNITS = {"field_tilt": "percent", "xg": "xg", "npxg": "xg", "chances_created": "count", "forward_passes": "count",
         "ppda": "ratio", "shot_cluster_score": "count", "territorial_stress": "seconds", "momentum": "score_0_100",
         "rhythm_index": "per_min", "xt_added": "xt", "milestone_count": "count", "zone_mismatch": "percent"}


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
    ev = [e["event_id"] for e in source if pred(e)]
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
