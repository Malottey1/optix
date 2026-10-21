"""Plain-text style and matchup report for two teams.

    python -m engine.report --team AUR --opponent NOR [--data data/generated] [--json]

Everything printed is computed from the event tables by engine/; nothing is read from the
generator or ground truth.
"""
from __future__ import annotations

import argparse
import json
import sys

from .matchup import lane_matchup, matchup_claim
from .profiles import BRACKETS, SCALARS, bracket_shift, team_style_profile
from .tables import load
from .zones import LANES


def _f(v, nd=3):
    return "-" if v is None else f"{v:.{nd}f}"


def _pp(v):
    return "-" if v is None else f"{v:+.1f}"


def _z(v):
    return "-" if v is None else f"{v:+.1f}"


def profile_lines(ds, team_id) -> list[str]:
    code = ds.code(team_id)
    out = [f"== {code} style profile (value / league avg / z, n) =="]
    profiles = {b: team_style_profile(ds, team_id, b) for b in BRACKETS}
    out.append(f"{'metric':22s}" + "".join(f"{b:>28s}" for b in BRACKETS))
    for name in SCALARS:
        cells = []
        for b in BRACKETS:
            m = profiles[b]["metrics"][name]
            cells.append(f"{_f(m['value'], 2)} / {_f(m['league'], 2)} / {_z(m['z'])}, {m['n']}".rjust(28))
        out.append(f"{name:22s}" + "".join(cells))
    lanes = profiles["all"]["lanes"]
    out.append("lane shares, all minutes (share / league / z)   [attacker point of view]")
    for set_name in ("entry_lanes", "entry_lanes_conceded", "chance_lanes_conceded"):
        n = next(iter(lanes[set_name].values()))["n"]
        cells = "  ".join(f"{l}={_f(v['share'], 2)}/{_f(v['league'], 2)}/{_z(v['z'])}"
                          for l, v in lanes[set_name].items())
        out.append(f"  {set_name:22s} n={n:<5d} {cells}")
    return out


def shift_lines(ds, team_id) -> list[str]:
    out = [f"== {ds.code(team_id)} when leading vs level (descriptive) =="]
    for name, s in bracket_shift(ds, team_id, "leading", "level").items():
        out.append(f"  {name:22s} level {_f(s['from'], 2):>7s} -> leading {_f(s['to'], 2):>7s}   "
                   f"delta {_f(s['delta'], 2):>6s}   league delta {_f(s['league_delta'], 2):>6s}   "
                   f"n {s['n_from']}/{s['n_to']}")
    return out


def matchup_lines(ds, attacker_id, defender_id, baseline_ds=None) -> list[str]:
    m = lane_matchup(ds, attacker_id, defender_id, baseline_ds=baseline_ds)
    a, d = ds.code(attacker_id), ds.code(defender_id)
    out = [f"== {a} attack vs {d} defence, final-third entries by lane (attacker point of view) ==",
           f"  sample: {a} entries n={m['n_attack']}, entries conceded by {d} n={m['n_concede']}, "
           f"baseline {m['baseline_label']} n={m['n_baseline']}",
           f"  {'lane':18s}{'attack % [95% CI]':>22s}{'concede % [95% CI]':>22s}{'league %':>10s}"
           f"{'att pp':>8s}{'con pp':>8s}{'mismatch pp':>13s}{'confidence':>12s}"]
    for lane in LANES:
        v = m["lanes"][lane]
        ci = lambda s, iv: "-" if s is None else f"{100 * s:.1f} [{100 * iv[0]:.1f}-{100 * iv[1]:.1f}]"
        out.append(f"  {lane:18s}{ci(v['attack_share'], v['attack_interval']):>22s}"
                   f"{ci(v['concede_share'], v['concede_interval']):>22s}{100 * v['league_share']:>10.1f}"
                   f"{_pp(v['attack_pp']):>8s}{_pp(v['concede_pp']):>8s}{_pp(v['mismatch_pp']):>13s}{v['confidence']:>12s}")
    top = m["top"]
    out.append(f"  top mismatch: {top['lane']} ({len(top['evidence_event_ids'])} evidence events)" if top
               else "  top mismatch: none (no lane where both sides lean the same way)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--team", required=True, help="attacking team code, e.g. AUR")
    ap.add_argument("--opponent", required=True, help="defending team code, e.g. NOR")
    ap.add_argument("--data", default="data/generated", help="directory with the CSV tables")
    ap.add_argument("--match-id", default=None, help="match_id for the claim (default preview_<A>_<B>)")
    ap.add_argument("--json", action="store_true", help="print only the claim object as JSON")
    args = ap.parse_args(argv)

    ds = load(args.data)
    att, dfn = ds.team_by_code(args.team), ds.team_by_code(args.opponent)
    claim = matchup_claim(ds, att, dfn, args.match_id)
    if args.json:
        print(json.dumps(claim, indent=2))
        return 0
    lines = [f"Optix engine report: {ds.code(att)} vs {ds.code(dfn)}  "
             f"({len(ds.matches)} matches, {len(ds.events)} events from {args.data})", ""]
    lines += profile_lines(ds, att) + [""] + profile_lines(ds, dfn) + [""]
    lines += shift_lines(ds, att) + [""] + matchup_lines(ds, att, dfn) + [""]
    lines += ["== claim (pending verification) ==", json.dumps(claim, indent=2)]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
