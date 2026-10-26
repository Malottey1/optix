"""The showcase match's compact event file for player focus (#/match/m_showcase, "Player so far").

    python -m agents.showcase_events                # writes out/matches/events-m_showcase.json

Read only when a viewer follows a player in the live hub (web/src/data/events.ts). One row per event
in clock order: [n, clock_sec, type, player, x, y, outcome, related, key], where n is the event id's
number (m_showcase_e00402 -> 402), type / outcome / player / related index into `types`, `outcomes`
and `players` (null when absent), x and y are the start location rounded to whole units of the
0-100 attacking frame, and key is 1 for a key pass (passes.csv is_key_pass), else 0. Every value is
copied from data/showcase (events.csv, passes.csv); nothing is computed beyond rounding.
The file is named events-*.json so the match-file globs (m_*.json) and their schema stay as they are.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

MATCH = "m_showcase"
COLS = ("n", "clock_sec", "type", "player", "x", "y", "outcome", "related", "key")


def whole(v: str):
    return None if v in ("", None) else math.floor(float(v) + 0.5)


def build(showcase_dir: Path) -> dict:
    with open(showcase_dir / "events.csv", newline="", encoding="utf-8") as f:
        evs = [e for e in csv.DictReader(f) if e["match_id"] == MATCH]
    with open(showcase_dir / "passes.csv", newline="", encoding="utf-8") as f:
        key = {p["event_id"] for p in csv.DictReader(f) if p["is_key_pass"] in ("1", "True", "true")}
    evs.sort(key=lambda e: (int(e["clock_sec"]), e["event_id"]))
    types = sorted({e["event_type"] for e in evs})
    outcomes = sorted({e["outcome"] for e in evs if e["outcome"]})
    players = sorted({e[k] for e in evs for k in ("player_id", "related_player_id") if e[k]})
    ti, oi, pi = ({v: i for i, v in enumerate(xs)} for xs in (types, outcomes, players))
    rows = [[int(e["event_id"].rsplit("_e", 1)[1]), int(e["clock_sec"]), ti[e["event_type"]],
             pi.get(e["player_id"]), whole(e["x_start"]), whole(e["y_start"]),
             oi.get(e["outcome"]), pi.get(e["related_player_id"]), int(e["event_id"] in key)] for e in evs]
    return dict(match_id=MATCH, cols=list(COLS), types=types, outcomes=outcomes, players=players, rows=rows)


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--showcase", default="data/showcase")
    ap.add_argument("--out", default="out/matches")
    a = ap.parse_args(argv)
    text = dumps(build(Path(a.showcase)))
    out = Path(a.out) / f"events-{MATCH}.json"
    out.write_text(text, encoding="utf-8")
    print(f"{out}: {len(text.encode())} B")


if __name__ == "__main__":
    main()
