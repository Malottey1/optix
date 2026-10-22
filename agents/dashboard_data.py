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
  measured  the tables of docs/realism-report.md, docs/robustness.md and docs/verifier-recall.md
  track     [clock_sec, x, y, team code] of every on-ball event in the match, in the acting team's
            attacking frame (event locations, not tracking: the ball marker on the Focus Pitch)
"""
from __future__ import annotations

import re
from pathlib import Path

from engine import metrics as M
from engine import threat as T
from engine.claims import build_claim
from engine.matchup import lane_matchup, matchup_claim
from engine.profiles import soft_lane, team_style_profile
from engine.style_labels import style_labels
from engine.tables import match_events, team_events
from engine.verifier import verdict
from engine.zones import LANES

from .analyst import REVISIONS
from .narrative import languages, number_guard, render, rule_reasons

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ("realism-report.md", "robustness.md", "verifier-recall.md")
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
        row = dict(id=pid, name=p["name"], team=season.code(tid), position=p["position"],
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


# ---------- all ----------

def build(match_ds, season, match_id, insights, attempts, docs_dir: Path = ROOT / "docs") -> dict:
    ledger, rewrites = ledger_section(insights, attempts)
    teams = teams_section(season)
    players = players_section(season)
    ids = [i for ins in insights for i in ins["evidence_event_ids"]]
    ids += [i for p in players for c in p["checks"] for i in c["evidence_event_ids"]]
    ids += [i for h in teams["head_to_head"] if h["claim"] for i in h["claim"]["evidence_event_ids"]]
    return dict(match_id=match_id, season=dict(dataset=season.label, matches=len(season.matches),
                                               teams=len(season.teams)),
                teams=teams, players=players, ledger=ledger, rewrites=rewrites,
                reasons={lang: rule_reasons(lang) for lang in languages()},
                evidence=evidence_section(ids, (match_ds, season)), measured=measured_section(docs_dir),
                track=[[e["clock_sec"], e["x_start"], e["y_start"], match_ds.code(e["team_id"])]
                       for e in match_events(match_ds)[match_id] if e["event_type"] in TRACK_TYPES])
