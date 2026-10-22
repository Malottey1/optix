"""Run one match through the agents and write the timed insight stream.

    python -m agents.run_match --match m_showcase --out out/insights.jsonl

Also writes, next to --out: claims.jsonl (every verification attempt of every published claim),
timeline.json (teams, players, goals and the engine's per-minute momentum, for the dashboard),
ui.json (team, player, ledger and report data for the dashboard, agents/dashboard_data.py) and
agent_log.jsonl (structured logs). Data: --data (match directory, default data/showcase) with the
season baseline from --season (default data/generated).
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from engine import flow as F
from engine import threat as T
from engine.tables import load, match_events

from . import dashboard_data
from .log import AgentLog
from .narrative import languages as available_languages
from .stream import InsightStream


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


def timeline(ds, match_id) -> dict:
    """Match furniture for the dashboard. Every number is copied from the events or computed by
    engine.flow.momentum (home team's sign, one value per minute)."""
    m = ds.matches[match_id]
    evs = match_events(ds)[match_id]
    team = {tid: {"id": tid, "code": t["code"], "name": t["name"]} for tid, t in ds.teams.items()
            if tid in (m["home_team_id"], m["away_team_id"])}
    mom = F.momentum(evs, ds.shots, T.xt_grid(ds), m["home_team_id"], m["away_team_id"]).value
    goals = [{"event_id": e["event_id"], "clock_sec": e["clock_sec"], "team": ds.code(e["team_id"]),
              "player_id": e["player_id"], "score_home": e["score_home"] + (e["team_id"] == m["home_team_id"]),
              "score_away": e["score_away"] + (e["team_id"] == m["away_team_id"])}
             for e in evs if e["event_type"] == "shot" and e["outcome"] == "goal"]
    players = {pid: {"name": p["name"], "team": ds.code(p["team_id"]), "shirt": p["shirt"]}
               for pid, p in ds.players.items() if p["team_id"] in team}
    # elapsed-clock bounds of each half, so the dashboard can show football time (45+2, 90+5)
    periods = [{"period": int(p), "start_sec": min(e["clock_sec"] for e in evs if str(e["period"]) == p),
                "end_sec": max(e["clock_sec"] for e in evs if str(e["period"]) == p)}
               for p in sorted({str(e["period"]) for e in evs})]
    return {"match_id": match_id, "home": team[m["home_team_id"]], "away": team[m["away_team_id"]],
            "duration_sec": evs[-1]["clock_sec"], "periods": periods, "momentum": [[t, round(v, 1)] for t, v in mom],
            "goals": goals, "players": players}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--match", default="m_showcase")
    ap.add_argument("--data", default="data/showcase")
    ap.add_argument("--season", default="data/generated")
    ap.add_argument("--out", default="out/insights.jsonl")
    ap.add_argument("--languages", default=",".join(available_languages()),
                    help="comma-separated template languages (default: all available)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    ds = load(a.data, baseline="season", season_dir=a.season)
    if a.match not in ds.matches:
        ap.error(f"match {a.match!r} not in {a.data}")
    log = AgentLog(out.parent / "agent_log.jsonl")
    stream = InsightStream(ds, a.match, log=log, languages=tuple(a.languages.split(",")))
    insights = stream.run()
    write_jsonl(out, insights)
    write_jsonl(out.parent / "claims.jsonl", stream.attempts())
    (out.parent / "timeline.json").write_text(json.dumps(timeline(ds, a.match), ensure_ascii=False, sort_keys=True),
                                              encoding="utf-8")
    attempts = {x["claim"]["claim_id"]: x for x in stream.attempts()}
    ui = dashboard_data.build(ds, ds.baseline, a.match, insights, attempts)
    (out.parent / "ui.json").write_text(json.dumps(ui, ensure_ascii=False, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    lat = [i["clock"]["emitted_latency_ms"] for i in insights]
    blocked = sum(1 for x in stream.attempts() if x["claim"]["verification"]["status"] == "blocked")
    print(f"{len(insights)} insights -> {out} ({blocked} blocked attempts revised, "
          f"{len(stream.orc.state.dropped)} claims dropped)")
    if lat:
        print(f"latency ms: median {statistics.median(lat):.0f}, max {max(lat)}; "
              f"per-event max {max(stream.event_ms):.1f} ms")
    return insights


if __name__ == "__main__":
    main()
