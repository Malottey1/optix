"""Multi-seed robustness: does the realism and trap recovery hold beyond the one default seed?

    python -m tools.robustness                      # writes docs/robustness.md
    python -m tools.robustness --jobs 4 --out /tmp/robustness.md

Four parts, every league generated fresh (no network, nothing written under data/):
  1. the small league under 10 seeds: how many seeds put each calibration target in range;
  2. the full league under 3 seeds: targets in range, planted-pattern recovery by type,
     champion and bottom points;
  3. the showcase seed search (from offset 0) under 3 generator seeds: the margin of every trap
     threshold in the match it finds;
  4. the Verifier's trap rules pooled over the 3 full leagues: recall and false-fire rate with
     the number of true cases.

This is an evaluation harness like tests/: it scores the engine against the generator's ground
truth (taken from the generator's return value). engine/ and agents/ never see that truth.
"""
from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from data_gen import calibration, traps
from data_gen.config import SHOWCASE_PLAYER_TRAITS
from data_gen.generate import build_showcase, main_full, make_players, showcase_reference

ROOT = Path(__file__).resolve().parent.parent
SMALL_SEEDS = tuple(range(2026, 2036))
FULL_SEEDS = (2026, 2027, 2028)
# extra full leagues used only to pool the Verifier: 3 leagues give about 60-90 true cases for the
# match rules, 5 put both above 75 (the player rules have 4 plants per league, so they stay small)
VERIFIER_EXTRA_SEEDS = (2029, 2030)
SHOWCASE_SEEDS = (2026, 2027, 2028)
FLAG_FAILS = 2                      # list targets that fail on more than this many small seeds
RULES = ("shot_spam", "field_tilt_with_lead", "set_piece_inflation", "wide_forward_passes")


def _small_job(seed: int) -> dict:
    from tools.realism_report import small_league
    res = calibration.check(calibration.season_stats(small_league(seed)))
    return {k: dict(applicable=r["applicable"], passed=r["passed"], measured=r["measured"])
            for k, r in res.items()}


def _points(matches: dict) -> dict:
    pts = Counter()
    for m in matches.values():
        h, a, hs, as_ = m["home_team_id"], m["away_team_id"], m["home_score"], m["away_score"]
        pts[h] += 3 if hs > as_ else 1 if hs == as_ else 0
        pts[a] += 3 if as_ > hs else 1 if hs == as_ else 0
    return pts


def _recovery(ds, gt) -> dict:
    """Planted-pattern recovery by type, with the same checks as tests/test_full_league.py."""
    from engine import metrics as M
    from engine.profiles import bracket_shift, soft_lane
    from engine.tables import score_diff, team_events
    from tests.soft_lane_truth import true_soft_lane_effect
    from tests.test_full_league import RECOVERABLE_EFFECT_PP

    out = {}
    lanes, false_pos, unplanted = [], [], 0
    for code, t in gt["teams"].items():
        got = soft_lane(ds, t["team_id"])
        if t["weak_lane_attacker_pov"] is None:
            unplanted += 1
            if got is not None:
                false_pos.append(code)
            continue
        eff = true_soft_lane_effect(ds, t["team_id"], t["weak_lane_attacker_pov"], t["weak_strength"])
        lanes.append(dict(code=code, strength=t["weak_strength"], effect_pp=round(eff["effect_pp_low"], 1),
                          recoverable=eff["effect_pp_low"] >= RECOVERABLE_EFFECT_PP,
                          found=got is not None and got["lane"] == t["weak_lane_attacker_pov"]))
    out["soft_lane"] = dict(lanes=lanes, false_pos=false_pos, unplanted=unplanted)

    ranked = [p for p, _ in M.forward_passes_by_player(ds.events).value]
    vp, cs = [], []
    for pid, v in gt["planted_players"].items():
        ev = team_events(ds, v["team"])
        code = ds.code(v["team"])
        if v["trap"] == "volume_passer":
            team_rank = [p for p in ranked if ds.players[p]["team_id"] == v["team"]].index(pid) + 1
            wide = M.forward_passes_wide_share(ev, v["team"], pid).detail["wide_share"]
            vp.append(dict(code=code, team_rank=team_rank, top_pct=round(100 * (ranked.index(pid) + 1) / len(ranked), 1),
                           wide_share=round(wide, 3),
                           found=team_rank == 1 and ranked.index(pid) + 1 <= 0.10 * len(ranked) and wide >= 0.8))
        elif v["trap"] == "corner_specialist":
            c = M.chances_created(ev, ds.passes, v["team"], pid)
            cs.append(dict(code=code, set_piece=c.detail["set_piece"], open_play=c.detail["open_play"],
                           found=c.detail["set_piece"] > c.detail["open_play"]))
    out["volume_passer"], out["corner_specialist"] = vp, cs

    by_id = {e["event_id"]: e for e in ds.events}
    tot, low = Counter(), Counter()
    for eid, s in ds.shots.items():
        e = by_id[eid]
        if score_diff(e, e["team_id"]) < 0:
            tot[e["team_id"]] += 1
            low[e["team_id"]] += s["xg"] <= 0.08
    league_low = sum(low.values()) / sum(tot.values())
    spam, deep = [], []
    for code, trs in gt["team_traps"].items():
        tid = gt["teams"][code]["team_id"]
        for tr in trs:
            if tr["trap"] == "shot_spam":
                share = low[tid] / tot[tid]
                spam.append(dict(code=code, share=round(share, 3), league=round(league_low, 3), found=share > league_low))
            elif tr["trap"] == "sit_deep_when_leading":
                s = bracket_shift(ds, tid)["field_tilt"]
                deep.append(dict(code=code, delta=round(s["delta"], 3), league=round(s["league_delta"], 3),
                                 found=s["delta"] < s["league_delta"]))
    out["shot_spam"], out["sit_deep_when_leading"] = spam, deep
    return out


def _full_job(seed: int) -> dict:
    from engine.tables import load
    from tests.test_verifier_full import _counts
    from tests.test_full_league import _tables
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        gt = main_full(seed, out)
        gen_sec = time.perf_counter() - t0
        res = calibration.check(calibration.season_stats(_tables(out)))
        ds = load(out)
        pts = sorted(_points(ds.matches).values())
        counts = _counts((ds, gt))
        recovery = _recovery(ds, gt)
    return dict(seed=seed, gen_sec=round(gen_sec, 1),
                targets={k: dict(applicable=r["applicable"], passed=r["passed"], measured=r["measured"])
                         for k, r in res.items()},
                champion=pts[-1], bottom=pts[0], recovery=recovery,
                verifier={f"{rule}|{int(trap)}|{int(fired)}": n for (rule, trap, fired), n in counts.items()})


def _showcase_job(seed: int, max_tries: int) -> dict:
    t0 = time.perf_counter()
    players = make_players(seed, SHOWCASE_PLAYER_TRAITS)
    try:
        sim, checks, s, tries = build_showcase(seed, players, max_tries=max_tries, start=0,
                                               reference_completion=showcase_reference(seed))
    except RuntimeError:
        return dict(seed=seed, found=False, tries=max_tries, sec=round(time.perf_counter() - t0, 1))
    return dict(seed=seed, found=True, sim_seed=s, tries=tries, score=[sim.score["t_aur"], sim.score["t_nor"]],
                margins=traps.trap_margins(checks), sec=round(time.perf_counter() - t0, 1))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, c - h), min(1.0, c + h))


def _yes(rows) -> str:
    return f"{sum(r['found'] for r in rows)}/{len(rows)}"


def _pooled_table(full: list) -> list:
    pooled = Counter()
    for f in full:
        for key, n in f["verifier"].items():
            rule, trap, fired = key.split("|")
            pooled[(rule, trap == "1", fired == "1")] += n
    L = ["| Rule | True cases | Recall | 95% CI | Non-trap cases | False-fire rate | 95% CI | Precision | Per-seed recall |",
         "|---|---|---|---|---|---|---|---|---|"]
    for rule in RULES:
        tp, fn = pooled[(rule, True, True)], pooled[(rule, True, False)]
        fp, tn = pooled[(rule, False, True)], pooled[(rule, False, False)]
        rl, rh = wilson(tp, tp + fn)
        fl, fh = wilson(fp, fp + tn)
        per = []
        for f in full:
            v = f["verifier"]
            a, b = v.get(f"{rule}|1|1", 0), v.get(f"{rule}|1|0", 0)
            per.append(f"{a}/{a + b}")
        L.append(f"| {rule} | {tp + fn} | {tp / max(1, tp + fn):.2f} | {rl:.2f}-{rh:.2f} | {fp + tn} | "
                 f"{fp / max(1, fp + tn):.3f} | {fl:.3f}-{fh:.3f} | {tp / max(1, tp + fp):.2f} | {', '.join(per)} |")
    return L


def render(small: dict, full: list, showcase: list, extra: list = ()) -> str:
    L = ["# Multi-seed robustness", "",
         "Generated by `python -m tools.robustness`. Every league is generated fresh in a temporary "
         "directory; ranges and allowances are those of `data_gen/calibration.py` (a value passes inside "
         "[lo - a, hi + a], a = 2 sd / sqrt(n)).", ""]

    # 1. small league
    seeds = sorted(small)
    L += [f"## 1. Small league, {len(seeds)} seeds ({seeds[0]}-{seeds[-1]})", "",
          "Seeds in range per target (season-shape targets need 20 teams and are n/a here). "
          "Min and max are the measured values across the seeds.", "",
          "| Target | Range | In range | Min | Max |", "|---|---|---|---|---|"]
    flagged = []
    for k, t in calibration.TARGETS.items():
        rows = [small[s][k] for s in seeds]
        if not rows[0]["applicable"]:
            L.append(f"| {k} | {t['lo']}-{t['hi']} | n/a | | |")
            continue
        ok = sum(r["passed"] for r in rows)
        vals = [r["measured"] for r in rows if r["measured"] is not None]
        L.append(f"| {k} | {t['lo']}-{t['hi']} | {ok}/{len(rows)} | {_fmt(min(vals))} | {_fmt(max(vals))} |")
        if len(rows) - ok > FLAG_FAILS:
            fails = [s for s in seeds if not small[s][k]["passed"]]
            flagged.append((k, len(rows) - ok, fails))
    applicable = [k for k in calibration.TARGETS if small[seeds[0]][k]["applicable"]]
    all_ok = sum(all(small[s][k]["passed"] for k in applicable) for s in seeds)
    L += ["", f"{len(applicable)} targets apply to the small league; {all_ok}/{len(seeds)} seeds have every one in range.", "",
          f"Targets failing on more than {FLAG_FAILS} of {len(seeds)} seeds: "
          + ("; ".join(f"**{k}** ({n} fails: seeds {', '.join(map(str, f))})" for k, n, f in flagged) or "none") + ".", ""]

    # 2. full league
    L += [f"## 2. Full league, {len(full)} seeds", "",
          "| Seed | Targets in range | Outside range | Soft lanes (true effect >= 7 pp) | Soft lanes (all planted) "
          "| Soft-lane false positives | Volume passers | Corner specialists | Shot-spam teams | Deep-when-leading teams "
          "| Champion pts | Bottom pts | Generation s |",
          "|" + "---|" * 13]
    for f in full:
        tg = f["targets"]
        out = sorted(k for k, r in tg.items() if r["applicable"] and not r["passed"])
        n_app = sum(r["applicable"] for r in tg.values())
        rc = f["recovery"]
        sl = rc["soft_lane"]
        rec = [x for x in sl["lanes"] if x["recoverable"]]
        L.append(f"| {f['seed']} | {n_app - len(out)}/{n_app} | {', '.join(out) or 'none'} | {_yes(rec)} | {_yes(sl['lanes'])} "
                 f"| {len(sl['false_pos'])}/{sl['unplanted']} | {_yes(rc['volume_passer'])} | {_yes(rc['corner_specialist'])} "
                 f"| {_yes(rc['shot_spam'])} | {_yes(rc['sit_deep_when_leading'])} | {f['champion']} | {f['bottom']} | {f['gen_sec']} |")
    for f in full:
        out = {k: r for k, r in f["targets"].items() if r["applicable"] and not r["passed"]}
        for k, r in out.items():
            t = calibration.TARGETS[k]
            L.append(f"\n- Seed {f['seed']}: {k} measured {_fmt(r['measured'])}, range {t['lo']}-{t['hi']}.")
    L += ["", "Soft lanes by plant (true effect is the lower bound from the generator's own pass "
          "probabilities, tests/soft_lane_truth.py; found = the engine's soft_lane names the planted lane):", "",
          "| Team | Strength | " + " | ".join(f"Seed {f['seed']} effect pp / found" for f in full) + " |",
          "|" + "---|" * (2 + len(full))]
    for i, lane in enumerate(full[0]["recovery"]["soft_lane"]["lanes"]):
        cells = []
        for f in full:
            x = f["recovery"]["soft_lane"]["lanes"][i]
            cells.append(f"{x['effect_pp']} / {'yes' if x['found'] else 'no'}")
        L.append(f"| {lane['code']} | {lane['strength']} | " + " | ".join(cells) + " |")
    misses = []
    for f in full:
        rc = f["recovery"]
        for kind in ("volume_passer", "corner_specialist", "shot_spam", "sit_deep_when_leading"):
            for x in rc[kind]:
                if not x["found"]:
                    misses.append(f"seed {f['seed']} {kind} {x['code']}: {json.dumps({k: v for k, v in x.items() if k not in ('code', 'found')})}")
        if rc["soft_lane"]["false_pos"]:
            misses.append(f"seed {f['seed']} soft-lane false positives: {', '.join(rc['soft_lane']['false_pos'])}")
    L += ["", "Player and team plant misses: " + ("; ".join(misses) if misses else "none") + ".", ""]

    # 3. showcase
    L += [f"## 3. Showcase seed search, {len(showcase)} generator seeds", "",
          f"Search from offset 0; a match qualifies when all five traps fire with every threshold cleared by "
          f"at least {100 * 0.10:.0f}% inside the realism envelope (data_gen/generate.py).", ""]
    found = [s for s in showcase if s["found"]]
    if found:
        keys = list(found[0]["margins"])
        L += ["| Trap threshold | " + " | ".join(f"Seed {s['seed']}" for s in found) + " |",
              "|" + "---|" * (1 + len(found))]
        for k in keys:
            m = found[0]["margins"][k]
            L.append(f"| {k} ({m['kind']} {m['threshold']}) | "
                     + " | ".join(f"{s['margins'][k]['value']} (+{100 * s['margins'][k]['margin']:.0f}%)" for s in found) + " |")
        L.append("| minimum margin | " + " | ".join(f"{100 * min(m['margin'] for m in s['margins'].values()):.0f}%" for s in found) + " |")
        L.append("| score AUR-NOR | " + " | ".join(f"{s['score'][0]}-{s['score'][1]}" for s in found) + " |")
        L.append("| seeds tried | " + " | ".join(str(s["tries"]) for s in found) + " |")
        L.append("| search time s | " + " | ".join(str(s["sec"]) for s in found) + " |")
    for s in showcase:
        if not s["found"]:
            L.append(f"\n- Generator seed {s['seed']}: no qualifying match in {s['tries']} tries ({s['sec']} s).")
    L.append("")

    # 4. pooled verifier
    L += [f"## 4. Verifier trap rules pooled over {len(full)} full leagues (seeds {', '.join(str(f['seed']) for f in full)})", "",
          "Cases as in tests/test_verifier_full.py. Recall = fired / true cases; false-fire rate = fired / "
          "non-trap cases. Intervals are Wilson 95%.", ""] + _pooled_table(full)
    if extra:
        allf = list(full) + list(extra)
        L += ["", f"The same pooled over {len(allf)} full leagues (adding seeds "
              f"{', '.join(str(f['seed']) for f in extra)}, used for this table only):", ""] + _pooled_table(allf)
    L.append("")
    return "\n".join(L)


def _fmt(v):
    if v is None:
        return "–"
    return f"{v:.3f}" if abs(v) < 10 else f"{v:.1f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "robustness.md")
    ap.add_argument("--json", type=Path, default=None, help="also write the raw results here")
    ap.add_argument("--reuse", action="store_true", help="reuse results already in --json")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--showcase-max-tries", type=int, default=6000)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    cache = json.loads(a.json.read_text()) if a.reuse and a.json and a.json.exists() else {}
    have_full = {f["seed"]: f for f in cache.get("full", [])}
    have_sc = {s["seed"]: s for s in cache.get("showcase", [])}
    have_small = {int(k): v for k, v in cache.get("small", {}).items()}
    with ProcessPoolExecutor(a.jobs) as ex:
        # longest jobs first; anything in the --reuse cache is not recomputed
        sc = {s: ex.submit(_showcase_job, s, a.showcase_max_tries) for s in SHOWCASE_SEEDS if s not in have_sc}
        fu = {s: ex.submit(_full_job, s) for s in FULL_SEEDS + VERIFIER_EXTRA_SEEDS if s not in have_full}
        sm = {s: ex.submit(_small_job, s) for s in SMALL_SEEDS if s not in have_small}
        have_small.update({s: f.result() for s, f in sm.items()})
        have_full.update({s: f.result() for s, f in fu.items()})
        have_sc.update({s: f.result() for s, f in sc.items()})
    small = {s: have_small[s] for s in SMALL_SEEDS}
    full = [have_full[s] for s in FULL_SEEDS]
    extra = [have_full[s] for s in VERIFIER_EXTRA_SEEDS]
    showcase = [have_sc[s] for s in SHOWCASE_SEEDS]
    if a.json:
        a.json.write_text(json.dumps(dict(small=small, full=full + extra, showcase=showcase), indent=1))
    a.out.write_text(render(small, full, showcase, extra))
    print(f"wrote {a.out} in {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
