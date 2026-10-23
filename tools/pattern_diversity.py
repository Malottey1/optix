"""Stream diversity of tactical pattern cards, with and without novelty ranking, and pipeline-level
recall (planted cases the stream actually surfaced).

    python -m tools.pattern_diversity            # seeds 2026-2028, small league -> docs/pattern-diversity.md

Every match of the 40-match season is streamed in date order through the agents (template
phraser). "With novelty": each match gets the families (and magnitudes) surfaced for each team in
its earlier matches (agents/analyst.py rank_candidates); "without": no history. A surfaced pattern
card is a published insight of type tactical_pattern; its family is the payload's family.

Bars (the brief): the most common family is at most 25% of pattern cards, and per-team repetition
(the share of a team's pattern cards whose family was also surfaced for that team in its previous
match) is at most 40% for every team.
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

from agents.stream import InsightStream
from data_gen.generate import make_players, small_season, write_dataset
from data_gen.config import MOTIF_SCALE
from engine import patterns as P
from engine.tables import load

from .pattern_recall import NEED, reset_caches

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (2026, 2027, 2028)
MAX_FAMILY_SHARE, MAX_REPEAT = 0.25, 0.40


def season_dir(seed: int) -> Path:
    d = ROOT / "data" / f"generated-{seed}" / "season"
    if not (d / "matches.csv").exists():
        players = make_players(seed)
        sims, fixtures = small_season(seed, players, MOTIF_SCALE)
        write_dataset(d, sims, players, fixtures)
        from data_gen.generate import planted_motifs, TEAMS
        pm = planted_motifs(sims, TEAMS, players, MOTIF_SCALE)
        (d / "ground_truth.json").write_text(json.dumps({"planted_motifs": pm}, indent=1))
    return d


def run_season(seed: int, novelty: bool) -> dict:
    d = season_dir(seed)
    ds = load(d)
    gt = json.loads((d / "ground_truth.json").read_text())["planted_motifs"]
    by_code = {t["code"]: tid for tid, t in ds.teams.items()}
    order = sorted(ds.matches, key=lambda mid: (ds.matches[mid].get("date") or "", mid))
    history: dict = {}
    cards = []                                    # (match, team, family)
    played = []                                   # (match, team) in date order
    cases = Counter()
    hits = Counter()
    for mid in order:
        s = InsightStream(ds, mid, history=history if novelty else None)
        s.run()
        fams = {(i["teams"]["primary"], i["payload"]["family"]) for i in s.insights
                if i["insight_type"] == "tactical_pattern" and i["payload"].get("family")}
        cards += [(mid, by_code[c], f) for c, f in sorted(fams)]
        for tid in (ds.matches[mid]["home_team_id"], ds.matches[mid]["away_team_id"]):
            played.append((mid, tid))
            history.setdefault(tid, []).append({f: mag for (f, t, _), mag in s.orc.analyst.shown.items() if t == tid})
        inst = Counter()
        for k, n in gt["instances"].get(mid, {}).items():
            f, code, _ = k.split("|")
            inst[(f, by_code[code])] += n
        for (f, tid), n in inst.items():
            if n >= NEED.get(f, 1):
                cases[f] += 1
                hits[f] += (ds.code(tid), f) in fams
    return dict(cards=cards, cases=dict(cases), hits=dict(hits), played=played,
                teams={tid: ds.code(tid) for tid in ds.teams})


def summarise(runs: list) -> dict:
    fam = Counter(f for r in runs for _, _, f in r["cards"])
    total = sum(fam.values())
    repeat = Counter()
    per_team = Counter()
    for r in runs:
        by_match: dict = {}
        for mid, tid, f in r["cards"]:
            by_match.setdefault((mid, tid), set()).add(f)
        last: dict = {}
        for mid, tid in r["played"]:                # each team's own matches, in date order
            fs = by_match.get((mid, tid), set())
            code = r["teams"][tid]
            per_team[code] += len(fs)
            repeat[code] += len(fs & last.get(tid, set()))
            last[tid] = fs
    cases = Counter()
    hits = Counter()
    for r in runs:
        cases.update(r["cases"])
        hits.update(r["hits"])
    return dict(total=total, families=dict(fam.most_common()),
                top_share=(fam.most_common(1)[0][1] / total) if total else 0.0,
                repeat={t: (repeat[t] / n if n else 0.0, repeat[t], n) for t, n in sorted(per_team.items())},
                recall={f: (hits[f], cases[f]) for f in P.FAMILIES if cases[f]})


def report(on: dict, off: dict, seconds: float, peak: float) -> str:
    def block(name, s):
        top = max(s["families"], key=s["families"].get) if s["families"] else "-"
        worst = max(s["repeat"].items(), key=lambda kv: kv[1][0]) if s["repeat"] else ("-", (0, 0, 0))
        ok = s["top_share"] <= MAX_FAMILY_SHARE and worst[1][0] <= MAX_REPEAT
        lines = [f"## {name}", "",
                 f"Pattern cards: {s['total']}. Most common family: {top}, {s['top_share']:.1%} (bar {MAX_FAMILY_SHARE:.0%}). "
                 f"Highest per-team repetition: {worst[0]}, {worst[1][0]:.1%} ({worst[1][1]} of {worst[1][2]}; "
                 f"bar {MAX_REPEAT:.0%}). Bars met: {'yes' if ok else 'no'}.", "",
                 "| Family | Cards | Share |", "|---|---|---|"]
        lines += [f"| {f} | {n} | {n / s['total']:.1%} |" for f, n in s["families"].items()]
        lines += ["", "| Team | Repeated from the previous match | Cards | Share |", "|---|---|---|---|"]
        lines += [f"| {t} | {k} | {n} | {v:.1%} |" for t, (v, k, n) in s["repeat"].items()]
        lines += ["", "| Family | Pipeline recall (planted cases the stream surfaced) |", "|---|---|"]
        lines += [f"| {f} | {h}/{n} = {h / n:.2f} |" for f, (h, n) in s["recall"].items()]
        return lines
    out = ["# Pattern card diversity", "",
           "Generated by `python -m tools.pattern_diversity` (do not edit by hand). Small league (5 teams, 40",
           f"matches) for seeds {', '.join(map(str, SEEDS))}, every match streamed in date order with the template "
           "phraser.", "",
           "A card is a published tactical_pattern insight: a pattern claim, or a naive claim a pattern rule "
           "rewrote (its family is the rule's). Families switched off as experimental "
           f"({', '.join(f for f in P.FAMILIES if not P.enabled(f)) or 'none'}) publish no claim of their own, "
           "so their rows count rewritten naive claims only.", ""]
    out += block("With novelty ranking (history of each team's previous matches)", on) + [""]
    out += block("Without novelty ranking (no history)", off) + [""]
    out += [f"Run: {seconds:.0f} s, peak RSS {peak:.0f} MB.", ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, nargs="*", default=list(SEEDS))
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "pattern-diversity.md")
    a = ap.parse_args(argv)
    t0 = time.time()
    on, off = [], []
    for seed in a.seeds:
        on.append(run_season(seed, True))
        reset_caches()
        off.append(run_season(seed, False))
        reset_caches()
        print(f"seed {seed}: done", flush=True)
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = r / 2**20 if sys.platform == "darwin" else r / 2**10
    text = report(summarise(on), summarise(off), time.time() - t0, peak)
    a.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
