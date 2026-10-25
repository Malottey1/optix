"""Attack-vs-defence lane matchup for a pair of teams, and the top mismatch as a claim object.

Zones are from the ATTACKER's point of view on both sides of the comparison: the attacker's
entries down its left and the entries the defender concedes down the attacker's left (the
defender's own right) are the same lane, "left_flank". Never mirror one side.

Per lane:
    attack_share   share of the attacker's final-third entries that go into the lane
    league_share   share of all final-third entries in the baseline league that go into the lane
    attack_pp      attack_share - league_share, percentage points (the attacker's habit)
    completion     rate at which the defender's opponents complete entry passes into the lane
    league_completion   the league's rate for the lane
    completion_pp  completion - league_completion, percentage points (the defender's softness;
                   this is what recovers planted soft lanes, see docs/engine.md)
    concede_share / concede_pp   share of entries the defender concedes into the lane, and its lift
                   (kept for context: it mixes in every opponent's own lane habits)
    *_interval     95% Wilson intervals
    mismatch_pp    attack_pp + completion_pp; a lane only counts when both are positive
    confidence     the lower of the attacker-share and the completion confidence labels
    attack_z / completion_z   sampling z, kept only as an internal tie-break signal

Baselines come from tables.baseline_of(ds): the season when a single match was loaded with
baseline="season", never the match itself.

Descriptive only: a mismatch says where the attacker's habit meets the defender's soft spot in
past matches; it is not a prediction of what will happen.
"""
from __future__ import annotations

from .metrics import min_confidence, share_confidence, wilson_interval, z_proportion
from .profiles import league_baseline, team_metric
from .tables import Dataset, baseline_of
from .zones import LANES, WIDE_LANES

MAX_EVIDENCE = 12
# a lane is a candidate when both lifts are above these (percentage points); the dashboard reads them
# from here (ui.json teams.matchup_rule) so its display never retypes them
MIN_ATTACK_PP = 0.0
MIN_COMPLETION_PP = 0.0


def _pp(v):
    return None if v is None else 100 * v


def lane_matchup(ds: Dataset, attacker_id: str, defender_id: str, bracket: str = "all",
                 baseline_ds: Dataset | None = None) -> dict:
    """Per-lane mismatch table plus the top mismatch (or None if no lane has both lifts > 0).

    Inputs: dataset; attacker and defender team ids; game-state bracket ("all" by default; the
    attacker's state for its entries, the defender's for concessions); baseline_ds = the dataset
    the league shares come from (defaults to ds; single-match analyses pass the season).
    Returns {attacker, defender, bracket, n_attack, n_concede, n_baseline, lanes, top}.
    """
    base_ds = baseline_ds or baseline_of(ds)
    att = team_metric(ds, attacker_id, "entry_lanes", bracket)
    dfn = team_metric(ds, defender_id, "entry_lanes_conceded", bracket)
    comp = team_metric(ds, defender_id, "entry_completion_conceded", bracket).detail["lanes"]
    base = league_baseline(base_ds, bracket)
    league, n_base = base["entry_lanes"], base["entry_lanes_n"]
    lanes = {}
    for lane in LANES:
        ha, hc = att.detail["lanes"][lane], dfn.detail["lanes"][lane]
        a = ha / att.value if att.value else None
        c = hc / dfn.value if dfn.value else None
        lg, lc = league[lane], base["entry_completion_conceded"][lane]
        k, n = comp[lane]["completed"], comp[lane]["attempted"]
        r = k / n if n else None
        ap = None if a is None else _pp(a - lg)
        rp = None if r is None or lc is None else _pp(r - lc)
        lanes[lane] = dict(
            attack_share=a, league_share=lg, attack_pp=ap, attack_interval=wilson_interval(ha, att.value),
            completion=r, league_completion=lc, completion_pp=rp, completion_interval=wilson_interval(k, n),
            concede_share=c, concede_pp=None if c is None else _pp(c - lg),
            concede_interval=wilson_interval(hc, dfn.value),
            mismatch_pp=None if ap is None or rp is None else ap + rp,
            confidence=min_confidence(share_confidence(ha, att.value, lg), share_confidence(k, n, lc)),
            attack_z=z_proportion(a, lg, att.value), completion_z=z_proportion(r, lc, n),
            concede_z=z_proportion(c, lg, dfn.value),
            n_attack_lane=ha, n_concede_lane=hc, n_completion_attempts=n)
    candidates = [l for l, v in lanes.items() if v["mismatch_pp"] is not None
                  and v["attack_pp"] > MIN_ATTACK_PP and v["completion_pp"] > MIN_COMPLETION_PP]
    top = None
    if candidates:
        lane = max(candidates, key=lambda l: (lanes[l]["mismatch_pp"], lanes[l]["attack_z"] + lanes[l]["completion_z"]))
        top = dict(lane=lane, **lanes[lane], evidence_event_ids=_evidence(att, dfn, lane))
    return dict(attacker=attacker_id, defender=defender_id, bracket=bracket,
                n_attack=att.value, n_concede=dfn.value, n_baseline=n_base,
                baseline_label=base_ds.label, baseline_is_self=base_ds is ds, lanes=lanes, top=top)


def _evidence(att, dfn, lane) -> list:
    """Up to MAX_EVIDENCE event IDs, balanced across three groups: the attacker's entries into
    the lane against this defender, the attacker's entries there against others, and the
    defender's concessions there to others. A short group's quota passes to the next."""
    att_ids, con_ids = att.detail["lane_ids"][lane], dfn.detail["lane_ids"][lane]
    con_set, att_set = set(con_ids), set(att_ids)
    groups = [[i for i in att_ids if i in con_set],
              [i for i in att_ids if i not in con_set],
              [i for i in con_ids if i not in att_set]]
    picked, quota = [], MAX_EVIDENCE // len(groups)
    for g in groups:
        picked += g[:quota]
    for g in groups:                     # top up from whatever is left, in group order
        picked += [i for i in g if i not in picked][:MAX_EVIDENCE - len(picked)]
    return picked[:MAX_EVIDENCE]


def _r1(v):
    return round(v, 1)


def matchup_claim(ds: Dataset, attacker_id: str, defender_id: str, match_id: str | None = None,
                  bracket: str = "all", baseline_ds: Dataset | None = None) -> dict | None:
    """The top lane mismatch as a claim object (contracts/claim.schema.json), status "pending".

    Scope "season": an aggregate over `ds` (a pre-match preview), so there is no window;
    `match_id` optionally names the match being previewed. If `ds` is a single match loaded with a
    season baseline, the scope is "match": the window is the whole match and match_id is that match. value.amount is the attacker's lane
    share (percent) against the baseline league share; supporting_values carries every other
    number the template uses so the Verifier can recompute it. Returns None when there is no
    mismatch to claim.
    """
    m = lane_matchup(ds, attacker_id, defender_id, bracket, baseline_ds)
    top = m["top"]
    if top is None:
        return None
    a, d = ds.code(attacker_id), ds.code(defender_id)
    amount, base, conc = _r1(100 * top["attack_share"]), _r1(100 * top["league_share"]), _r1(100 * top["concede_share"])
    lo, hi = top["attack_interval"]
    single = ds.baseline is not None and len(ds.matches) == 1
    if single:
        match_id = next(iter(ds.matches))
    supporting = {
        "baseline_share": base,
        "concede_share": conc,
        "concede_completion": _r1(100 * top["completion"]),
        "league_completion": _r1(100 * top["league_completion"]),
        "attack_effect_pp": _r1(top["attack_pp"]),
        "completion_effect_pp": _r1(top["completion_pp"]),
        "mismatch_pp": _r1(top["mismatch_pp"]),
        "concede_sample_size": m["n_concede"],
        "completion_attempts": top["n_completion_attempts"],
    }
    return {
        "claim_id": f"clm_matchup_{a}_{d}_{top['lane']}",
        "scope": "match" if single else "season",
        "match_id": match_id,
        **({"window": {"from_sec": 0, "to_sec": max(e["clock_sec"] for e in ds.events)}} if single else {}),
        "claim_type": "matchup",
        "metric": "zone_mismatch",
        "subject": {"kind": "team", "id": attacker_id, "team_code": a},
        "value": {
            "amount": amount,
            "unit": "percent",
            "baseline": base,
            "baseline_kind": "league_avg",
            "baseline_source": {"kind": "season", "n": m["n_baseline"], "dataset": m["baseline_label"]},
            "interval": {"low": _r1(100 * lo), "high": _r1(100 * hi), "level": 0.95},
            "effect_pp": _r1(top["attack_pp"]),
            "confidence": top["confidence"],
            "z_score": round(top["attack_z"], 2),
            "sample_size": m["n_attack"],
        },
        "zone": {"lane": top["lane"], "third": "attacking"},
        "game_state": {"score_diff_for_subject": 0, "bracket": "level"},
        "evidence_event_ids": top["evidence_event_ids"],
        "supporting_values": supporting,
        "template_key": "matchup.weak_flank" if top["lane"] in WIDE_LANES else "matchup.weak_lane",
        "params": {
            "attacker": a, "defender": d, "lane": top["lane"], "defender_id": defender_id,
            "attack_share": amount, "league_share": base,
            "concede_completion": supporting["concede_completion"],
            "league_completion": supporting["league_completion"],
        },
        "verification": {"status": "pending", "attempt": 1},
    }
