"""Everything the dashboard shows beyond the insight stream, as one JSON file (out/ui.json).

Written by agents.run_match next to insights.jsonl. Every number in it is computed by engine/ (style
profiles, labels, matchups, player metrics), copied from the stream (verification ledger), or
parsed from the generated reports in docs/ (measured numbers). Every sentence comes from the
templates through the number guard. The page computes no statistic.

Sections:
  teams     style profile per team (season), labels with their rules, entry lanes made and
            conceded (attacker point of view), soft lane, and every ordered head-to-head matchup
  players   involvement, pass quality and chances created per player (season); the Verifier's
            verdict on each player's forward_passes and chances_created claim, with the sentence
            that is allowed out
  ledger    every claim in the showcase stream: passed, passed with context, revised or blocked,
            and the rule that decided it
  rewrites  per insight whose first attempt was blocked: the original sentence (rendered from the
            blocked claim, every language and tone) and the rule's plain reason
  reasons   rule_id -> plain sentence, per language
  evidence  event rows for every evidence id the dashboard can show
  measured  the tables of docs/realism-report.md, docs/robustness.md, docs/verifier-recall.md and
            docs/pattern-recall.md
  patterns  the tactical pattern catalogue (family, icon, the Verifier rules that test its naive
            claim, measured status, recall and false-positive rate from docs/data/pattern_recall.json),
            the Tier 2 and skipped patterns with their reason, each team's signature patterns
            (season share of its matches with a finding against the other teams' share) and the
            player-level findings per player (matches with a finding)
  track     [clock_sec, x, y, team code] of every on-ball event in the match, in the acting team's
            attacking frame (event locations, not tracking: the ball marker on the Focus Pitch)
  visuals   plain exports of engine metrics the visuals draw (no new metric): the match's shots
            with xG, territorial-stress spells and per-minute rhythm; per team the leading and
            trailing field tilt and ball-won height (style profile brackets); per player the
            forward passes and chances grouped by start and end zone, with xT added and xA
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from engine import metrics as M
from engine import patterns as PAT
from engine import threat as T
from engine import flow as F
from engine.claims import build_claim
from engine.matchup import lane_matchup, matchup_claim
from engine.profiles import soft_lane, team_style_profile
from engine.rules import PATTERN_RULES
from engine.style_labels import style_labels
from engine.tables import match_events, team_events
from engine.verifier import verdict
from engine.zones import FINAL_THIRD_X, LANES, MIDDLE_THIRD_X, THIRDS, lane_of, third_of

from .analyst import REVISIONS
from .azure_status import status as azure_status
from .narrative import languages, number_guard, render, rule_reasons

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ("realism-report.md", "robustness.md", "verifier-recall.md", "pattern-recall.md")
TRACK_TYPES = ("pass", "carry", "dribble", "shot", "duel", "tackle", "interception", "clearance", "block",
               "ball_recovery", "save", "claim")
PLAYER_RULES = (("chances_created", "set_piece_inflation", 4), ("forward_passes", "wide_forward_passes", 15))


def _r(v, dp=1):
    return None if v is None else round(v, dp)


def _pct(v, dp=1):
    return None if v is None else round(100 * v, dp)


def _rendered(template_key, params):
    """{lang: {tone: text}}; raises if the number guard finds a problem (it never should)."""
    out = {}
    for lang in languages():
        r = render(template_key, params, lang)
        for tone, text in r.items():
            problems = number_guard(text, params, lang)
            if problems:
                raise ValueError(f"number guard: {template_key} {lang} {tone}: {problems}")
        out[lang] = r
    return out


# ---------- teams ----------

def _metric_row(m, kind):
    """Display form of one profile metric: shares in percent, means as they are."""
    if kind == "pp":
        return dict(value=_pct(m["value"]), league=_pct(m["league"]), effect=_r(m["effect"]), unit="%",
                    interval=None if m["interval"] is None else [_pct(m["interval"][0]), _pct(m["interval"][1])],
                    confidence=m["confidence"], n=m["n"])
    return dict(value=_r(m["value"], 2), league=_r(m["league"], 2), effect=_r(m["effect"], 2), unit="",
                interval=None if m["interval"] is None else [_r(m["interval"][0], 2), _r(m["interval"][1], 2)],
                confidence=m["confidence"], n=m["n"])


def teams_section(season) -> dict:
    teams = []
    for tid in sorted(season.teams, key=season.code):
        prof = team_style_profile(season, tid)
        labels = [dict(id=l["id"], metric=l["metric"], label=l["label"], direction=l["direction"], rule=l["rule"],
                       **_metric_row(prof["metrics"][l["metric"]], l["effect_unit"]))
                  for l in style_labels(prof)]
        lanes = {}
        for set_name in ("entry_lanes", "entry_lanes_conceded"):
            lanes[set_name] = {l: dict(share=_pct(v["share"]), league=_pct(v["league"]), effect=_r(v["effect_pp"]),
                                       confidence=v["confidence"], n=v["n"])
                               for l, v in prof["lanes"][set_name].items()}
        comp = {l: dict(rate=_pct(v["rate"]), league=_pct(v["league"]), effect=_r(v["effect_pp"]),
                        confidence=v["confidence"], attempted=v["attempted"])
                for l, v in prof["completion"]["entry_completion_conceded"].items()}
        soft = soft_lane(season, tid)
        teams.append(dict(
            id=tid, code=season.code(tid), name=season.teams[tid]["name"], labels=labels,
            entry_lanes=lanes["entry_lanes"], entry_lanes_conceded=lanes["entry_lanes_conceded"],
            completion_conceded=comp,
            soft_lane=None if soft is None else dict(lane=soft["lane"], rate=_pct(soft["rate"]),
                                                     league=_pct(soft["league"]), effect=_r(soft["effect_pp"]),
                                                     confidence=soft["confidence"], attempted=soft["attempted"]),
            matches=sum(1 for m in season.matches.values() if tid in (m["home_team_id"], m["away_team_id"]))))
    h2h = []
    for a in sorted(season.teams, key=season.code):
        for d in sorted(season.teams, key=season.code):
            if a == d:
                continue
            m = lane_matchup(season, a, d)
            row = dict(attacker=season.code(a), defender=season.code(d), n_attack=m["n_attack"],
                       n_concede=m["n_concede"],
                       lanes={l: dict(attack_share=_pct(v["attack_share"]), league_share=_pct(v["league_share"]),
                                      attack_pp=_r(v["attack_pp"]), completion=_pct(v["completion"]),
                                      league_completion=_pct(v["league_completion"]),
                                      completion_pp=_r(v["completion_pp"]), mismatch_pp=_r(v["mismatch_pp"]),
                                      confidence=v["confidence"])
                              for l, v in m["lanes"].items()},
                       top=None, claim=None)
            if m["top"]:
                row["top"] = m["top"]["lane"]
                c = matchup_claim(season, a, d)
                if c is not None:
                    v = verdict(c, season)
                    row["claim"] = dict(status=v.status, rule_ids=list(v.rule_ids), template_key=c["template_key"],
                                        lane=c["zone"]["lane"],
                                        confidence=c["value"].get("confidence"),
                                        evidence_event_ids=c["evidence_event_ids"],
                                        text=_rendered(c["template_key"], c["params"]) if v.status != "blocked" else None)
            h2h.append(row)
    return dict(teams=teams, head_to_head=h2h, lanes=list(LANES),
                matches=len(season.matches), dataset=season.label)


# ---------- players ----------

def players_section(season) -> list:
    grid = T.xt_grid(season)
    league_fwd = T.league_forward_share(season)
    out = []
    for pid in sorted(season.players):
        p = season.players[pid]
        tid = p["team_id"]
        ev = team_events(season, tid)
        inv = M.involvement(ev, pid, tid)
        if not inv.value:
            continue
        comp = M.pass_completion(ev, pid, tid)
        fw = M.forward_passes_wide_share(ev, tid, pid)
        q = T.pass_quality_ratio(ev, grid, pid, team_id=tid, league_share=league_fwd)
        ch = M.chances_created(ev, season.passes, tid, pid)
        row = dict(id=pid, name=p["name"], team=season.code(tid), position=p["position"], shirt=int(p["shirt"]),
                   goals=M.goals(ev, season.shots, pid).value, assists=M.assists(ev, season.shots, pid).value,
                   involvement=inv.value, team_share=_pct(inv.detail["team_share"]),
                   passes=comp.detail["attempted"], pass_completion=_pct(comp.value),
                   forward_passes=fw.value, wide_share=_pct(fw.detail["wide_share"]),
                   pass_quality_ratio=_r(q.value, 2), chances=ch.value, chances_open_play=ch.detail["open_play"],
                   chances_set_piece=ch.detail["set_piece"], checks=[])
        subject = {"kind": "player", "id": pid}
        extra = {"player": p["name"], "team": season.code(tid)}
        for metric, rule, min_n in PLAYER_RULES:
            c = build_claim(season, metric, "season", subject, template_key=f"{metric}.stat",
                            param_values=("amount",), extra_params=extra)
            if c["value"]["amount"] < min_n:
                continue
            v = verdict(c, season)
            check = dict(metric=metric, rule=rule, fired=rule in v.rule_ids, status=v.status, rule_ids=list(v.rule_ids),
                         amount=c["value"]["amount"], evidence_event_ids=c["evidence_event_ids"])
            if rule in v.rule_ids:
                template, add, _ = REVISIONS[rule]
                c2 = build_claim(season, metric, "season", subject, template_key=template,
                                 param_values=("amount",) + add, extra_params=extra, attempt=2)
                v2 = verdict(c2, season)
                check.update(original=_rendered(c["template_key"], c["params"]), status=v2.status,
                             text=_rendered(template, c2["params"]), context_note=v2.context_note,
                             params={k: x for k, x in c2["params"].items() if isinstance(x, (int, float))})
            else:
                check.update(text=_rendered(c["template_key"], c["params"]))
            row["checks"].append(check)
        out.append(row)
    return out


# ---------- lineups (export layer: listed data, nothing measured) ----------

# left-to-right order inside a line of the lineup pitch (attacker's frame: y = 0 is the left), from
# the listed role; roles not listed here sit in the middle
LATERAL = {"left_back": 0, "centre_back_l": 1, "centre_back": 2, "centre_back_r": 3, "right_back": 4,
           "left_mid": 0, "central_mid_l": 1, "defensive_mid_l": 1, "defensive_mid": 2, "attacking_mid": 2,
           "central_mid": 2, "central_mid_r": 3, "defensive_mid_r": 3, "right_mid": 4,
           "left_winger": 0, "striker_l": 1, "striker": 2, "striker_r": 3, "right_winger": 4}
LINES = ("GK", "DF", "MF", "FW")


def _csv(path: Path) -> list:
    import csv
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def starts_by_player(season_dir: Path) -> dict:
    """player_id -> matches started (lineups.csv starter = 1)."""
    out: dict = {}
    for r in _csv(season_dir / "lineups.csv"):
        if r["starter"] == "1":
            out[r["player_id"]] = out.get(r["player_id"], 0) + 1
    return out


def lineups_section(season, season_dir: Path) -> dict:
    """Most-used starting XI per team: the 11 players with the most starts (ties: player id), each
    with the data's shirt number, listed position (GK/DF/MF/FW) and listed role. line = index in
    LINES, slot = order inside the line from LATERAL. The label counts listed positions
    (DF-MF-FW): a description of the list, not a measured or tactical shape."""
    starts = starts_by_player(season_dir)
    role = {r["player_id"]: r["role"] for r in _csv(season_dir / "players.csv")}
    out = {}
    for tid in sorted(season.teams, key=season.code):
        squad = [pid for pid, p in season.players.items() if p["team_id"] == tid]
        xi = sorted(squad, key=lambda pid: (-starts.get(pid, 0), pid))[:11]
        rows = sorted(({"id": pid, "shirt": int(season.players[pid]["shirt"]), "position": season.players[pid]["position"],
                        "role": role.get(pid), "starts": starts.get(pid, 0)} for pid in xi),
                      key=lambda r: (LINES.index(r["position"]), LATERAL.get(r["role"], 2), r["shirt"]))
        for line in LINES:
            inline = [r for r in rows if r["position"] == line]
            for k, r in enumerate(inline):
                r.update(line=LINES.index(line), slot=k, of=len(inline))
        count = {line: sum(1 for r in rows if r["position"] == line) for line in LINES}
        out[season.code(tid)] = dict(xi=rows, label="-".join(str(count[x]) for x in LINES[1:]),
                                     matches=sum(1 for m in season.matches.values()
                                                 if tid in (m["home_team_id"], m["away_team_id"])),
                                     next_most_starts=max((starts.get(p, 0) for p in squad if p not in xi), default=0))
    return out


# ---------- stream: ledger and rewrites ----------

def _chain(attempts, claim_id):
    out, a = [], attempts.get(claim_id)
    while a:
        out.insert(0, a)
        a = attempts.get(a["revision_of"]) if a["revision_of"] else None
    return out


def ledger_section(insights, attempts) -> dict:
    rows, rewrites = [], {}
    revised_from = {a["revision_of"] for a in attempts.values() if a["revision_of"]}
    seen = set()
    for ins in insights:
        hist = _chain(attempts, ins["claim_id"])
        seen.update(a["claim"]["claim_id"] for a in hist)
        first, final = hist[0]["claim"], hist[-1]["claim"]
        if len(hist) > 1:
            kind = "revised"
        elif final["verification"]["status"] == "published_with_context":
            kind = "passed_with_context"
        else:
            kind = "passed"
        deciding = list(first["verification"]["rule_ids"]) if len(hist) > 1 else list(final["verification"]["rule_ids"])
        rows.append(dict(insight_id=ins["insight_id"], claim_id=ins["claim_id"], clock_sec=ins["clock"]["start_sec"],
                         insight_type=ins["insight_type"], metric=final["metric"], team=ins["teams"]["primary"],
                         outcome=kind, rule_ids=deciding, attempts=len(hist),
                         statuses=[a["claim"]["verification"]["status"] for a in hist],
                         template_keys=[a["claim"]["template_key"] for a in hist],
                         context_note=final["verification"]["context_note"]))
        if len(hist) > 1:
            v = first["verification"]
            rewrites[ins["insight_id"]] = dict(rule_ids=list(v["rule_ids"]), revision_hint=v.get("revision_hint") or {},
                                               original=_rendered(first["template_key"], first["params"]),
                                               original_template=first["template_key"],
                                               final_template=final["template_key"], strategy=hist[-1]["strategy"])
    for cid, a in attempts.items():
        if cid in seen or cid in revised_from:
            continue
        c = a["claim"]
        rows.append(dict(insight_id=None, claim_id=cid, clock_sec=a["trigger_clock"], insight_type=None,
                         metric=c["metric"], team=c["subject"].get("team_code"), outcome="blocked",
                         rule_ids=list(c["verification"]["rule_ids"]), attempts=c["verification"]["attempt"],
                         statuses=[c["verification"]["status"]], template_keys=[c["template_key"]],
                         context_note=c["verification"]["context_note"]))
    rows.sort(key=lambda r: (r["clock_sec"], r["claim_id"]))
    counts = {k: sum(1 for r in rows if r["outcome"] == k) for k in ("passed", "passed_with_context", "revised", "blocked")}
    return dict(rows=rows, counts=counts, total=len(rows),
                attempts=len(attempts), blocked_attempts=sum(1 for a in attempts.values()
                                                             if a["claim"]["verification"]["status"] == "blocked")), rewrites


# ---------- evidence rows ----------

def evidence_section(ids, datasets) -> dict:
    want, out = set(ids), {}
    for ds in datasets:
        for e in ds.events:
            if e["event_id"] in want and e["event_id"] not in out:
                pl = ds.players.get(e["player_id"]) or {}
                rel = ds.players.get(e["related_player_id"]) or {}
                out[e["event_id"]] = dict(event_id=e["event_id"], match_id=e["match_id"], clock_sec=e["clock_sec"],
                                          period=e["period"], team=ds.code(e["team_id"]), player=pl.get("name"),
                                          related_player=rel.get("name"), event_type=e["event_type"],
                                          outcome=e["outcome"], x=e["x_start"], y=e["y_start"],
                                          x_end=e["x_end"], y_end=e["y_end"])
    return out


# ---------- measured numbers (generated reports) ----------

_ROW = re.compile(r"^\|(.*)\|\s*$")


def _cells(line):
    return [c.strip() for c in _ROW.match(line).group(1).split("|")]


def parse_report(path: Path) -> dict:
    """The markdown tables of one generated report: [{heading, headers, rows}], plus its title,
    the first paragraph and any bullet lines (the reading notes)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    title = next((l[2:] for l in lines if l.startswith("# ")), path.name)
    intro = next((l for l in lines if l and not l.startswith(("#", "|", "-"))), "")
    tables, heading, i = [], title, 0
    bullets = []
    while i < len(lines):
        l = lines[i]
        if l.startswith("#"):
            heading = l.lstrip("#").strip()
        elif l.startswith("- "):
            bullets.append(dict(heading=heading, text=l[2:]))
        elif _ROW.match(l) and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            headers = _cells(l)
            rows = []
            i += 2
            while i < len(lines) and _ROW.match(lines[i]):
                rows.append(_cells(lines[i]))
                i += 1
            tables.append(dict(heading=heading, headers=headers, rows=rows))
            continue
        i += 1
    return dict(file=f"docs/{path.name}", title=title, intro=intro, tables=tables, notes=bullets)


def measured_section(docs_dir: Path) -> list:
    return [parse_report(docs_dir / name) for name in REPORTS if (docs_dir / name).exists()]


# ---------- tactical patterns ----------

# a family is a team's signature when it is found in at least this share of the team's season
# matches and at least SIGNATURE_LIFT times the other teams' share (docs/patterns.md)
SIGNATURE_SHARE = 0.30
SIGNATURE_LIFT = 2.0
NOT_BUILT = (("P9", "sustained_box_pinning", "metric-territorial-stress", "not built"),
             ("P10", "controlled_funneling", "style-wing-play", "not built"),
             ("P12", "third_man_wall_pass", "pass", "not built"),
             ("P13", "wide_zone_turnovers", "pressure", "not built"),
             ("P14", "restless_rotation", "players", "not built"),
             (None, "false_nine_vacuum", None, "skipped: its core, a centre-back drawn out of line, is not in event data"),
             (None, "mid_block_passivity", None, "skipped: shape claims are not in event data; the rest overlaps P4"))


def _recall_rows(path: Path) -> dict:
    """family -> measured numbers from tools.pattern_recall's JSON (pooled as in docs/pattern-recall.md)."""
    if not path.exists():
        return {}
    from tools.pattern_recall import HOLDOUT, TUNING, pool, status
    raw = json.loads(path.read_text())
    runs = {(int(k.split("@")[0]), float(k.split("@")[1])): v for k, v in raw.items()}
    if not all((s, x) in runs for s in TUNING + HOLDOUT for x in (1.0, 0.5)):
        return {}
    tune, hold, half = pool(runs, TUNING, 1.0), pool(runs, HOLDOUT, 1.0), pool(runs, TUNING + HOLDOUT, 0.5)

    def rate(k, n):
        return _r(100 * k / n) if n else None
    return {f: dict(status=status(tune[f], hold[f]),
                    recall_tuning=rate(tune[f]["hits"], tune[f]["cases"]),
                    recall_holdout=rate(hold[f]["hits"], hold[f]["cases"]),
                    fp_tuning=rate(tune[f]["fps"], tune[f]["negatives"]),
                    fp_holdout=rate(hold[f]["fps"], hold[f]["negatives"]),
                    recall_half=rate(half[f]["hits"], half[f]["cases"]),
                    cases_holdout=hold[f]["cases"]) for f in PAT.FAMILIES}


def patterns_section(season, docs_dir: Path) -> dict:
    measured = _recall_rows(docs_dir / "data" / "pattern_recall.json")
    rules = {f: sorted(r for r, fam in PATTERN_RULES.items() if fam == f) for f in PAT.FAMILIES}
    catalogue = [dict(family=f, icon=PAT.ICONS[f], rule_ids=rules[f], enabled=PAT.enabled(f),
                      **(measured.get(f) or dict(status="not measured")))
                 for f in PAT.FAMILIES]
    found = {}                                    # (team, family) -> matches with a finding
    played = {}
    by_player = {}                                # (player, family) -> matches with a finding
    for mid, m in season.matches.items():
        for tid in (m["home_team_id"], m["away_team_id"]):
            played[tid] = played.get(tid, 0) + 1
            fs = PAT.detect_team(season, mid, tid)
            for fam in {f.family for f in fs}:
                found[(tid, fam)] = found.get((tid, fam), 0) + 1
            for f in fs:
                if f.player_id:
                    by_player[(f.player_id, f.family)] = by_player.get((f.player_id, f.family), 0) + 1
    signature = {}
    for tid in sorted(season.teams):
        rows = []
        for f in PAT.FAMILIES:
            n = found.get((tid, f), 0)
            others = sum(v for (t, fam), v in found.items() if fam == f and t != tid)
            others_played = sum(v for t, v in played.items() if t != tid)
            share, league = n / played[tid], others / others_played if others_played else 0.0
            if share >= SIGNATURE_SHARE and share >= SIGNATURE_LIFT * league:
                rows.append(dict(family=f, icon=PAT.ICONS[f], matches=n, played=played[tid],
                                 share=_pct(share), others_share=_pct(league)))
        signature[season.code(tid)] = sorted(rows, key=lambda r: -r["share"])
    players = {}
    for (pid, fam), n in sorted(by_player.items()):
        players.setdefault(pid, []).append(dict(family=fam, icon=PAT.ICONS[fam], matches=n,
                                                team_played=played[season.players[pid]["team_id"]]))
    return dict(catalogue=catalogue, signature=signature, players=players,
                not_built=[dict(id=i, name=n, icon=ic, status=s) for i, n, ic, s in NOT_BUILT],
                signature_rule=dict(min_share=_pct(SIGNATURE_SHARE), min_lift=SIGNATURE_LIFT))


# ---------- visuals: plain exports of existing engine metrics ----------

STATE_METRICS = ("field_tilt", "press_intensity")


def _zone(x: float, y: float) -> int:
    """Zone index = third (0 own .. 2 attacking) * 5 + lane (0 left flank .. 4 right flank), attacker POV."""
    return THIRDS.index(third_of(x)) * len(LANES) + LANES.index(lane_of(y))


def _routes(ev, season, grid, hot, pid, tid) -> list:
    """[kind, from_zone, to_zone, passes, xt_or_xa_sum, hot] per group. kind "fwd": the player's
    completed forward passes (same set as forward_passes_wide_share), summed xT added
    (threat.value_at), and how many end in a high-threat cell (the cells pass_quality_ratio
    counts); kind "op" / "sp": the player's key passes in open play / from set pieces (same split
    as chances_created), summed xA from the passes table."""
    groups: dict = {}
    for e in M._acting(ev, tid, etype="pass"):
        if e["player_id"] != pid:
            continue
        rows = []
        if e["outcome"] == "success" and e["x_end"] - e["x_start"] >= M.FORWARD_GAIN:
            rows.append(("fwd", T.value_at(grid, e["x_end"], e["y_end"]) - T.value_at(grid, e["x_start"], e["y_start"])))
        p = season.passes[e["event_id"]]
        if p["is_key_pass"]:
            rows.append(("sp" if p["pass_type"] == "corner" or e["play_pattern"] == "set_piece" else "op", p["xa"]))
        in_hot = int(T.cell(e["x_end"], e["y_end"]) in hot)
        for kind, v in rows:
            g = groups.setdefault((kind, _zone(e["x_start"], e["y_start"]), _zone(e["x_end"], e["y_end"])), [0, 0.0, 0])
            g[0] += 1
            g[1] += v
            g[2] += in_hot
    return [[k, a, b, n, round(v, 4), h] for (k, a, b), (n, v, h) in sorted(groups.items())]


def visuals_section(match_ds, season, match_id, players) -> dict:
    evs = match_events(match_ds)[match_id]
    teams = sorted({e["team_id"] for e in evs if e["team_id"]}, key=match_ds.code)
    shots = [[e["event_id"], e["clock_sec"], match_ds.code(e["team_id"]), e["player_id"], e["x_start"], e["y_start"],
              round(match_ds.shots[e["event_id"]]["xg"], 4), match_ds.shots[e["event_id"]]["shot_result"],
              match_ds.shots[e["event_id"]]["shot_type"]] for e in evs if e["event_type"] == "shot"]
    stress = {}
    for tid in teams:
        r = F.territorial_stress(evs, tid, top=len(evs))
        stress[match_ds.code(tid)] = [[s["start_sec"], s["end_sec"], s["seconds"], s["n_events"]]
                                      for s in sorted(r.detail["spells"], key=lambda s: s["start_sec"])]
    rhythm = []
    for period in sorted({e["period"] for e in evs}):
        pe = [e for e in evs if e["period"] == period]
        lo, hi = min(e["minute"] for e in pe), max(e["minute"] for e in pe)
        r = F.rhythm(pe, end_minute=hi, length=hi - lo + 1)
        first = pe[0]
        t0 = first["clock_sec"] - first["second"] - 60 * (first["minute"] - lo)   # clock at the start of minute lo
        for m, n, var in zip(r.detail["minutes"], r.detail["possession_changes"], r.detail["tempo_var"]):
            rhythm.append([period, m, t0 + 60 * (m - lo), n, var])
    states = {}
    for tid in sorted(season.teams, key=season.code):
        row = {}
        for b in ("leading", "trailing"):
            prof = team_style_profile(season, tid, b)["metrics"]
            row[b] = {k: dict(value=_r(prof[k]["value"], 4), league=_r(prof[k]["league"], 4), n=prof[k]["n"],
                              interval=None if prof[k]["interval"] is None else [_r(x, 4) for x in prof[k]["interval"]],
                              confidence=prof[k]["confidence"]) for k in STATE_METRICS}
        states[season.code(tid)] = row
    grid = T.xt_grid(season)
    hot = T.high_threat_cells(grid)
    routes = {p["id"]: _routes(team_events(season, season.players[p["id"]]["team_id"]), season, grid, hot, p["id"],
                               season.players[p["id"]]["team_id"]) for p in players}
    return dict(shots=shots, stress=stress, league_hot_share=_r(T.league_forward_share(season), 4), rhythm=rhythm, states=states, state_min_n=M.CONF_MEDIUM_N,
                routes=routes, zones=dict(thirds=list(THIRDS), lanes=list(LANES), third_x=[MIDDLE_THIRD_X, FINAL_THIRD_X]))


# ---------- all ----------

def build(match_ds, season, match_id, insights, attempts, docs_dir: Path = ROOT / "docs",
          season_dir: Path | None = None) -> dict:
    ledger, rewrites = ledger_section(insights, attempts)
    teams = teams_section(season)
    players = players_section(season)
    starts = starts_by_player(season_dir or ROOT / "data" / season.label)
    for p in players:
        p["starts"] = starts.get(p["id"], 0)
    ids = [i for ins in insights for i in ins["evidence_event_ids"]]
    ids += [i for p in players for c in p["checks"] for i in c["evidence_event_ids"]]
    ids += [i for h in teams["head_to_head"] if h["claim"] for i in h["claim"]["evidence_event_ids"]]
    return dict(match_id=match_id, season=dict(dataset=season.label, matches=len(season.matches),
                                               teams=len(season.teams)),
                teams=teams, players=players, lineups=lineups_section(season, season_dir or ROOT / "data" / season.label), ledger=ledger, rewrites=rewrites,
                reasons={lang: rule_reasons(lang) for lang in languages()},
                evidence=evidence_section(ids, (match_ds, season)), measured=measured_section(docs_dir),
                track=[[e["clock_sec"], e["x_start"], e["y_start"], match_ds.code(e["team_id"])]
                       for e in match_events(match_ds)[match_id] if e["event_type"] in TRACK_TYPES],
                visuals=visuals_section(match_ds, season, match_id, players),
                azure_status=[{k: r[k] for k in ("id", "name", "tech", "state", "live", "note")} for r in azure_status()],
                patterns=patterns_section(season, docs_dir))
