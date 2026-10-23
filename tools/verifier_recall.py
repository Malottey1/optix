"""Recall, false-fire rate and outcome-based precision of the match-level Verifier rules
(shot_spam, field_tilt_with_lead) over several full leagues, with every planted miss classified.

    python -m tools.verifier_recall --json F            # measure seeds 2026-2030 (resumes from F)
    python -m tools.verifier_recall --json F --out docs/verifier-recall.md

Memory: one league at a time, each in a fresh child process (freed when it exits); the stream's
per-match caches are dropped after every match; results are written to --json after every league,
so a crash loses at most the league in progress and a rerun skips the leagues already in F.

Two levels, on the cases of tests/verifier_cases.py:
  * claim level: one full-match claim per (match, team), as tests/test_verifier_full.py builds it;
  * pipeline level: the claims the Analyst proposes while streaming the match
    (agents/orchestrator.py); a case is caught when any of them fires the rule.
For every claim scope the run records the rule inputs, so the rule versions compared in the
report are re-evaluated from the same recorded scopes (the Analyst's windows do not depend on the
rules; v2 also drops the full-time windows the old cooldown did not allow):
  v2  before: shot_spam on every shot; field tilt box-entry share over the whole scope;
  v3  shot_spam on non-penalty shots; box-entry share over the trailing part; full-time window;
  v4  = v3 plus the chaser-threat condition of field_tilt_with_lead (the current code).
The current code's own verdicts are recorded too and must agree with the v4 re-evaluation.

A planted case the rule did not catch is classified (for v4, a case that v3 would have caught and
the chaser-threat condition held back counts as (c) and is also shown as "threat N"):
  (a) coverage gap: no claim of the metric for that team in that match;
  (b) window or scope: the rule's own conditions hold over the trailing spell, but no claim's
      scope kept the spell's pattern;
  (c) thresholds: a claim covered the spell, the case is detectable, and the rule did not fire
      over the spell either;
  (d) below detection (tests/verifier_cases.py): a miss is acceptable.

Outcome-based precision of field_tilt_with_lead (independent of the rule's inputs, which are
passes): for each fire, the chaser's non-penalty xG in the claim's scope against the league's
expectation for a side with the same time in each game state (league npxG per second while
leading / level / trailing, times the subject's seconds in each state in the scope). ratio =
actual / expected (engine.metrics.chaser_threat). A fire is "justified" when ratio <= 1 (the
chaser created no more than an average side in that state: territory without threat, which is
what the caveat says), a "false positive" when ratio > the 75th percentile of the ratio over all
league scopes of the same length in which the subject trailed for at least half the time
(engine.metrics.chaser_threat_line), and "unclear" in between. v4 uses that same line as a rule
condition, so for v4 the label is no longer independent: it can only show that the condition is
applied (no false positives by construction). The independent evidence is the v2 / v3 labels.
Evaluation harness like tests/: it reads the generator's ground truth; engine/ and agents/ never do.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import tempfile
import time
from collections import Counter
from pathlib import Path

SEEDS = (2026, 2027, 2028, 2029, 2030)
TUNE, HOLD = (2026, 2027, 2028), (2029, 2030)
RULES = ("shot_spam", "field_tilt_with_lead")
WINDOW_SEC = 1800
LOW_XG, MIN_SHOTS, MIN_LOW, MAX_MEAN = 0.08, 12, 0.65, 0.08
MIN_TILT, MIN_TRAIL, MAX_ENTRY = 0.60, 0.5, 0.18


# ---------- rule versions, re-evaluated from recorded scope features ----------

def ss_v2(sh) -> bool:
    """shot_spam before: every shot counts, penalties included."""
    n = len(sh)
    return n >= MIN_SHOTS and sum(x <= LOW_XG for x, _ in sh) / n >= MIN_LOW and sum(x for x, _ in sh) / n <= MAX_MEAN


def ss_v3(sh) -> bool:
    """shot_spam after: non-penalty shots only."""
    return ss_v2([s for s in sh if not s[1]])


def ft_v2(f) -> bool:
    """field_tilt_with_lead before: box-entry share over the whole scope."""
    n = f["own"]
    return bool(n) and n / (n + f["opp"]) >= MIN_TILT and f["town"] / n >= MIN_TRAIL and f["box"] / n <= MAX_ENTRY


def ft_v3(f) -> bool:
    """field_tilt_with_lead after: box-entry share over the trailing part of the scope."""
    n = f["own"]
    return (bool(n) and n / (n + f["opp"]) >= MIN_TILT and f["town"] / n >= MIN_TRAIL
            and f["tbox"] / f["town"] <= MAX_ENTRY)


def _ratio(f, q="") -> float | None:
    return f[q + "npxg"] / f[q + "expected"] if f[q + "expected"] else None


def ft_v4(f) -> bool:
    """field_tilt_with_lead now: v3, and the chaser did not clearly out-create an average chaser
    from real chances (shots above the low-xG line)."""
    r = _ratio(f, "q_")
    return ft_v3(f) and (f["q_line"] is None or r is None or r <= f["q_line"])


def outcome(f, q="") -> str:
    """Outcome label of one fire: q="" total non-penalty xG (the label as specified), q="q_" xG
    from shots above the low-xG line only."""
    r = _ratio(f, q) or 0.0
    line = f[q + "line"]
    return "justified" if r <= 1 else "false positive" if line is not None and r > line else "unclear"


VERSIONS = {"shot_spam": {"v2": ss_v2, "v3": ss_v3, "v4": ss_v3},
            "field_tilt_with_lead": {"v2": ft_v2, "v3": ft_v3, "v4": ft_v4}}
CURRENT = "v4"


# ---------- recording ----------

def _features(ds, evs, tid, metric, length) -> dict:
    """Rule inputs over one scope (length None = full match), plus the outcome measure (field tilt)."""
    from engine import metrics as M
    from engine.tables import score_diff
    from engine.zones import in_box
    if metric == "xg":
        return dict(shots=[(ds.shots[e["event_id"]]["xg"], ds.shots[e["event_id"]]["shot_type"] == "penalty")
                           for e in evs if e["event_type"] == "shot" and e["team_id"] == tid])
    th = M.chaser_threat(evs, ds.shots, tid, M.state_npxg_rates(ds))
    tq = M.chaser_threat(evs, ds.shots, tid, M.state_npxg_rates(ds, LOW_XG), LOW_XG)
    f = dict(own=0, opp=0, box=0, town=0, topp=0, tbox=0,
             npxg=th.detail["npxg"], expected=th.detail["expected"], line=M.chaser_threat_line(ds, length),
             q_npxg=tq.detail["npxg"], q_expected=tq.detail["expected"],
             q_line=M.chaser_threat_line(ds, length, 0.75, LOW_XG))
    for e in evs:
        tr = score_diff(e, tid) < 0
        if e["event_type"] != "pass" or e["outcome"] != "success":
            continue
        if e["team_id"] == tid:
            if e["x_start"] >= M.FINAL_THIRD_X:
                f["own"] += 1
                f["town"] += tr
            if in_box(e["x_end"], e["y_end"]) and not in_box(e["x_start"], e["y_start"]):
                f["box"] += 1
                f["tbox"] += tr
        elif e["opponent_team_id"] == tid and e["x_start"] >= M.FINAL_THIRD_X:
            f["opp"] += 1
            f["topp"] += tr
    return f


def measure(seed: int) -> dict:
    from data_gen.generate import main_full
    from engine.claims import build_claim
    from engine.tables import load, match_events
    from engine.verifier import verdict
    from tests.verifier_cases import cases, drop_match_caches, pipeline_claims

    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as d:
        gt = main_full(seed, Path(d))
        ds = load(d)
    pipe = {}
    for mid in match_events(ds):
        pipe[mid] = pipeline_claims(ds, mid)
        drop_match_caches(ds)
    rows = []
    for c in cases(ds, gt):
        if c["planted"] is None:
            continue
        rule, metric, mid, tid = c["rule"], c["metric"], c["match_id"], c["team_id"]
        evs = match_events(ds)[mid]
        claim = build_claim(ds, metric, "match", {"kind": "team", "id": tid}, match_id=mid,
                            template_key=f"{metric}.stat", param_values=("amount",))
        wins = pipe[mid].get((tid, metric), [])
        m = ds.matches[mid]
        row = dict(rule=rule, match_id=mid, team=ds.code(tid), planted=c["planted"], reason=c["reason"],
                   end=evs[-1]["clock_sec"], claim=_features(ds, evs, tid, metric, None),
                   claim_fired=rule in verdict(claim, ds).rule_ids,
                   windows=[dict(window=w["window"], fired=rule in w["rules"],
                                 feat=_features(ds, [e for e in evs if w["window"][0] <= e["clock_sec"] <= w["window"][1]],
                                                tid, metric, w["window"][1] - w["window"][0])) for w in wins])
        if c["planted"]:
            opp = m["away_team_id"] if m["home_team_id"] == tid else m["home_team_id"]
            row.update(opp=ds.code(opp), spell={k: round(x, 3) for k, x in c["spell"].items()})
        rows.append(row)
    return dict(seed=seed, sec=round(time.perf_counter() - t0), rows=rows)


# ---------- analysis ----------

def _old_windows(row) -> list:
    """The windows the Analyst proposed before the full-time cooldown change: a full-time window
    proposed less than the regular cooldown after the previous one did not exist."""
    w = row["windows"]
    if row["rule"] == "field_tilt_with_lead" and len(w) >= 1 and w[-1]["window"][1] == row["end"]:
        prev = w[-2]["window"][1] if len(w) >= 2 else None
        if prev is not None and row["end"] - prev < WINDOW_SEC:
            return w[:-1]
    return w


def _spell_oracle(rule, sp) -> bool:
    if rule == "shot_spam":
        n = sp["shots"]
        return n >= MIN_SHOTS and sp["low_xg_shots"] / n >= MIN_LOW and sp["xg"] / n <= MAX_MEAN
    n = sp["f3_passes"]
    return bool(n) and sp["field_tilt"] >= MIN_TILT and sp["box_entries"] / n <= MAX_ENTRY


def evaluate(results, seeds, rule, level, version) -> dict:
    """Counts for one rule version: recall on true / all planted cases, the unplanted fire rate,
    miss classes and (field tilt) the outcome labels of every fire."""
    fn = VERSIONS[rule][version]
    out = dict(true=[0, 0], planted=[0, 0], unplanted=[0, 0], classes=Counter(), outcome=Counter(),
               unplanted_by_label=Counter(), q_outcome=Counter(), q_unplanted_by_label=Counter())
    for res in results:
        if res["seed"] not in seeds:
            continue
        for r in res["rows"]:
            if r["rule"] != rule:
                continue
            if level == "claim":
                scopes, recorded = [r["claim"]], [r["claim_fired"]]
            else:
                ws = _old_windows(r) if version == "v2" else r["windows"]
                scopes, recorded = [w["feat"] for w in ws], [w["fired"] for w in ws]
            if version == CURRENT:      # the current code's own verdicts, as recorded
                fires = [f for f, x in zip(scopes, recorded) if x]
            else:
                fires = [f for f in scopes if fn(f["shots"] if rule == "shot_spam" else f)]
            hit = bool(fires)
            for q in ("", "q_"):
                labels = [outcome(f, q) for f in fires] if rule == "field_tilt_with_lead" else []
                out[q + "outcome"].update(labels)
                if labels and not r["planted"]:     # a case is labelled by its worst fire
                    out[q + "unplanted_by_label"][next(x for x in ("false positive", "unclear", "justified")
                                                       if x in labels)] += 1
            if not r["planted"]:
                out["unplanted"][0] += hit
                out["unplanted"][1] += 1
                continue
            out["planted"][0] += hit
            out["planted"][1] += 1
            if not r["reason"]:
                out["true"][0] += hit
                out["true"][1] += 1
            if hit:
                cls = "caught"
            elif r["reason"]:
                cls = "d"
            elif not scopes:
                cls = "a"
            elif version == "v4" and rule == "field_tilt_with_lead" and any(ft_v3(f) for f in scopes):
                cls = "c"                   # the chaser-threat condition held the caveat back
                out["classes"]["threat"] += 1
            else:
                cls = "b" if _spell_oracle(rule, r["spell"]) else "c"
            out["classes"][cls] += 1
    return out


def check_current(results) -> list:
    """Cases where the recorded verdict of the current code disagrees with its re-evaluation."""
    bad = []
    for res in results:
        for r in res["rows"]:
            fn = VERSIONS[r["rule"]][CURRENT]
            g = (lambda f, fn=fn: fn(f["shots"])) if r["rule"] == "shot_spam" else fn
            if g(r["claim"]) != r["claim_fired"]:
                bad.append((res["seed"], r["match_id"], r["team"], r["rule"], "claim"))
            for w in r["windows"]:
                if g(w["feat"]) != w["fired"]:
                    bad.append((res["seed"], r["match_id"], r["team"], r["rule"], w["window"]))
    return bad


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, c - h), min(1.0, c + h))


def rate(k: int, n: int) -> str:
    """k/n with its Wilson 95% interval; a bare count when there are fewer than 40 cases."""
    lo, hi = wilson(k, n)
    if n < 40:
        return f"{k}/{n} [{lo:.2f}-{hi:.2f}]"
    return f"{k / n:.2f} [{lo:.2f}-{hi:.2f}] ({k}/{n})"


def render(results) -> str:
    seeds = sorted(r["seed"] for r in results)
    L = ["# Verifier recall (match-level rules)", "",
         f"Generated by `python -m tools.verifier_recall` on full leagues {', '.join(map(str, seeds))}. Cases and "
         "the true-case definition: `tests/verifier_cases.py`. Recall is k/n with a Wilson 95% interval "
         "(a count when there are fewer than 40 cases). Versions (all evaluated on the same recorded "
         "claim scopes): v2 = before the recall work; v3 = non-penalty shot_spam, trailing box-entry "
         "share and the full-time tilt window; v4 = v3 plus the chaser-threat condition (the current "
         "code). Seeds 2026-2028 were used to choose the changes; 2029-2030 are the hold-out.", "",
         "Unplanted fire rate: share of unplanted (match, team) cases on which the rule fires; the fired "
         "cases are split by the outcome label of the case's worst fire (J justified / U unclear / FP "
         "false positive). Outcome label (field tilt only): the chaser's non-penalty xG in the scope "
         "against the league expectation for the same time in each game state; justified <= 1x, false "
         "positive above the league's 75th percentile for scopes of that length, unclear in between. "
         "'Total xG' counts every non-penalty shot (the label as specified); 'chance xG' only shots "
         "above the 0.08 low-xG line. v4 uses the chance-xG line as a rule condition, so its zero "
         "chance-xG false positives hold by construction; the total-xG label stays independent of it.", ""]
    splits = (("2026-2028 (tune)", TUNE), ("2029-2030 (hold-out)", HOLD), ("all", tuple(seeds)))
    L += _reading(results, seeds)
    for level, title in (("claim", "Claim level: one full-match claim per team (tests/test_verifier_full.py)"),
                         ("pipeline", "Pipeline level: the claims the Analyst proposes while streaming")):
        L += [f"## {title}", "",
              "| Rule | Seeds | Version | Recall, true cases | Recall, all planted | Unplanted fire rate "
              "| Unplanted fired cases J / U / FP, total xG | same, chance xG | Misses a / b / c / d |",
              "|---|---|---|---|---|---|---|---|---|"]
        for rule in RULES:
            for name, ss in splits:
                for ver in (("v2", "v3") if rule == "shot_spam" else ("v2", "v3", "v4")):
                    s = evaluate(results, ss, rule, level, ver)
                    c, u = s["classes"], s["unplanted"]
                    th = f" (threat {c['threat']})" if c["threat"] else ""
                    lab = []
                    for q in ("", "q_"):
                        ub = s[q + "unplanted_by_label"]
                        lab.append(f"{ub['justified']} / {ub['unclear']} / {ub['false positive']} (FP "
                                   f"{ub['false positive'] / u[1]:.3f} of all)" if rule == "field_tilt_with_lead" else "–")
                    L.append(f"| {rule} | {name} | {ver} | {rate(*s['true'])} | {rate(*s['planted'])} | "
                             f"{u[0] / u[1]:.3f} ({u[0]}/{u[1]}) | {lab[0]} | {lab[1]} | "
                             f"{c['a']} / {c['b']} / {c['c']}{th} / {c['d']} |")
        L.append("")
    bad = check_current(results)
    L += [f"The {CURRENT} rows are the current code's own recorded verdicts. Recorded verdicts that disagree with "
          f"the {CURRENT} re-evaluation from the recorded features: {len(bad)}"
          + (f" ({', '.join(f'seed {b[0]} {b[1]} {b[2]}' for b in bad)})" if bad else "") + ".", ""]
    L += [f"## Examples of misses ({CURRENT}, pipeline level)", ""]
    for rule in RULES:
        rows = [(res["seed"], r) for res in results for r in res["rows"] if r["rule"] == rule and r["planted"]]
        fn = VERSIONS[rule][CURRENT]
        g = (lambda f, fn=fn: fn(f["shots"])) if rule == "shot_spam" else fn
        groups = {"a": [], "b": [], "c": [], "d": []}
        for seed, r in rows:
            if any(w["fired"] for w in r["windows"]):
                continue
            cls = ("d" if r["reason"] else "a" if not r["windows"]
                   else "c" if rule == "field_tilt_with_lead" and any(ft_v3(w["feat"]) for w in r["windows"])
                   else "b" if _spell_oracle(rule, r["spell"]) else "c")
            groups[cls].append((seed, r))
        for cls, ex in groups.items():
            if not ex:
                continue
            L += [f"**{rule}, category {cls}** ({len(ex)} cases)", ""]
            for seed, r in ex[:3]:
                L.append(f"- seed {seed} {r['match_id']} {r['team']} v {r['opp']}: trailing spell {json.dumps(r['spell'])}"
                         + (f"; {r['reason']}" if r["reason"] else "")
                         + "; claim windows " + (", ".join(str(tuple(w["window"])) for w in r["windows"]) or "none"))
            L.append("")
    return "\n".join(L)


def _reading(results, seeds) -> list:
    """The headline figures in words, computed from the results (no number typed by hand)."""
    ft = "field_tilt_with_lead"
    cur = {(lvl, name): evaluate(results, ss, ft, lvl, CURRENT)
           for lvl in ("claim", "pipeline") for name, ss in (("tune", TUNE), ("hold", HOLD), ("all", tuple(seeds)))}
    old = evaluate(results, tuple(seeds), ft, "pipeline", "v2")
    lines = {"match": set(), "window": set()}
    for res in results:
        for r in res["rows"]:
            if r["rule"] == ft:
                lines["match"].add(r["claim"]["q_line"])
                lines["window"].update(w["feat"]["q_line"] for w in r["windows"]
                                       if w["window"][1] - w["window"][0] == WINDOW_SEC)
    span = {k: f"{min(v):.2f}-{max(v):.2f}" for k, v in lines.items() if v}

    def rec(lvl, name):
        k, n = cur[(lvl, name)]["true"]
        lo, hi = wilson(k, n)
        return f"{k / n:.2f} [{lo:.2f}-{hi:.2f}], n={n}"

    def split(s):
        u, b = s["unplanted"][1], s["unplanted_by_label"]
        return (f"{s['unplanted'][0] / u:.1%} of {u} unplanted cases: {b['justified'] / u:.1%} justified, "
                f"{b['unclear'] / u:.1%} unclear, {b['false positive'] / u:.1%} real false positives")
    return ["## Reading these numbers", "",
            f"- field_tilt_with_lead on one full-match claim per team: {rec('claim', 'tune')} on the tuning "
            f"seeds 2026-2028, but {rec('claim', 'hold')} on the hold-out seeds 2029-2030. The changes "
            "(including the chaser-threat line at the league's 75th percentile) were chosen on the tuning "
            "seeds, so the hold-out figure is the honest one for this level.",
            f"- The same rule in the Analyst pipeline, the figure users experience: {rec('pipeline', 'tune')} "
            f"(tuning) and {rec('pipeline', 'hold')} (hold-out). The pipeline proposes a field tilt claim for "
            "every 30-minute window above 60% tilt, several per match, and a case counts as caught when any "
            "of them fires, so a window the rule misses is often caught by a neighbouring one. A full-match "
            "claim has one chance, its box-entry and threat figures are averaged over the whole match, and "
            f"the league's threat line for full matches is tighter than for 30-minute windows (less spread: "
            f"{span.get('match')} against {span.get('window')} on these leagues).",
            f"- Analyst-pipeline unplanted fire rate, outcome label on total xG: before the changes {split(old)}; "
            f"now {split(cur[('pipeline', 'all')])}. The before figures are the old rules re-applied to the "
            "claim scopes recorded in this run (the Analyst's windows do not depend on the rules).", ""]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    ap.add_argument("--json", type=Path, required=True, help="results file; leagues already in it are skipped")
    ap.add_argument("--out", type=Path, default=None, help="markdown report (default: print)")
    ap.add_argument("--no-measure", action="store_true", help="only render what is in --json")
    a = ap.parse_args(argv)
    results = json.loads(a.json.read_text()) if a.json.exists() else []
    if not a.no_measure:
        done = {r["seed"] for r in results}
        ctx = mp.get_context("spawn")
        for seed in (int(s) for s in a.seeds.split(",")):
            if seed in done:
                continue
            with ctx.Pool(1, maxtasksperchild=1) as pool:       # one league in memory at a time
                res = pool.apply(measure, (seed,))
            results.append(res)
            a.json.write_text(json.dumps(results))
            print(f"seed {seed}: {res['sec']} s", flush=True)
    text = render(results)
    if a.out:
        a.out.write_text(text)
        print(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
