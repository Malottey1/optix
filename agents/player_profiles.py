"""Player profiles for the dashboard (export layer): minutes, defensive actions, goalkeeper figures,
passing extras, chance lists and per-match lineups. Counted from the event, pass, shot and lineup
tables; nothing is estimated. Every rounded value is stored as the page shows it, so the number
tracer (tools/check_web.py) can match it exactly. tests/test_player_profiles.py recomputes each
aggregate from the raw CSV rows independently.

Definitions (docs/data-dictionary.md, "Dashboard exports derived from the tables"):
  minutes            sum of lineups.csv minutes_played; starts = starter rows; sub_apps = rows with
                     starter 0 and minutes > 0, sub_minutes = their minutes
  defensive actions  events of DEFENSIVE_TYPES by the player; tackles_won = tackle outcome success;
                     clearances_head = clearance body_part head; aerials / aerials_won = duel events
                     (all headed) and those with outcome success
  contributions      DEFENSIVE_CONTRIBUTIONS = tackles + interceptions + blocks + clearances
  per 90             count / minutes * 90, only with at least MIN_MINUTES minutes (else omitted)
  per 100 entries    count / opposition final-third entries faced * 100; entries faced = the
                     opponents' completed passes from outside into the final third (engine
                     metrics._is_entry) while the player was on the pitch (lineups on_sec..off_sec)
  peers              players with the same listed position and at least MIN_MINUTES minutes;
                     percentile = share below + half the ties (as web/src/lib/viz.ts percentile)
  keeper             shots by the opponents while the keeper was on the pitch (lineups on/off);
                     on target = shot_result goal or saved; xG faced = sum of xg of the on-target
                     shots; saves = save events by the keeper; save % = saves / on target; goals
                     conceded minus xG faced is descriptive only; clean sheet = started, stayed on
                     to the final whistle and the team conceded no goal in the match
  distribution       the keeper's passes, completion, and the share at least LONG_PASS_M long
  passing extras     completed progressive passes (passes.is_progressive), completed passes into
                     the final third (start outside, end inside), completed passes into the box
                     (start outside the box, end inside); line-breaking passes need opponent
                     positions and are not observable
  pass map           per player the TOP_PASSES completed forward passes (passes.is_forward) that
                     gained the most ground toward goal (x_end - x_start, attacker's frame; ties by
                     event id), each typed key pass (is_key_pass), else progressive
                     (is_progressive), else forward
  minutes (whole)    minutes rounded half up to a whole number, the figure the console shows
  chances            key passes (passes.is_key_pass) with the assisted shot (shots.assist_event_id):
                     xA = passes.xa (equal to that shot's xg in this data), result = its shot_result;
                     set piece = pass_type corner or play_pattern set_piece (engine.metrics
                     chances_created); kind = corner / free_kick / throw_in / set_piece / open_play
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from engine.zones import BOX_X, BOX_Y, FINAL_THIRD_X

DEFENSIVE_TYPES = ("tackle", "interception", "block", "clearance")
DEFENSIVE_CONTRIBUTIONS = DEFENSIVE_TYPES          # tackles + interceptions + blocks + clearances
MIN_MINUTES = 270                                  # three full matches before a rate or percentile is shown
LONG_PASS_M = 32.0                                 # a keeper pass at least this long counts as long
CHANCE_KINDS = ("corner", "free_kick", "throw_in", "set_piece", "open_play")
PASS_TYPES = ("forward", "progressive", "key_pass")   # the pass map's line types, in this order
TOP_PASSES = 25                                    # passes on a player's pass map
POINT_TYPES = DEFENSIVE_TYPES                      # the console map's marker types, in this order
DEF_RATES = ("tackles", "interceptions", "blocks", "clearances", "fouls", "contributions")


def _r(v, dp=1):
    return None if v is None else round(v, dp)


def _rows(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def lineup_rows(season_dir: Path) -> list:
    """lineups.csv rows with numeric fields."""
    out = []
    for r in _rows(Path(season_dir) / "lineups.csv"):
        out.append(dict(r, starter=int(r["starter"]), on_sec=int(r["on_sec"]) if r["on_sec"] else None,
                        off_sec=int(r["off_sec"]) if r["off_sec"] else None,
                        minutes_played=float(r["minutes_played"] or 0), sent_off=int(r["sent_off"] or 0)))
    return out


def _percentile(values, v):
    xs = [x for x in values if x is not None]
    if v is None or not xs:
        return None
    return 100 * (sum(1 for x in xs if x < v) + 0.5 * sum(1 for x in xs if x == v)) / len(xs)


def _js_round(v, dp=0):
    import math
    f = 10 ** dp
    return math.floor(v * f + 0.5) / f


def _is_entry(e) -> bool:
    return e["x_end"] is not None and e["x_start"] < FINAL_THIRD_X <= e["x_end"]


def _in_box(x, y) -> bool:
    return x is not None and y is not None and x >= BOX_X and BOX_Y[0] <= y <= BOX_Y[1]


def _intervals(lineups) -> dict:
    """(match_id, player_id) -> (on_sec, off_sec) for players who took the pitch."""
    return {(r["match_id"], r["player_id"]): (r["on_sec"], r["off_sec"])
            for r in lineups if r["minutes_played"] > 0}


def minutes_section(lineups) -> dict:
    out: dict = {}
    for r in lineups:
        if r["minutes_played"] <= 0:
            continue
        m = out.setdefault(r["player_id"], dict(minutes=0.0, starts=0, sub_apps=0, sub_minutes=0.0))
        m["minutes"] += r["minutes_played"]
        if r["starter"]:
            m["starts"] += 1
        else:
            m["sub_apps"] += 1
            m["sub_minutes"] += r["minutes_played"]
    return {pid: dict(minutes=_r(m["minutes"]), starts=m["starts"], sub_apps=m["sub_apps"],
                      sub_minutes=_r(m["sub_minutes"])) for pid, m in out.items()}


def entries_faced(season, lineups) -> dict:
    """player_id -> opposition final-third entries (completed passes) while on the pitch."""
    by_match: dict = defaultdict(list)
    for e in season.events:
        if e["event_type"] == "pass" and e["outcome"] == "success" and _is_entry(e):
            by_match[e["match_id"]].append(e)
    team = {pid: p["team_id"] for pid, p in season.players.items()}
    out: dict = defaultdict(int)
    for (mid, pid), (on, off) in _intervals(lineups).items():
        out[pid] += sum(1 for e in by_match.get(mid, ()) if e["team_id"] != team[pid] and on <= e["clock_sec"] < off)
    return dict(out)


def defensive_counts(season) -> dict:
    out: dict = defaultdict(lambda: dict(tackles=0, tackles_won=0, interceptions=0, blocks=0, clearances=0,
                                         clearances_head=0, fouls=0, pressures=0, aerials=0, aerials_won=0))
    plural = {"tackle": "tackles", "interception": "interceptions", "block": "blocks", "clearance": "clearances"}
    for e in season.events:
        pid, t = e["player_id"], e["event_type"]
        if not pid:
            continue
        if t in plural:
            out[pid][plural[t]] += 1
            if t == "tackle" and e["outcome"] == "success":
                out[pid]["tackles_won"] += 1
            if t == "clearance" and e["body_part"] == "head":
                out[pid]["clearances_head"] += 1
        elif t == "foul":
            out[pid]["fouls"] += 1
        elif t == "pressure":
            out[pid]["pressures"] += 1
        elif t == "duel":
            out[pid]["aerials"] += 1
            out[pid]["aerials_won"] += e["outcome"] == "success"
    for c in out.values():
        c["contributions"] = sum(c[plural[t]] for t in DEFENSIVE_CONTRIBUTIONS)
    return dict(out)


def passing_extras(season) -> dict:
    out: dict = defaultdict(lambda: dict(progressive=0, into_final_third=0, into_box=0))
    for e in season.events:
        if e["event_type"] != "pass" or e["outcome"] != "success" or not e["player_id"]:
            continue
        p = season.passes.get(e["event_id"])
        c = out[e["player_id"]]
        if p and p["is_progressive"]:
            c["progressive"] += 1
        if _is_entry(e):
            c["into_final_third"] += 1
        if _in_box(e["x_end"], e["y_end"]) and not _in_box(e["x_start"], e["y_start"]):
            c["into_box"] += 1
    return dict(out)


def keeper_section(season, lineups) -> dict:
    """keeper player_id -> season figures, plus the shots-against points (keeper's defending frame)."""
    gk = {pid for pid, p in season.players.items() if p["position"] == "GK"}
    on = _intervals(lineups)
    end = defaultdict(int)
    for r in lineups:
        end[r["match_id"]] = max(end[r["match_id"]], r["off_sec"] or 0)
    shots = defaultdict(list)
    saves = defaultdict(int)
    for e in season.events:
        if e["event_type"] == "shot":
            shots[e["match_id"]].append(e)
        elif e["event_type"] == "save" and e["player_id"] in gk:
            saves[e["player_id"]] += 1
    team = {pid: p["team_id"] for pid, p in season.players.items()}
    passes = defaultdict(list)
    for e in season.events:
        if e["event_type"] == "pass" and e["player_id"] in gk:
            passes[e["player_id"]].append(e)
    out = {}
    for pid in sorted(gk):
        mine = [(mid, iv) for (mid, p), iv in on.items() if p == pid]
        if not mine:
            continue
        faced, pts = [], []
        clean = 0
        for mid, (t0, t1) in sorted(mine):
            opp = [e for e in shots[mid] if e["team_id"] != team[pid] and t0 <= e["clock_sec"] < t1]
            faced += opp
            started = any(r["match_id"] == mid and r["player_id"] == pid and r["starter"] for r in lineups)
            conceded_all = sum(1 for e in shots[mid] if e["team_id"] != team[pid] and e["outcome"] == "goal")
            if started and t1 == end[mid] and conceded_all == 0:
                clean += 1
            for e in opp:
                s = season.shots[e["event_id"]]
                pts.append([e["event_id"], e["clock_sec"], _r(100 - e["x_start"]), _r(100 - e["y_start"]),
                            s["shot_result"], _r(s["xg"], 2)])
        on_t = [e for e in faced if season.shots[e["event_id"]]["shot_result"] in ("goal", "saved")]
        goals = sum(1 for e in faced if season.shots[e["event_id"]]["shot_result"] == "goal")
        xg_on = sum(season.shots[e["event_id"]]["xg"] for e in on_t)
        ps = passes[pid]
        done = [e for e in ps if e["outcome"] == "success"]
        long_ = [e for e in ps if season.passes[e["event_id"]]["pass_distance_m"] >= LONG_PASS_M]
        out[pid] = dict(
            shots_faced=len(faced), on_target=len(on_t), saves=saves[pid], conceded=goals,
            xg_faced=_r(xg_on, 2), save_pct=_r(100 * saves[pid] / len(on_t)) if on_t else None,
            conceded_minus_xg=_r(goals - xg_on, 2), clean_sheets=clean, matches=len(mine),
            passes=len(ps), pass_completion=_r(100 * len(done) / len(ps)) if ps else None,
            long_share=_r(100 * len(long_) / len(ps)) if ps else None, long_m=LONG_PASS_M,
            goal_kicks=sum(1 for e in ps if season.passes[e["event_id"]]["pass_type"] == "goal_kick"),
            points=pts)
    return out


def chance_kind(pass_type: str, play_pattern: str) -> str:
    """corner, or open_play unless the play pattern is a set piece (engine.metrics.chances_created's
    split), then the set-piece pass type: free_kick, throw_in, else set_piece."""
    if pass_type == "corner":
        return "corner"
    if play_pattern != "set_piece":
        return "open_play"
    return pass_type if pass_type in ("free_kick", "throw_in") else "set_piece"


def chances_section(season) -> dict:
    """player_id -> key passes: [event_id, clock_sec, period, minute, kind, pass_type, xA (2 dp),
    result, x0, y0, x1, y1, progressive, forward]. Sorted by match date, then clock."""
    assisted = {s["assist_event_id"]: s for s in season.shots.values() if s["assist_event_id"]}
    order = {mid: (m["date"], m["kickoff"], mid) for mid, m in season.matches.items()}
    out = defaultdict(list)
    for e in season.events:
        if e["event_type"] != "pass" or not e["player_id"]:
            continue
        p = season.passes.get(e["event_id"])
        if not p or not p["is_key_pass"]:
            continue
        s = assisted.get(e["event_id"])
        out[e["player_id"]].append((order[e["match_id"]], e["clock_sec"], [
            e["event_id"], e["clock_sec"], e["period"], e["minute"],
            chance_kind(p["pass_type"], e["play_pattern"]), p["pass_type"], _r(p["xa"], 2),
            s["shot_result"] if s else None, _r(e["x_start"]), _r(e["y_start"]), _r(e["x_end"]), _r(e["y_end"]),
            int(p["is_progressive"]), int(p["is_forward"])]))
    return {pid: [r for _, _, r in sorted(rows, key=lambda x: (x[0], x[1]))] for pid, rows in out.items()}


def pass_type_of(p) -> str:
    """key_pass, else progressive, else forward (the pass map's colour)."""
    return "key_pass" if p["is_key_pass"] else "progressive" if p["is_progressive"] else "forward"


def passes_section(season) -> dict:
    """player_id -> the TOP_PASSES most progressive completed forward passes: [event_id, x0, y0, x1, y1,
    type index into PASS_TYPES], most ground gained first (ties by event id)."""
    out = defaultdict(list)
    for e in season.events:
        if e["event_type"] != "pass" or e["outcome"] != "success" or not e["player_id"]:
            continue
        p = season.passes.get(e["event_id"])
        if not p or not p["is_forward"]:
            continue
        out[e["player_id"]].append((-(e["x_end"] - e["x_start"]), e["event_id"], [
            e["event_id"], _r(e["x_start"]), _r(e["y_start"]), _r(e["x_end"]), _r(e["y_end"]),
            PASS_TYPES.index(pass_type_of(p))]))
    return {pid: [r for _, _, r in sorted(rows, key=lambda x: (x[0], x[1]))[:TOP_PASSES]] for pid, rows in out.items()}


def whole(v: float) -> int:
    """Half up to a whole number (as the page shows minutes)."""
    import math
    return math.floor(v + 0.5)


def raw_xa(season) -> dict:
    """player_id -> sum of passes.xa over the player's key passes, in exact ten-thousandths (xa has
    four decimals), so a mean that lands on a half rounds the same way everywhere."""
    out: dict = defaultdict(int)
    for e in season.events:
        p = season.passes.get(e["event_id"]) if e["event_type"] == "pass" else None
        if p and p["is_key_pass"] and e["player_id"]:
            out[e["player_id"]] += round(p["xa"] * 10_000)
    return dict(out)


def mean3(total_1e4: int, n: int) -> float:
    """total / n rounded half up to 3 decimals, exactly (total in ten-thousandths)."""
    from fractions import Fraction
    import math
    return math.floor(Fraction(total_1e4, n * 10) + Fraction(1, 2)) / 1000


def chance_summary(rows, xa_1e4: int) -> dict:
    xa = xa_1e4 / 10_000
    kinds = {k: sum(1 for r in rows if r[4] == k) for k in CHANCE_KINDS}
    return dict(total=len(rows), set_piece=len(rows) - kinds["open_play"], open_play=kinds["open_play"],
                kinds=kinds, xa=_r(xa, 2), xa_per=mean3(xa_1e4, len(rows)) if rows else None,
                progressive=sum(r[12] for r in rows), forward=sum(r[13] for r in rows))


def defensive_points(season) -> dict:
    """player_id -> [[x, y, type index into POINT_TYPES], ...] in the player's own frame."""
    out = defaultdict(list)
    for e in season.events:
        if e["event_type"] in POINT_TYPES and e["player_id"] and e["x_start"] is not None:
            out[e["player_id"]].append([_r(e["x_start"]), _r(e["y_start"]), POINT_TYPES.index(e["event_type"])])
    return dict(out)


def profiles(season, lineups) -> dict:
    """Per-player season profile rows for ui.json (players[].profile) and the per-team lazy files.
    Returns (rows by player id, per-team file dicts)."""
    mins = minutes_section(lineups)
    faced = entries_faced(season, lineups)
    dc = defensive_counts(season)
    px = passing_extras(season)
    gk = keeper_section(season, lineups)
    ch = chances_section(season)
    xa_raw = raw_xa(season)
    pts = defensive_points(season)
    pm = passes_section(season)
    rows: dict = {}
    for pid, p in season.players.items():
        m = mins.get(pid)
        if not m:
            continue
        d = dc.get(pid, defensive_counts_empty())
        x = px.get(pid, dict(progressive=0, into_final_third=0, into_box=0))
        enough = m["minutes"] >= MIN_MINUTES
        p90 = {k: _r(90 * d[k] / m["minutes"], 2) for k in DEF_RATES} if enough else None
        f = faced.get(pid, 0)
        p100 = {k: _r(100 * d[k] / f, 1) for k in DEF_RATES} if enough and f else None
        row = dict(minutes=m["minutes"], minutes_whole=whole(m["minutes"]), starts=m["starts"], sub_apps=m["sub_apps"], sub_minutes=m["sub_minutes"],
                   passing=dict(x, p90={k: _r(90 * v / m["minutes"], 2) for k, v in x.items()} if enough else None),
                   chances=chance_summary(ch.get(pid, []), xa_raw.get(pid, 0)))
        if pid in gk:          # keepers get the keeper block; the outfield defensive block does not apply
            row["keeper"] = {k: v for k, v in gk[pid].items() if k != "points"}
        else:
            row["defence"] = dict(d, entries_faced=f, p90=p90, p100=p100)
        rows[pid] = row
    # position peers: same listed position, enough minutes
    tot = sum(r["chances"]["total"] for r in rows.values())
    meta = dict(min_minutes=MIN_MINUTES, long_pass_m=LONG_PASS_M, rates=list(DEF_RATES),
                contributions=list(DEFENSIVE_CONTRIBUTIONS), peers={},
                league_chances=dict(total=tot, xa_per=mean3(sum(xa_raw.values()), tot) if tot else None))
    for pos in ("DF", "MF", "FW"):
        peers = [pid for pid, r in rows.items()
                 if season.players[pid]["position"] == pos and r.get("defence") and r["defence"]["p90"]]
        for pid in peers:
            r = rows[pid]
            r["defence"]["peer_pctl"] = {
                k: int(_js_round(_percentile([rows[q]["defence"]["p90"][k] for q in peers], r["defence"]["p90"][k])))
                for k in DEF_RATES}
        meta["peers"][pos] = dict(n=len(peers), avg_p90={
            k: _r(sum(rows[q]["defence"]["p90"][k] for q in peers) / len(peers), 2) for k in DEF_RATES} if peers else None)
    files = {}
    for tid in sorted(season.teams, key=season.code):
        squad = sorted(pid for pid in rows if season.players[pid]["team_id"] == tid)
        files[season.code(tid)] = dict(
            team=season.code(tid), point_types=list(POINT_TYPES), pass_types=list(PASS_TYPES),
            players={pid: {k: v for k, v in dict(
                defence=pts.get(pid), chances=ch.get(pid), passes=pm.get(pid),
                shots_faced=gk[pid]["points"] if pid in gk else None).items() if v} for pid in squad})
    return dict(rows=rows, files=files, meta=meta)


def defensive_counts_empty() -> dict:
    return dict(tackles=0, tackles_won=0, interceptions=0, blocks=0, clearances=0, clearances_head=0, fouls=0,
                pressures=0, aerials=0, aerials_won=0, contributions=0)


# ---------- per-match lineups (match files) ----------

LINES = ("GK", "DF", "MF", "FW")


def match_lineups(ds, match_id: str, lineups, lateral: dict) -> dict:
    """Both teams' starters for one match: [player_id, shirt, position, line, slot, of], laid out by
    listed position (one line per position, left to right by listed role, as the Team Board), plus
    the listed shape label. Substitutions, cards and goals are the match file's turning points."""
    out = {}
    m = ds.matches[match_id]
    for side, tid in (("home", m["home_team_id"]), ("away", m["away_team_id"])):
        starters = [r for r in lineups if r["match_id"] == match_id and r["team_id"] == tid and r["starter"]]
        rows = sorted(starters, key=lambda r: (LINES.index(ds.players[r["player_id"]]["position"]),
                                               lateral.get(r["role"], 2), int(ds.players[r["player_id"]]["shirt"])))
        xi = []
        for line in LINES:
            inline = [r for r in rows if ds.players[r["player_id"]]["position"] == line]
            for k, r in enumerate(inline):
                xi.append([r["player_id"], int(ds.players[r["player_id"]]["shirt"]), line, LINES.index(line), k,
                           len(inline)])
        count = {line: sum(1 for r in xi if r[2] == line) for line in LINES}
        out[side] = dict(code=ds.code(tid), xi=xi, label="-".join(str(count[x]) for x in LINES[1:]))
    return out
