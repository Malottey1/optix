"""Writes the golden cases shared by tests/test_personalize.py and web/src/lib/personalize.test.ts.

    python -m tools.personalize_golden

personalize_golden.json: the showcase stream reduced to the fields personalization reads, the
evidence-event -> player ids map, and per profile the insight ids engine.personalize selects (in
order). player_so_far_golden.json: per player and clock, counts recomputed straight from
data/showcase/events.csv, passes.csv and shots.csv (not from the exported event file), which the
web's "Player so far" card must reproduce from events-m_showcase.json and ui.json shots.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from engine.personalize import personalize

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
SHOWCASE = ROOT / "data" / "showcase"

PROFILES = [
    {},
    {"mode": "fan"},
    {"mode": "analyst"},
    {"mode": "fan", "clubs": ["NTG"]},
    {"mode": "analyst", "clubs": ["NTG"]},
    {"mode": "analyst", "players": ["NTG_10"]},
    {"mode": "fan", "players": ["NTG_10"]},
    {"mode": "analyst", "metric": "momentum"},
    {"mode": "fan", "metric": "xg"},
    {"mode": "zzz", "metric": "zzz", "language": "xx"},
    {"mode": "analyst", "players": ["AUR_10"], "metric": "xg"},
    {"mode": "fan", "clubs": ["AUR"], "language": "es"},
    {"mode": "analyst", "metric": "rhythm"},
    {"mode": "analyst", "metric": "stress", "clubs": ["AUR"]},
]
FOCUS = [("NTG_10", (900, 2883, 6000)), ("AUR_09", (1149, 6000)), ("AUR_10", (3000, 6000)), ("NTG_02", (3842, 6000))]


def _csv(name):
    with open(SHOWCASE / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def stream_rows() -> list:
    rows = [json.loads(x) for x in (ROOT / "web" / "public" / "data" / "insights.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return [{"insight_id": i["insight_id"], "insight_type": i["insight_type"],
             "clock": {"start_sec": i["clock"]["start_sec"]}, "teams": {"primary": i["teams"]["primary"]},
             "player_ids": i["player_ids"], "evidence_event_ids": i["evidence_event_ids"]} for i in rows]


def involved_map(stream) -> dict:
    ids = {e for i in stream for e in i["evidence_event_ids"]}
    out = {}
    for e in _csv("events.csv"):
        if e["event_id"] in ids:
            out[e["event_id"]] = [p for p in (e["player_id"], e["related_player_id"]) if p]
    return dict(sorted(out.items()))


def so_far(pid: str, t: int) -> dict:
    evs = [e for e in _csv("events.csv") if int(e["clock_sec"]) <= t]
    key = {p["event_id"] for p in _csv("passes.csv") if p["is_key_pass"] == "1"}
    mine = [e for e in evs if e["player_id"] == pid]
    xg = sum(float(s["xg"]) for s in _csv("shots.csv") if s["player_id"] == pid
             and s["event_id"] in {e["event_id"] for e in mine})
    return {"passes": sum(e["event_type"] == "pass" for e in mine),
            "shots": sum(e["event_type"] == "shot" for e in mine),
            "xg": round(xg, 2),
            "key_passes": sum(e["event_type"] == "pass" and e["event_id"] in key for e in mine),
            "cards": sum(e["event_type"] == "card" for e in mine),
            "subs": sum(e["event_type"] == "substitution" and pid in (e["player_id"], e["related_player_id"]) for e in evs)}


def build() -> tuple[dict, dict]:
    stream = stream_rows()
    involved = involved_map(stream)
    cases = [{"profile": p, "ids": [i["insight_id"] for i in personalize(stream, p, involved)]} for p in PROFILES]
    golden = {"stream": stream, "involved": involved, "cases": cases}
    focus = {"cases": [{"player": pid, "clock": t, "counts": so_far(pid, t)} for pid, ts in FOCUS for t in ts]}
    return golden, focus


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def main():
    golden, focus = build()
    (FIX / "personalize_golden.json").write_text(dumps(golden), encoding="utf-8")
    (FIX / "player_so_far_golden.json").write_text(dumps(focus), encoding="utf-8")
    print(f"{len(golden['cases'])} personalize cases, {len(focus['cases'])} player-so-far cases")


if __name__ == "__main__":
    main()
