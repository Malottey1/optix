"""out/ui.json (agents/dashboard_data.py): the data the dashboard shows beyond the insight stream.
Every sentence passes the number guard, the planted cases surface where a viewer would look for
them, and nothing the pages need is missing."""
import json
import re
from pathlib import Path

import pytest

from agents.narrative import languages, number_guard
from agents.run_match import main as run_main
from data_gen.generate import main as generate
from engine.verifier import RULES

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    root = tmp_path_factory.mktemp("ui")
    generate(2026, root / "season", root / "showcase")
    run_main(["--match", "m_showcase", "--data", str(root / "showcase"), "--season", str(root / "season"),
              "--out", str(root / "out" / "insights.jsonl")])
    o = root / "out"
    insights = [json.loads(l) for l in (o / "insights.jsonl").read_text().splitlines() if l.strip()]
    attempts = {a["claim"]["claim_id"]: a for a in map(json.loads, (o / "claims.jsonl").read_text().splitlines())}
    gt = json.loads((root / "season" / "ground_truth.json").read_text())
    return json.loads((o / "ui.json").read_text()), insights, attempts, gt


def _texts(rendered, params):
    for lang, tones in rendered.items():
        for tone, text in tones.items():
            yield lang, tone, text, number_guard(text, params, lang)


def test_ledger_accounts_for_every_claim_and_every_rewrite(out):
    ui, insights, attempts, _ = out
    L = ui["ledger"]
    assert sum(L["counts"].values()) == L["total"] == len(L["rows"])
    assert L["attempts"] == len(attempts)
    revised = [r for r in L["rows"] if r["outcome"] == "revised"]
    assert {r["insight_id"] for r in revised} == set(ui["rewrites"])
    assert L["blocked_attempts"] == sum(1 for a in attempts.values() if a["claim"]["verification"]["status"] == "blocked")
    for r in revised:                              # the deciding rule is the one that blocked attempt 1
        assert r["rule_ids"] and r["statuses"][0] == "blocked" and r["statuses"][-1] != "blocked"


def test_original_wording_is_the_blocked_claim_and_passes_the_number_guard(out):
    ui, insights, attempts, _ = out
    by_id = {i["insight_id"]: i for i in insights}
    for iid, rw in ui["rewrites"].items():
        first = attempts[by_id[iid]["claim_id"]]
        while first["revision_of"]:
            first = attempts[first["revision_of"]]
        assert rw["original_template"] == first["claim"]["template_key"]
        assert set(rw["original"]) == set(languages())
        for lang, tone, text, problems in _texts(rw["original"], first["claim"]["params"]):
            assert not problems, (iid, lang, tone, text, problems)


def test_rule_reasons_cover_every_rule_in_every_language_without_numbers(out):
    ui = out[0]
    ids = {r.RULE_ID for r in RULES}
    for lang in languages():
        assert ids <= set(ui["reasons"][lang]), (lang, ids - set(ui["reasons"][lang]))
        for rid, text in ui["reasons"][lang].items():
            assert not re.search(r"\d", text), (lang, rid, text)


def test_team_board_recovers_the_planted_styles(out):
    ui = out[0]
    teams = {t["code"]: t for t in ui["teams"]["teams"]}
    label = lambda code, lid: next(l for l in teams[code]["labels"] if l["id"] == lid)
    assert label("CAL", "press")["label"] == "High press"
    assert all(l["rule"] and l["n"] > 0 for t in teams.values() for l in t["labels"])
    aur = teams["AUR"]["entry_lanes"]
    assert max(aur, key=lambda l: aur[l]["effect"]) == "left_flank"           # AUR attacks down its left
    assert teams["NOR"]["soft_lane"]["lane"] == "left_flank"                  # NOR is soft on that side
    h = next(x for x in ui["teams"]["head_to_head"] if x["attacker"] == "AUR" and x["defender"] == "NOR")
    assert h["top"] == "left_flank" and h["claim"]["status"] != "blocked"
    assert len(ui["teams"]["head_to_head"]) == len(teams) * (len(teams) - 1)


def test_player_deck_puts_context_on_the_planted_players(out):
    ui, _, _, gt = out
    players = {p["id"]: p for p in ui["players"]}
    for pid, plant in gt["planted_players"].items():
        rule = {"volume_passer": "wide_forward_passes", "corner_specialist": "set_piece_inflation"}[plant["trap"]]
        c = next(c for c in players[pid]["checks"] if c["rule"] == rule)
        assert c["fired"] and c["status"] == "published_with_context", (pid, c)
        for lang, tone, text, problems in _texts(c["text"], c["params"]):
            assert not problems, (pid, lang, tone, text, problems)


def test_no_tracking_or_fitness_fields_on_players(out):
    banned = re.compile(r"fatigue|speed|distance|sprint|fitness|gps|meters|metres", re.I)
    for p in out[0]["players"]:
        assert not [k for k in p if banned.search(k)], p.keys()


def test_every_evidence_id_the_pages_show_has_an_event_row(out):
    ui, insights, _, _ = out
    ids = {i for ins in insights for i in ins["evidence_event_ids"]}
    ids |= {i for p in ui["players"] for c in p["checks"] for i in c["evidence_event_ids"]}
    assert ids <= set(ui["evidence"]), sorted(ids - set(ui["evidence"]))[:5]


def test_measured_numbers_are_parsed_from_the_three_reports(out):
    reports = {r["file"]: r for r in out[0]["measured"]}
    assert set(reports) == {"docs/realism-report.md", "docs/robustness.md", "docs/verifier-recall.md"}
    for r in reports.values():
        assert r["tables"] and all(t["rows"] and len(t["headers"]) == len(t["rows"][0]) for t in r["tables"])
    text = (ROOT / "docs" / "verifier-recall.md").read_text()
    assert all(n["text"] in text for n in reports["docs/verifier-recall.md"]["notes"])
