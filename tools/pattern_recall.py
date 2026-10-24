"""Pattern recovery: recall on planted cases and false-positive rate on unplanted team-matches, per
family, with Wilson intervals, over full leagues (20 teams, 380 matches).

    python -m tools.pattern_recall                 # seeds 2026-2030 at 1.0x and 0.5x -> docs/pattern-recall.md

Tuning seeds 2026-2028, hold-out 2029-2030 (thresholds were set on the tuning seeds only). League
data is generated once into data/generated-<seed>[-half]/full (gitignored) and reused. Serial, one
league in memory at a time; peak RSS is logged.

A planted case is a team-match of a planted team (or the team of a planted player) in which the
script completed at least NEED instances: the number the definition needs, so one planted foul
cannot make a three-foul pattern. A false positive is a finding for a team (player) with no motif
of that family planted. Every finding is also re-checked with the Verifier's independent recompute.
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

from data_gen.generate import main_full
from engine import patterns as P
from engine.tables import load, match_events

from .verifier_recall import wilson

ROOT = Path(__file__).resolve().parents[1]
TUNING = (2026, 2027, 2028)
HOLDOUT = (2029, 2030)
NEED = {"pat_counter_press": 2, "pat_rest_defence": 2, "pat_starved_finisher": 2, "pat_tactical_fouling": 3,
        "pat_set_piece_dependence": 3, "pat_direct_transition": 4, "pat_press_resistant": 12,
        "pat_pressed_presser": 4}
MIN_RECALL, MAX_FP = 0.60, 0.08
NAMES = {"pat_bait_switch": "Bait and switch (P1)", "pat_cutback": "Cut-back (P2)",
         "pat_flank_isolation": "Flank isolation (P3)", "pat_elastic_low_block": "Elastic low block (P4)",
         "pat_counter_press": "Counter-press (P5)", "pat_rest_defence": "Rest defence (P6)",
         "pat_starved_finisher": "Starved finisher (P7)", "pat_tactical_fouling": "Fouls after losses (P8)",
         "pat_pressed_presser": "Pressed presser (P11)", "pat_set_piece_dependence": "Set-piece dependence (P15)",
         "pat_press_resistant": "Press-resistant passer (P16)", "pat_direct_transition": "Direct transition (P17)"}


def rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 2**10


def generator_stamp() -> str:
    """Hash of the generator's source: a reused league is only valid for the code that wrote it."""
    import hashlib
    h = hashlib.sha256()
    for f in sorted((ROOT / "data_gen").glob("*.py")):
        h.update(f.name.encode() + f.read_bytes())
    return h.hexdigest()[:16]


def league_dir(seed: int, scale: float) -> Path:
    d = ROOT / "data" / f"generated-{seed}{'' if scale == 1.0 else '-half'}" / "full"
    stamp = d / "generator_stamp.txt"
    if not (d / "ground_truth.json").exists() or not stamp.exists() or stamp.read_text() != generator_stamp():
        main_full(seed, d, motif_scale=scale)       # overwrites every table and ground_truth.json
        stamp.write_text(generator_stamp())
    return d


def reset_caches():
    """Drop the engine's per-dataset caches (keyed by id) so only one league is ever in memory."""
    import gc

    from engine import claims, metrics, tables, threat, verifier
    from engine.patterns import helpers
    for cache in (tables._INDEX, threat._GRIDS, P._POS, helpers._BASE, verifier._EV, metrics._THREAT,
                  claims._SUBSETS):
        cache.clear()
    gc.collect()


def measure(seed: int, scale: float) -> dict:
    """Counts for one league: {family: {cases, hits, negatives, fps}}, recompute mismatches."""
    d = league_dir(seed, scale)
    ds = load(d)
    gt = json.loads((d / "ground_truth.json").read_text()).get("planted_motifs") or {"instances": {}, "teams": {},
                                                                                    "players": {}}
    by_code = {t["code"]: tid for tid, t in ds.teams.items()}
    planted = {f: set() for f in P.FAMILIES}
    for code, ms in gt["teams"].items():
        for f in ms:
            planted[f].add(by_code[code])
    for pid, v in gt["players"].items():
        for f in v["motifs"]:
            planted[f].add(by_code[v["team"]])
    out = {f: Counter() for f in P.FAMILIES}
    mismatches = 0
    for mid, evs in match_events(ds).items():
        m = ds.matches[mid]
        inst = Counter()
        for k, n in gt["instances"].get(mid, {}).items():
            f, code, _ = k.split("|")
            inst[(f, by_code[code])] += n
        for tid in (m["home_team_id"], m["away_team_id"]):
            found = P.detect_team(ds, mid, tid, families=P.FAMILIES)
            for f in found:
                subj = {"kind": "player", "id": f.player_id} if f.player_id else {"kind": "team", "id": f.team_id}
                scope = evs if f.window is None else [e for e in evs if f.window[0] <= e["clock_sec"] <= f.window[1]]
                vals, bad = P.recompute(ds, f.family, mid, subj, f.evidence, scope, f.window)
                if bad or vals is None or any(abs(vals[k] - v) > 1e-9 for k, v in f.values.items() if k in vals):
                    mismatches += 1
            fams = {f.family for f in found}
            for fam in P.FAMILIES:
                c = out[fam]
                if tid in planted[fam]:
                    if inst[(fam, tid)] >= NEED.get(fam, 1):
                        c["cases"] += 1
                        c["hits"] += fam in fams
                else:
                    c["negatives"] += 1
                    c["fps"] += fam in fams
    return {"counts": {f: dict(c) for f, c in out.items()}, "mismatches": mismatches, "matches": len(ds.matches)}


def pool(runs: dict, seeds, scale) -> dict:
    tot = {f: Counter() for f in P.FAMILIES}
    for s in seeds:
        for f, c in runs[(s, scale)]["counts"].items():
            tot[f].update(c)
    return tot


def _rate(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]" if n else "no cases"


def status(tune, hold) -> str:
    ok = all(c["cases"] and c["hits"] / c["cases"] >= MIN_RECALL and c["fps"] / max(c["negatives"], 1) <= MAX_FP
             for c in (tune, hold))
    return "validated" if ok else "experimental"


def report(runs: dict, peak: float, seconds: float) -> str:
    tune, hold = pool(runs, TUNING, 1.0), pool(runs, HOLDOUT, 1.0)
    half = pool(runs, TUNING + HOLDOUT, 0.5)
    lines = ["# Pattern recall", "",
             "Generated by `python -m tools.pattern_recall` (do not edit by hand). Full leagues: 20 teams, 380",
             "matches each. Tuning seeds 2026-2028, hold-out 2029-2030; thresholds were set on tuning seeds only.",
             f"Bar: recall >= {MIN_RECALL:.2f} and false-positive rate <= {MAX_FP:.0%} on both; otherwise "
             "**experimental**.",
             "Intervals are 95% Wilson intervals. Claim level: the detector (whose findings the Verifier's",
             "independent recompute re-checks). Pipeline level (what the stream surfaces) is in",
             "docs/pattern-diversity.md.", "",
             "| Pattern | Status | Recall, tuning | Recall, hold-out | FP rate, tuning | FP rate, hold-out "
             "| Recall at 0.5x strength (all seeds) |",
             "|---|---|---|---|---|---|---|"]
    for f in P.FAMILIES:
        t, h, x = tune[f], hold[f], half[f]
        lines.append(f"| {NAMES[f]} | {status(t, h)} | {_rate(t['hits'], t['cases'])} | {_rate(h['hits'], h['cases'])} "
                     f"| {_rate(t['fps'], t['negatives'])} | {_rate(h['fps'], h['negatives'])} "
                     f"| {_rate(x['hits'], x['cases'])} |")
    mism = sum(r["mismatches"] for r in runs.values())
    lines += ["", f"Detector versus independent recompute: {mism} mismatches over every finding of the "
              f"{len(runs)} leagues.", "",
              f"Run: {len(runs)} leagues, {seconds:.0f} s, peak RSS {peak:.0f} MB (one league in memory at a time).",
              ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, nargs="*", default=list(TUNING + HOLDOUT))
    ap.add_argument("--scales", type=float, nargs="*", default=[1.0, 0.5])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "pattern-recall.md")
    ap.add_argument("--json", type=Path, default=ROOT / "docs" / "data" / "pattern_recall.json")
    a = ap.parse_args(argv)
    t0, runs = time.time(), {}
    for scale in a.scales:
        for seed in a.seeds:
            runs[(seed, scale)] = measure(seed, scale)
            reset_caches()
            print(f"seed {seed} scale {scale}: done, peak RSS {rss_mb():.0f} MB", flush=True)
    peak = rss_mb()
    a.json.parent.mkdir(parents=True, exist_ok=True)
    a.json.write_text(json.dumps({f"{s}@{x}": r for (s, x), r in runs.items()}, indent=1, sort_keys=True) + "\n")
    if set(TUNING + HOLDOUT) <= set(a.seeds) and {1.0, 0.5} <= set(a.scales):
        a.out.write_text(report(runs, peak, time.time() - t0))
        print(f"wrote {a.out}")
    else:
        print(report(runs, peak, time.time() - t0))


if __name__ == "__main__":
    main()
