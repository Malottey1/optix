"""Run one match through the agents and write the timed insight stream.

    python -m agents.run_match --match m_showcase --out out/insights.jsonl

Also writes, next to --out: claims.jsonl (every verification attempt of every published claim) and
agent_log.jsonl (structured logs). Data: --data (match directory, default data/showcase) with the
season baseline from --season (default data/generated).
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from engine.tables import load

from .log import AgentLog
from .narrative import languages as available_languages
from .stream import InsightStream


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")


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
