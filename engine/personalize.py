"""Personalize: chooses and orders what one viewer sees from the already verified insight stream.

Definition. personalize(stream, profile, involved) returns a sub-list of `stream`, in a new order,
made of the very same insight objects: it filters, ranks and caps, and never copies, edits, phrases
or computes. The rules come from contracts/personalization.json (shared with
web/src/lib/personalize.ts, cross-checked on tests/fixtures/personalize_golden.json):
  player  keep insights involving that player id: listed in the insight's player_ids, or the
          player (or related player) of one of its evidence events (`involved`: event id -> ids)
  metric  keep insights whose insight_type is one of the metric's families
  clubs   insights whose primary team is followed come first at the same clock, and first in
          the fan ranking
  mode    fan: the top max_cards by fan_priority (then clock, then id), in that ranked order;
          analyst: everything, in stream order (with the club boost)
Inputs. stream: insight dicts (contracts/insight.schema.json); profile: a mapping with optional
mode, language, clubs, players, metric. Unknown modes and metrics are ignored (no filter); an empty
profile returns the stream unchanged. language never selects: every insight carries every language.
Limits. Involvement is only as good as the evidence events: a player who touched the move but is not
on an evidence event is not matched. Only the first player in `players` is followed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

CONFIG_PATH = Path(__file__).resolve().parent.parent / "contracts" / "personalization.json"
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
MODES = tuple(CONFIG["modes"])
METRICS = tuple(CONFIG["metrics"])


def _list(v) -> list:
    if v is None:
        return []
    return [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)]


def involves(ins: Mapping, player: str, involved: Mapping[str, Sequence[str]] | None = None) -> bool:
    """True when `player` is on the insight (player_ids) or on one of its evidence events."""
    if player in (ins.get("player_ids") or []):
        return True
    involved = involved or {}
    return any(player in (involved.get(e) or ()) for e in ins.get("evidence_event_ids") or [])


def fan_rank(ins: Mapping, clubs: Sequence[str] = ()) -> tuple:
    prio = CONFIG["fan_priority"]
    t = ins["insight_type"]
    return (ins["teams"]["primary"] not in clubs, prio.index(t) if t in prio else len(prio),
            ins["clock"]["start_sec"], ins["insight_id"])


def personalize(stream: Sequence[Mapping], profile: Mapping | None = None,
                involved: Mapping[str, Sequence[str]] | None = None) -> list:
    """The viewer's insights: the same objects as in `stream`, filtered, ranked and capped."""
    p = profile or {}
    mode = p.get("mode") if p.get("mode") in MODES else None
    metric = p.get("metric") if p.get("metric") in METRICS else None
    clubs = _list(p.get("clubs"))
    players = _list(p.get("players"))
    out = list(stream)
    if players:
        out = [i for i in out if involves(i, players[0], involved)]
    if metric:
        fams = CONFIG["metrics"][metric]["families"]
        out = [i for i in out if i["insight_type"] in fams]
    if mode == "fan":
        out = sorted(out, key=lambda i: fan_rank(i, clubs))[: CONFIG["modes"]["fan"]["max_cards"]]
    elif clubs:
        out = sorted(out, key=lambda i: (i["clock"]["start_sec"], i["teams"]["primary"] not in clubs))
    return out


def personalize_fixtures(fixtures: Sequence[Mapping], clubs: Sequence[str]) -> list:
    """Fixtures with a followed club first (stable: otherwise the given order). Rows need home, away."""
    clubs = _list(clubs)
    return sorted(fixtures, key=lambda f: not (f["home"] in clubs or f["away"] in clubs))
