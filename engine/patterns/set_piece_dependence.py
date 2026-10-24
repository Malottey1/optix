"""P15 Set-piece dependence (family pat_set_piece_dependence).

Definition: of the team's non-penalty xG in the scope, the share from set-piece shots (shots whose
event play_pattern is "set_piece": corners, free kicks and their second balls; penalties are left
out of both sides of the share). A finding needs >= min_sp_shots set-piece shots, non-penalty xG
>= min_npxg, and a set-piece share >= min_share and >= min_share_vs_league x the league share
(set-piece xG over all non-penalty xG, pooled over the baseline season).
Anchors: the team's set-piece shots in the scope, in order (one instance each).
Numbers: set-piece shots, set-piece xG, open-play xG, non-penalty xG, the set-piece share (%) and
the league share (%).
Known limits: the feed labels the phase (play_pattern), not how the set piece was won; a share on
a handful of shots is noisy, hence the shot and xG floors.
"""
from __future__ import annotations

from engine.tables import Dataset, match_events

from .config import cfg
from .helpers import Finding, league

FAMILY = "pat_set_piece_dependence"


def _np_shots(evs, shots, team_id):
    return [e for e in evs if e["event_type"] == "shot" and e["team_id"] == team_id
            and shots[e["event_id"]]["shot_type"] != "penalty"]


def league_share(base: Dataset) -> float:
    sp = total = 0.0
    for mid, evs in match_events(base).items():
        for e in evs:
            if e["event_type"] == "shot" and base.shots[e["event_id"]]["shot_type"] != "penalty":
                x = base.shots[e["event_id"]]["xg"]
                total += x
                sp += x if e["play_pattern"] == "set_piece" else 0.0
    return sp / total if total else 0.0


def _values(sp, npxg, spxg, lg):
    return dict(amount=len(sp), set_piece_xg=spxg, open_play_xg=npxg - spxg, npxg=npxg,
                share=100 * spxg / npxg if npxg else 0.0, league_share=100 * lg)


def _holds(n_sp, npxg, spxg, lg, c) -> bool:
    share = spxg / npxg if npxg else 0.0
    return (n_sp >= c["min_sp_shots"] and npxg >= c["min_npxg"] and share >= c["min_share"]
            and share >= c["min_share_vs_league"] * lg)


def detect(ds: Dataset, events, team_id, c=None) -> Finding | None:
    c = c or cfg(FAMILY)
    sh = _np_shots(events, ds.shots, team_id)
    sp = [e for e in sh if e["play_pattern"] == "set_piece"]
    npxg = sum(ds.shots[e["event_id"]]["xg"] for e in sh)
    spxg = sum(ds.shots[e["event_id"]]["xg"] for e in sp)
    lg = league(ds, FAMILY, league_share)
    if not _holds(len(sp), npxg, spxg, lg, c):
        return None
    return Finding(FAMILY, team_id, [[e["event_id"]] for e in sp], _values(sp, npxg, spxg, lg))


def recompute(ds: Dataset, team_id, anchors, scope_events, c=None):
    """Independent recompute from the scope: every anchor must be one of the team's non-penalty
    set-piece shots, and the anchors must be all of them, in order; the xG split is re-summed."""
    c = c or cfg(FAMILY)
    ids = {e["event_id"]: e for e in scope_events}
    bad = [i for i in anchors if i not in ids or ids[i]["event_type"] != "shot" or ids[i]["team_id"] != team_id
           or ids[i]["play_pattern"] != "set_piece" or ds.shots[i]["shot_type"] == "penalty"]
    npxg = spxg = 0.0
    sp = []
    for e in scope_events:
        if e["event_type"] != "shot" or e["team_id"] != team_id or ds.shots[e["event_id"]]["shot_type"] == "penalty":
            continue
        npxg += ds.shots[e["event_id"]]["xg"]
        if e["play_pattern"] == "set_piece":
            spxg += ds.shots[e["event_id"]]["xg"]
            sp.append(e["event_id"])
    if bad:
        return None, bad
    if list(anchors) != sp:
        return None, sorted(set(anchors) ^ set(sp)) or ["evidence_out_of_order"]
    lg = league(ds, FAMILY, league_share)
    vals = _values(sp, npxg, spxg, lg)
    return (vals, []) if _holds(len(sp), npxg, spxg, lg, c) else (vals, ["pattern_does_not_hold"])
