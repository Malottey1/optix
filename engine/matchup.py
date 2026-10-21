"""Attack-vs-defence lane matchup for a pair of teams, and the top mismatch as a claim object.

Zones are from the ATTACKER's point of view on both sides of the comparison: the attacker's
entries down its left and the entries the defender concedes down the attacker's left (the
defender's own right) are the same lane, "left_flank". Never mirror one side.

Per lane:
    attack_share   share of the attacker's final-third entries that go into the lane
    concede_share  share of the final-third entries the defender concedes that come into the lane
    league_share   share of all final-third entries in the league that go into the lane
    attack_z / concede_z   proportion z of each share against league_share (sample sizes below)
    mismatch       (attack_z + concede_z) / sqrt(2): high when the attacker over-uses a lane the
                   defender over-concedes. A lane only counts as a mismatch when both z > 0.

Descriptive only: a mismatch says where the attacker's habit meets the defender's soft spot in
past matches; it is not a prediction of what will happen.
"""
from __future__ import annotations

import math

from .profiles import team_metric, league_baseline
from .metrics import z_proportion
from .tables import Dataset
from .zones import LANES, WIDE_LANES

MAX_EVIDENCE = 12


def lane_matchup(ds: Dataset, attacker_id: str, defender_id: str, bracket: str = "all") -> dict:
    """Per-lane mismatch table plus the top mismatch (or None if no lane has both z > 0).

    Inputs: dataset; attacker and defender team ids; game-state bracket of each team's own
    matches ("all" by default; the attacker's state for its entries, the defender's for
    concessions).
    Returns {attacker, defender, bracket, n_attack, n_concede, lanes: {lane: {...}}, top}.
    """
    att = team_metric(ds, attacker_id, "entry_lanes", bracket)
    dfn = team_metric(ds, defender_id, "entry_lanes_conceded", bracket)
    league = league_baseline(ds, bracket)["entry_lanes"]
    lanes = {}
    for lane in LANES:
        a = att.detail["lanes"][lane] / att.value if att.value else None
        c = dfn.detail["lanes"][lane] / dfn.value if dfn.value else None
        za = z_proportion(a, league[lane], att.value)
        zc = z_proportion(c, league[lane], dfn.value)
        lanes[lane] = dict(attack_share=a, concede_share=c, league_share=league[lane],
                           attack_z=za, concede_z=zc,
                           mismatch=None if za is None or zc is None else (za + zc) / math.sqrt(2),
                           n_attack_lane=att.detail["lanes"][lane], n_concede_lane=dfn.detail["lanes"][lane])
    candidates = [l for l, v in lanes.items() if v["mismatch"] is not None
                  and v["attack_z"] > 0 and v["concede_z"] > 0]
    top = None
    if candidates:
        lane = max(candidates, key=lambda l: lanes[l]["mismatch"])
        top = dict(lane=lane, **lanes[lane], evidence_event_ids=_evidence(att, dfn, lane))
    return dict(attacker=attacker_id, defender=defender_id, bracket=bracket,
                n_attack=att.value, n_concede=dfn.value, lanes=lanes, top=top)


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


def matchup_claim(ds: Dataset, attacker_id: str, defender_id: str, match_id: str | None = None,
                  bracket: str = "all") -> dict | None:
    """The top lane mismatch as a claim object (contracts/claim.schema.json), status "pending".

    Pre-match preview over the season so far: window 0-0 and game state level, as in the contract
    example. value.amount is the attacker's lane share (percent) against the league share.
    Returns None when there is no mismatch to claim.
    """
    m = lane_matchup(ds, attacker_id, defender_id, bracket)
    top = m["top"]
    if top is None:
        return None
    a, d = ds.code(attacker_id), ds.code(defender_id)
    pct = lambda v: round(100 * v, 1)
    return {
        "claim_id": f"clm_matchup_{a}_{d}_{top['lane']}",
        "match_id": match_id or f"preview_{a}_{d}",
        "claim_type": "matchup",
        "metric": "zone_mismatch",
        "subject": {"kind": "team", "id": attacker_id, "team_code": a},
        "value": {
            "amount": pct(top["attack_share"]),
            "unit": "percent",
            "baseline": pct(top["league_share"]),
            "baseline_kind": "league_avg",
            "z_score": round(top["attack_z"], 2),
            "sample_size": m["n_attack"],
        },
        "zone": {"lane": top["lane"], "third": "attacking"},
        "window": {"from_sec": 0, "to_sec": 0},
        "game_state": {"score_diff_for_subject": 0, "bracket": "level"},
        "evidence_event_ids": top["evidence_event_ids"],
        "template_key": "matchup.weak_flank" if top["lane"] in WIDE_LANES else "matchup.weak_lane",
        "params": {
            "attacker": a, "defender": d, "lane": top["lane"],
            "attack_share": pct(top["attack_share"]), "league_share": pct(top["league_share"]),
            "concede_share": pct(top["concede_share"]), "concede_sample_size": m["n_concede"],
            "mismatch_score": round(top["mismatch"], 2),
        },
        "verification": {"status": "pending", "attempt": 1},
    }
