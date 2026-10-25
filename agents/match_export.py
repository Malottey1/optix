"""Per-match recap files and the fixture index for the dashboard (Fixtures and Match Hub).

    python -m agents.match_export                     # -> out/matches/index.json + out/matches/<id>.json

Every played match of the season (data/generated) is streamed through the agents one at a time, in
date order, with the novelty history of the earlier matches (as tools/pattern_diversity.py does;
the season is its own baseline). The showcase match (data/showcase, season baseline) is streamed
exactly as agents.run_match streams it. Template phraser only. Memory and time per match are
printed.

Each match file holds:
  header          teams, score, shots and xG per side (engine.metrics.xg_sum)
  periods         elapsed-clock bounds of each half
  turning_points  goals, cards and substitutions (events), and the published momentum_shift and
                  tactical_pattern insights (verified claims)
  insights        the published stream, compact (compact_insight; expand_insight restores the
                  insights.jsonl row exactly, wall-clock latency null)
  claims          every verification attempt, compact: metric, value, verdict, rules, evidence ids
                  (the live replay's stream stays in insights.jsonl / claims.jsonl: stream "bundle")
  heat            raw on-ball event counts per team per half on a 24 x 16 zone-aligned grid
                  (HEAT_X_EDGES, HEAT_Y_EDGES), in the acting team's attacking frame
  events          a compact event log; thinned by event type (THIN_ORDER) only when the file would
                  pass MAX_FILE_BYTES; claims and evidence rows are never thinned
  evidence        rows for evidence ids from other matches (season-scope claims)
  players         id -> [name, shirt, team] for every player named in the file
  matchups        only when the stream published a verified lane claim (matchup_mismatch)
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

from engine import metrics as M
from engine.tables import load, match_events
from engine.zones import FINAL_THIRD_X, LANE_EDGES, MIDDLE_THIRD_X

from .dashboard_data import TRACK_TYPES
from .run_match import timeline
from .narrative import languages
from .stream import InsightStream

MAX_FILE_BYTES = 80_000
MAX_DIR_BYTES = 3_000_000
FILE_TARGET = 72_000               # the event log is thinned to this, so 41 files stay under MAX_DIR_BYTES
TYPE_CAP = 2                       # recap cards per insight_type (turning-point types are never capped)
UNCAPPED = ("momentum_shift", "tactical_pattern", "matchup_mismatch")
SHOWCASE = "m_showcase"

# 8 columns per third and 3/3/4/3/3 rows per lane, so every bin lies inside one of the 15 zones
COLS_PER_THIRD = 8
ROWS_PER_LANE = (3, 3, 4, 3, 3)


def _cuts(lo: float, hi: float, k: int) -> list:
    return [round(lo + (hi - lo) * i / k, 4) for i in range(k)]


HEAT_X_EDGES = (_cuts(0.0, MIDDLE_THIRD_X, COLS_PER_THIRD) + _cuts(MIDDLE_THIRD_X, FINAL_THIRD_X, COLS_PER_THIRD)
                + _cuts(FINAL_THIRD_X, 100.0, COLS_PER_THIRD) + [100.0])
_LANE_LO = (0.0,) + LANE_EDGES
_LANE_HI = LANE_EDGES + (100.0,)
HEAT_Y_EDGES = [y for lo, hi, k in zip(_LANE_LO, _LANE_HI, ROWS_PER_LANE) for y in _cuts(lo, hi, k)] + [100.0]
HEAT_COLS, HEAT_ROWS = len(HEAT_X_EDGES) - 1, len(HEAT_Y_EDGES) - 1

# event types dropped from the event log, in this order, until the file fits
THIN_ORDER = (("pressure", "possession_change"), ("carry", "duel"), ("pass",),
              ("ball_recovery", "tackle", "interception", "clearance", "block", "dribble"))
LOG_COLS = ("event_id", "clock_sec", "team", "player_id", "event_type", "outcome", "related_player_id")


def heat_bin(x: float, y: float) -> int:
    """Bin index (row * HEAT_COLS + col) of a point in the attacker's frame. Thirds and lanes use the
    same comparisons as engine.zones.third_of and lane_of (>= for thirds, < for lanes), so a bin's
    zone is the zone of every point in it; within a third or lane the cut is uniform."""
    third = 2 if x >= FINAL_THIRD_X else 1 if x >= MIDDLE_THIRD_X else 0
    lo, hi = ((0.0, MIDDLE_THIRD_X), (MIDDLE_THIRD_X, FINAL_THIRD_X), (FINAL_THIRD_X, 100.0))[third]
    col = third * COLS_PER_THIRD + min(COLS_PER_THIRD - 1, max(0, int((x - lo) / (hi - lo) * COLS_PER_THIRD)))
    lane = next((i for i, e in enumerate(LANE_EDGES) if y < e), len(LANE_EDGES))
    k = ROWS_PER_LANE[lane]
    row = sum(ROWS_PER_LANE[:lane]) + min(k - 1, max(0, int((y - _LANE_LO[lane]) / (_LANE_HI[lane] - _LANE_LO[lane]) * k)))
    return row * HEAT_COLS + col


def bin_zone(b: int) -> int:
    """15-zone index (third * 5 + lane, as dashboard_data._zone) of a heat bin."""
    row, col = divmod(b, HEAT_COLS)
    lane, acc = 0, ROWS_PER_LANE[0]
    while row >= acc:
        lane += 1
        acc += ROWS_PER_LANE[lane]
    return (col // COLS_PER_THIRD) * 5 + lane


def zone_counts(bins: list) -> list:
    """The 15 zone counts of a bin vector (the zone shares are these over their sum)."""
    out = [0] * 15
    for b, n in enumerate(bins):
        out[bin_zone(b)] += n
    return out


def heat_section(ds, match_id, periods) -> dict:
    """Per team, per half: raw counts of the track's on-ball events (TRACK_TYPES with a location)
    per bin; a half is the clock range of its period, as the dashboard's zone shift reads it."""
    evs = match_events(ds)[match_id]
    m = ds.matches[match_id]
    teams = {}
    for tid in (m["home_team_id"], m["away_team_id"]):
        halves = []
        for p in periods[:2]:
            bins = [0] * (HEAT_COLS * HEAT_ROWS)
            for e in evs:
                if (e["team_id"] == tid and e["event_type"] in TRACK_TYPES and e["x_start"] is not None
                        and p["start_sec"] <= e["clock_sec"] <= p["end_sec"]):
                    bins[heat_bin(e["x_start"], e["y_start"])] += 1
            halves.append(bins)
        teams[ds.code(tid)] = halves
    return dict(cols=HEAT_COLS, rows=HEAT_ROWS, x_edges=HEAT_X_EDGES, y_edges=HEAT_Y_EDGES, teams=teams)


def header_section(ds, match_id) -> dict:
    m = ds.matches[match_id]
    evs = match_events(ds)[match_id]
    side = {}
    for key, tid in (("home", m["home_team_id"]), ("away", m["away_team_id"])):
        xg = M.xg_sum(evs, ds.shots, tid)
        side[key] = dict(code=ds.code(tid), name=ds.teams[tid]["name"], shots=xg.sample_size, xg=round(xg.value, 2))
    goals = {k: sum(1 for e in evs if e["event_type"] == "shot" and e["outcome"] == "goal" and e["team_id"] == tid)
             for k, tid in (("home", m["home_team_id"]), ("away", m["away_team_id"]))}
    side["home"]["goals"], side["away"]["goals"] = goals["home"], goals["away"]
    return dict(matchweek=m["matchweek"], date=m["date"], kickoff=m["kickoff"], **side)


def turning_points(ds, match_id, insights) -> list:
    """Goals, cards and substitutions from the events; momentum swings and pattern findings only as
    the stream published them (verified claims). Sorted by clock, then kind."""
    out = []
    for e in match_events(ds)[match_id]:
        kind = ("goal" if e["event_type"] == "shot" and e["outcome"] == "goal" else
                "card" if e["event_type"] == "card" else "sub" if e["event_type"] == "substitution" else None)
        if kind:
            row = dict(kind=kind, clock_sec=e["clock_sec"], team=ds.code(e["team_id"]), event_id=e["event_id"],
                       player_id=e["player_id"])
            if kind == "card":
                row["card"] = e["outcome"]
            if kind == "sub":
                row["on_player_id"] = e["related_player_id"] or None
            if kind == "goal":
                row["score"] = [e["score_home"] + (e["team_id"] == e["home_team_id"]),
                                e["score_away"] + (e["team_id"] != e["home_team_id"])]
            out.append(row)
    for i in insights:
        if i["insight_type"] in ("momentum_shift", "tactical_pattern"):
            row = dict(kind="momentum" if i["insight_type"] == "momentum_shift" else "pattern",
                       clock_sec=i["clock"]["start_sec"], team=i["teams"]["primary"], insight_id=i["insight_id"],
                       claim_id=i["claim_id"])
            if i["payload"].get("family"):
                row["family"] = i["payload"]["family"]
            out.append(row)
    order = {"goal": 0, "card": 1, "sub": 2, "momentum": 3, "pattern": 4}
    return sorted(out, key=lambda r: (r["clock_sec"], order[r["kind"]], r.get("event_id") or r.get("insight_id")))


def eid(match_id: str, event_id: str):
    """Compact event id: the event number for an event of this match ("m_001_e00936" -> 936),
    else the full id (evidence from other matches). expand_eid inverts it."""
    pre = f"{match_id}_e"
    return int(event_id[len(pre):]) if event_id.startswith(pre) and event_id[len(pre):].isdigit() else event_id


def expand_eid(match_id: str, v) -> str:
    return f"{match_id}_e{v:05d}" if isinstance(v, int) else v


POINT_KEYS = ("event_id", "kind", "value", "x", "y", "x_end", "y_end")


def compact_insight(match_id: str, i: dict) -> dict:
    """An insight without what the file already holds: match_id (file level), evidence ids (its
    claim's published attempt has them) and wall-clock latency (null in exports). Payload points
    become arrays in POINT_KEYS order. expand_insight restores the insights.jsonl row exactly."""
    pay = dict(i["payload"])
    if "points" in pay:
        pay["points"] = [[eid(match_id, p["event_id"]) if k == "event_id" else p[k] for k in POINT_KEYS]
                         for p in pay["points"]]
    return dict(id=i["insight_id"], type=i["insight_type"], t=i["clock"]["start_sec"], d=i["clock"]["duration_sec"],
                teams=[i["teams"]["primary"], i["teams"]["secondary"]], players=i["player_ids"], claim=i["claim_id"],
                chip=i["context_chip"], status=i["verification_status"], text=i["text"], payload=pay)


def claim_row(match_id: str, x) -> dict:
    """One verification attempt, compact: subject as [kind, id], evidence ids compacted (eid)."""
    c, v = x["claim"], x["claim"]["verification"]
    val = c["value"]
    row = dict(claim_id=c["claim_id"], attempt=v["attempt"], metric=c["metric"], claim_type=c["claim_type"],
               scope=c["scope"], subject=[c["subject"]["kind"], c["subject"]["id"]], status=v["status"],
               fact_check=v["fact_check"], context_check=v["context_check"], rule_ids=v["rule_ids"],
               amount=val.get("amount"), unit=val.get("unit"), baseline=val.get("baseline"),
               sample_size=val.get("sample_size"), interval=val.get("interval"), confidence=val.get("confidence"),
               evidence=[eid(match_id, e) for e in c["evidence_event_ids"]], revision_of=x.get("revision_of"))
    return {k: v for k, v in row.items() if v is not None}


def expand_insight(match_id: str, ci: dict, claims: list) -> dict:
    """Inverse of compact_insight: the insights.jsonl row (emitted_latency_ms null)."""
    ev = next(c["evidence"] for c in reversed(claims) if c["claim_id"] == ci["claim"])
    pay = dict(ci["payload"])
    if "points" in pay:
        pay["points"] = [{k: expand_eid(match_id, p[j]) if k == "event_id" else p[j] for j, k in enumerate(POINT_KEYS)}
                         for p in pay["points"]]
    return dict(claim_id=ci["claim"], clock=dict(duration_sec=ci["d"], emitted_latency_ms=None, start_sec=ci["t"]),
                context_chip=ci["chip"], evidence_event_ids=[expand_eid(match_id, e) for e in ev],
                insight_id=ci["id"], insight_type=ci["type"], match_id=match_id, payload=pay,
                player_ids=ci["players"], teams=dict(primary=ci["teams"][0], secondary=ci["teams"][1]),
                text=ci["text"], verification_status=ci["status"])


def matchup_section(insights) -> list:
    """The verified lane claims of this fixture (one per direction at most), if the stream
    published any; else [] and the hub omits the section."""
    return [dict(insight_id=i["insight_id"], claim_id=i["claim_id"], attacker=i["teams"]["primary"],
                 defender=i["teams"]["secondary"], metrics=i["payload"]["metrics"], confidence=i["payload"].get("confidence"), evidence_event_ids=i["evidence_event_ids"])
            for i in insights
            if i["insight_type"] == "matchup_mismatch" and i["verification_status"] in ("published", "published_with_context")]


def _log_row(ds, e) -> list:
    """An event log row in LOG_COLS order. No coordinates: the hub's pitches draw the claims'
    points and the heat bins, and the log is a list."""
    return [eid(e["match_id"], e["event_id"]), e["clock_sec"], ds.code(e["team_id"]) if e["team_id"] else None,
            e["player_id"] or None, e["event_type"], e["outcome"] or None, e["related_player_id"] or None]


def _coded(rows: list) -> dict:
    """Event log rows with event_type and outcome as indexes into `types` and `outcomes` (sorted),
    which keeps the file small; the hub decodes them (lib/match.ts)."""
    types = sorted({r[4] for r in rows})
    outcomes = sorted({r[5] for r in rows if r[5] is not None})
    ti, oi = {t: i for i, t in enumerate(types)}, {o: i for i, o in enumerate(outcomes)}
    return dict(types=types, outcomes=outcomes,
                rows=[r[:4] + [ti[r[4]], None if r[5] is None else oi[r[5]], r[6]] for r in rows])


def recap_selection(insights: list, attempts: list) -> tuple[list, list]:
    """The recap's cards: every momentum swing, pattern finding and lane claim (they are turning
    points or the matchup), and at most TYPE_CAP cards of every other insight_type, preferring
    revised cards (a blocked attempt was rewritten), then cards published with context, then the
    latest. Kept in stream order, with every verification attempt of each kept card's claim
    (the revision chain), so the claims behind a card are never cut. The full stream's counts
    stay in the file (stream_counts)."""
    by_claim = {x["claim"]["claim_id"]: x for x in attempts}

    def chain(cid):
        out = []
        while cid and cid in by_claim:
            out.append(cid)
            cid = by_claim[cid].get("revision_of")
        return out

    def rank(i):
        revised = len(chain(i["claim_id"])) > 1
        return (not revised, i["verification_status"] != "published_with_context", -i["clock"]["start_sec"],
                i["insight_id"])

    keep = {i["insight_id"] for i in insights if i["insight_type"] in UNCAPPED}
    by_type: dict = {}
    for i in insights:
        if i["insight_type"] not in UNCAPPED:
            by_type.setdefault(i["insight_type"], []).append(i)
    for rows in by_type.values():
        keep |= {i["insight_id"] for i in sorted(rows, key=rank)[:TYPE_CAP]}
    kept = [i for i in insights if i["insight_id"] in keep]
    cids = {c for i in kept for c in chain(i["claim_id"])}
    return kept, [x for x in attempts if x["claim"]["claim_id"] in cids]


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def match_file(ds, match_id, insights, attempts, status, lookup) -> tuple[dict, str]:
    """The match file as a dict and its exact serialisation. lookup: datasets to find cross-match
    evidence rows in (the match's own, then the season). For the live replay (status "live") the
    stream itself is not repeated: the hub plays it from insights.jsonl and claims.jsonl, the files
    agents.run_match writes for the same match; the file says so with stream = "bundle"."""
    tl = timeline(ds, match_id)
    evs = match_events(ds)[match_id]
    own = {e["event_id"] for e in evs}
    counts = _counts(insights)
    tps = turning_points(ds, match_id, insights)
    insights, attempts = recap_selection(insights, attempts)
    claims = [claim_row(match_id, x) for x in attempts]
    ev_ids = {i for ins in insights for i in ins["evidence_event_ids"]} | {
        i for x in attempts for i in x["claim"]["evidence_event_ids"]}
    keep_ids = ev_ids | {t["event_id"] for t in tps if "event_id" in t}
    other = sorted(ev_ids - own)
    evidence = {}
    for src in lookup:
        idx = {e["event_id"]: e for e in src.events} if other else {}
        for k in other:
            if k in idx and k not in evidence:
                evidence[k] = [idx[k]["match_id"]] + _log_row(src, idx[k])
                evidence[k][1] = k
    names = {}
    for src in lookup:
        for pid, p in src.players.items():
            names.setdefault(pid, [p["name"], p["shirt"], src.code(p["team_id"])])
    out = dict(match_id=match_id, status=status, header=header_section(ds, match_id), periods=tl["periods"],
               duration_sec=tl["duration_sec"], momentum=tl["momentum"], turning_points=tps,
               insights=[compact_insight(match_id, i) for i in insights],
               claims=claims, heat=heat_section(ds, match_id, tl["periods"]), stream="file", stream_counts=counts,
               evidence=dict(cols=["match_id", *LOG_COLS], rows=[evidence[k] for k in sorted(evidence)]))
    mu = matchup_section(insights)
    if mu:
        out["matchups"] = mu
    if status == "live":
        out.update(stream="bundle", insights=[], claims=[])
    dropped: list = []
    for step in (None, *THIN_ORDER):
        if step:
            dropped += step
        rows = [_log_row(ds, e) for e in evs if e["event_type"] not in dropped or e["event_id"] in keep_ids]
        out["events"] = dict(cols=list(LOG_COLS), omitted_types=list(dropped), total=len(evs), **_coded(rows))
        used = {r[3] for r in rows} | {r[6] for r in rows} | {r[4] for r in out["evidence"]["rows"]}
        used |= {p for i in insights for p in i["player_ids"]}
        used |= {t.get(k) for t in tps for k in ("player_id", "on_player_id")}
        out["players"] = {p: names[p] for p in sorted(x for x in used if x and x in names)}
        text = _dumps(out)
        if len(text.encode()) <= FILE_TARGET:
            return out, text
    if len(text.encode()) <= MAX_FILE_BYTES:
        return out, text
    raise SystemExit(f"{match_id}: {len(text.encode())} bytes after thinning the event log (limit {MAX_FILE_BYTES})")


def _counts(insights) -> dict:
    """Counts of the full published stream (before the recap selection), by insight_type."""
    types: dict = {}
    for i in insights:
        types[i["insight_type"]] = types.get(i["insight_type"], 0) + 1
    return dict(insights=len(insights), patterns=types.get("tactical_pattern", 0), types=dict(sorted(types.items())))


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1 << 20) if sys.platform == "darwin" else r / 1024


def fixture_row(f: dict) -> dict:
    h = f["header"]
    n = f["stream_counts"]
    return dict(id=f["match_id"], status=f["status"], matchweek=h["matchweek"], date=h["date"], kickoff=h["kickoff"],
                home=h["home"]["code"], away=h["away"]["code"], score=[h["home"]["goals"], h["away"]["goals"]],
                insights=n["insights"], patterns=n["patterns"], matchup="matchups" in f)


def export(season_dir: Path, showcase_dir: Path | None, out: Path, log=print, first: int | None = None) -> dict:
    """Write every match file and the index. first: only the first N season matches in date order
    (tests; the history of a match only depends on the matches before it, so their files are the
    same as in a full export)."""
    out.mkdir(parents=True, exist_ok=True)
    season = load(season_dir)
    order = sorted(season.matches, key=lambda mid: (season.matches[mid]["date"], season.matches[mid]["kickoff"], mid))
    order = order[:first] if first is not None else order
    history: dict = {}
    rows, sizes = [], {}

    def write(mid, data, text):
        (out / f"{mid}.json").write_text(text, encoding="utf-8")
        sizes[mid] = len(text.encode())
        rows.append(fixture_row(data))

    if showcase_dir is not None:
        t0 = time.time()
        sc = load(showcase_dir, baseline="season", season_dir=season_dir)
        s = InsightStream(sc, SHOWCASE, languages=tuple(languages()))
        ins = s.run()
        for i in ins:
            i["clock"]["emitted_latency_ms"] = None
        data, text = match_file(sc, SHOWCASE, ins, s.attempts(), "live", (sc, season))
        write(SHOWCASE, data, text)
        log(f"{SHOWCASE}: {len(ins)} insights, {sizes[SHOWCASE]} B, {time.time() - t0:.1f} s, peak RSS {_rss_mb():.0f} MB")
        del s, ins, data, text, sc
    for mid in order:
        t0 = time.time()
        s = InsightStream(season, mid, history=history, languages=tuple(languages()))
        ins = s.run()
        for i in ins:
            i["clock"]["emitted_latency_ms"] = None
        for tid in (season.matches[mid]["home_team_id"], season.matches[mid]["away_team_id"]):
            history.setdefault(tid, []).append({f: mag for (f, t, _), mag in s.orc.analyst.shown.items() if t == tid})
        data, text = match_file(season, mid, ins, s.attempts(), "final", (season,))
        write(mid, data, text)
        log(f"{mid}: {len(ins)} insights, {sizes[mid]} B, event log thinned {data['events']['omitted_types'] or 'no'}, "
            f"{time.time() - t0:.1f} s, peak RSS {_rss_mb():.0f} MB")
        del s, ins, data, text
    teams = {season.code(t): season.teams[t]["name"] for t in sorted(season.teams, key=season.code)}
    index = dict(dataset=season.label, teams=teams, heat=dict(cols=HEAT_COLS, rows=HEAT_ROWS, x_edges=HEAT_X_EDGES,
                                                               y_edges=HEAT_Y_EDGES),
                 fixtures=sorted(rows, key=lambda r: (r["status"] != "live", r["matchweek"], r["date"], r["kickoff"], r["id"])))
    text = _dumps(index)
    (out / "index.json").write_text(text, encoding="utf-8")
    total = sum(sizes.values())
    log(f"{len(sizes)} match files, {total} B in all (largest {max(sizes.values())} B); index {len(text.encode())} B")
    if total > MAX_DIR_BYTES:
        raise SystemExit(f"match files {total} B > {MAX_DIR_BYTES}")
    return dict(sizes=sizes, index=index)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", default="data/generated")
    ap.add_argument("--showcase", default="data/showcase", help="showcase match directory ('' to skip)")
    ap.add_argument("--out", default="out/matches")
    a = ap.parse_args(argv)
    return export(Path(a.season), Path(a.showcase) if a.showcase else None, Path(a.out))


if __name__ == "__main__":
    main()
