"""Print a personalized view of an insight stream.

    python -m agents.personalize --in out/insights.jsonl --mode casual --lang es --favorite NTG
    python -m agents.personalize --player NTG_07          # player focus
    python -m agents.personalize --metric volume_vs_value # single metric
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .personalization import PersonalizationAgent, UserProfile


def clock(sec: int) -> str:
    return f"{sec // 60:02d}:{sec % 60:02d}"


def lines(insights, profile: UserProfile) -> list:
    out = []
    for i in PersonalizationAgent().select(insights, profile):
        d = i["display"]
        chip = f"  [context: {d['context_chip']['note_key']}]" if d["context_chip"] else ""
        star = "*" if d["favorite"] else " "
        out.append(f"{clock(i['clock']['start_sec'])} {star} {i['insight_type']:<20} {d['text']}{chip}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="path", default="out/insights.jsonl")
    ap.add_argument("--mode", default="casual", choices=("analyst", "casual"))
    ap.add_argument("--lang", default="en")
    ap.add_argument("--favorite")
    ap.add_argument("--player")
    ap.add_argument("--metric")
    a = ap.parse_args(argv)
    insights = [json.loads(x) for x in Path(a.path).read_text(encoding="utf-8").splitlines() if x.strip()]
    profile = UserProfile(mode=a.mode, language=a.lang, favorite_club=a.favorite, player_focus=a.player,
                          single_metric=a.metric)
    out = lines(insights, profile)
    print("\n".join(out))
    return out


if __name__ == "__main__":
    main()
