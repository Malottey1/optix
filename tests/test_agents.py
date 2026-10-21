"""Agents: ingest, the block -> revise -> re-verify loop, narrative number guard, personalization,
and the orchestrated showcase stream."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agents.analyst import MAX_ATTEMPTS
from agents.ingest import IngestAgent
from agents.log import AgentLog
from agents.messages import ClaimProposal
from agents.narrative import fmt, number_guard, render, templates
from agents.orchestrator import Orchestrator
from agents.personalization import PersonalizationAgent, UserProfile
from agents.state import MatchState
from data_gen.generate import main as generate
from engine.claims import build_claim
from engine.tables import load, match_events

ROOT = Path(__file__).resolve().parent.parent
MID = "m_showcase"


@pytest.fixture(scope="module")
def sc(tmp_path_factory):
    root = tmp_path_factory.mktemp("agents")
    generate(2026, root / "season", root / "showcase")
    return load(root / "showcase", baseline="season", season_dir=root / "season")


@pytest.fixture(scope="module")
def run(sc):
    o = Orchestrator(sc, MID)
    return o, o.run()


@pytest.fixture(scope="module")
def validator():
    return Draft202012Validator(json.loads((ROOT / "contracts" / "claim.schema.json").read_text()))


def test_agents_never_touch_generator_or_ground_truth():
    for path in (ROOT / "agents").rglob("*.py"):
        text = path.read_text()
        assert "data_gen" not in text and "ground_truth" not in text, path


# ---------- ingest ----------

def test_ingest_drops_duplicates_and_rows_missing_fields(sc):
    evs = match_events(sc)[MID][:50]
    log = AgentLog()
    state = MatchState(MID, "t_aur", "t_nor")
    state.seen_ids.add(evs[0]["event_id"])
    broken = dict(evs[3], x_end=None) if evs[3]["event_type"] == "pass" else dict(evs[3], team_id="")
    rows = evs[:3] + [broken] + evs[4:] + [evs[10]]
    clean, rep = IngestAgent(log, sc.passes, sc.shots).process(rows, state)
    assert rep.duplicates == (evs[0]["event_id"], evs[10]["event_id"])
    assert list(rep.missing_fields) == [evs[3]["event_id"]]
    assert [e["event_id"] for e in clean] == [e["event_id"] for e in evs[1:3] + evs[4:]]
    assert log.where(agent="ingest", event="rows_dropped")


def test_stream_with_duplicates_publishes_the_same(sc, run):
    _, clean_pubs = run
    evs = match_events(sc)[MID]
    noisy = [r for e in evs for r in ((e, dict(e)) if e["clock_sec"] % 7 == 0 else (e,))]
    o = Orchestrator(sc, MID)
    pubs = o.run(noisy)
    assert [p.result.claim["claim_id"] for p in pubs] == [p.result.claim["claim_id"] for p in clean_pubs]
    assert o.log.where(agent="ingest", event="rows_dropped")


# ---------- the revision loop ----------

def test_raw_field_tilt_claim_blocked_then_republished_with_context(run):
    o, pubs = run
    nor = [p for p in pubs if p.result.claim["metric"] == "field_tilt" and p.result.claim["subject"]["id"] == "t_nor"]
    assert nor, "NOR's trailing field tilt should be published"
    p = nor[0]
    first, last = p.history[0], p.history[-1]
    assert first.claim["template_key"] == "field_tilt.stat"
    assert first.status == "blocked" and first.claim["verification"]["rule_ids"] == ["field_tilt_with_lead"]
    assert first.claim["verification"]["revision_hint"] == {"field_tilt_with_lead": ["box_entries"]}
    assert last.status == "published_with_context" and last.claim["verification"]["attempt"] == 2
    assert last.claim["verification"]["context_note"] == "field_tilt.trailing_vs_deep_block"
    assert last.proposal.strategy == "add_game_state" and last.proposal.revision_of == first.claim["claim_id"]
    text = p.text.rendered["en"]["analyst"]
    assert f"{fmt(last.claim['params']['box_entries'])} of" in text and "chasing the game" in text
    # the structured log tells the same story in order
    cid1, cid2 = first.claim["claim_id"], last.claim["claim_id"]
    seq = [(r["agent"], r["event"]) for r in o.log.records if r.get("claim_id") in (cid1, cid2)]
    assert seq == [("analyst", "proposed"), ("verifier", "verified"), ("analyst", "proposed"),
                   ("analyst", "revised"), ("verifier", "verified"), ("narrative", "rendered"),
                   ("orchestrator", "published")]


def test_each_planted_trap_is_revised_with_its_strategy(run):
    _, pubs = run
    strategies = {p.history[-1].proposal.strategy for p in pubs if len(p.history) > 1}
    assert {"add_game_state", "add_shot_quality", "split_open_play_set_piece", "add_pass_quality",
            "add_press_intensity"} <= strategies


def test_every_published_claim_is_valid_and_backed_by_the_past(sc, run, validator):
    _, pubs = run
    by_id = {e["event_id"]: e for e in sc.events}
    for p in pubs:
        c = p.result.claim
        assert not list(validator.iter_errors(c)), c["claim_id"]
        assert c["verification"]["status"] in ("published", "published_with_context")
        assert c["verification"]["attempt"] == len(p.history) <= MAX_ATTEMPTS
        assert [h.claim["verification"]["attempt"] for h in p.history] == list(range(1, len(p.history) + 1))
        assert p.text.number_guard_passed
        if c["scope"] != "season":       # the season preview is backed by past matches
            assert all(by_id[i]["clock_sec"] <= p.result.proposal.trigger_clock for i in c["evidence_event_ids"])


def test_causal_claim_is_dropped_not_revised(sc, run):
    o = Orchestrator(sc, MID)
    o.feed(match_events(sc)[MID][:400])
    t = o.state.clock
    c = build_claim(o.state.view(sc), "xg", "window", {"kind": "team", "id": "t_aur"}, match_id=MID, window=(0, t),
                    claim_type="causal", template_key="xg.stat", param_values=("amount",), extra_params={"team": "AUR"})
    p = ClaimProposal(c, "recap_line", o.state.events[-1]["event_id"], t,
                      meta={"spec": dict(metric="xg", scope="window", subject={"kind": "team", "id": "t_aur"},
                                         match_id=MID, window=(0, t), template_key="xg.stat",
                                         param_values=("amount",), extra_params={"team": "AUR"}, params={},
                                         claim_type="causal")})
    assert o.handle(p) is None
    assert o.state.dropped[-1] == (c["claim_id"], "blocking_rule:causal_claim")


def test_tampered_claim_is_recomputed_then_published(sc):
    o = Orchestrator(sc, MID)
    o.feed(match_events(sc)[MID][:600])
    t = o.state.clock
    spec = dict(metric="xg", scope="window", subject={"kind": "team", "id": "t_aur"}, match_id=MID, window=(0, t),
                template_key="xg.small_sample", param_values=("amount", "shots"), extra_params={"team": "AUR"},
                params={}, claim_type="stat")
    c = build_claim(o.state.view(sc), "xg", "window", spec["subject"], match_id=MID, window=(0, t),
                    template_key=spec["template_key"], param_values=spec["param_values"],
                    extra_params=spec["extra_params"])
    bad = copy.deepcopy(c)
    bad["value"]["amount"] += 0.5
    bad["params"]["amount"] = bad["value"]["amount"]
    pub = o.handle(ClaimProposal(bad, "recap_line", o.state.events[-1]["event_id"], t, meta={"spec": spec}))
    assert pub is not None
    assert [h.status for h in pub.history] == ["blocked", pub.result.status]
    assert pub.history[0].claim["verification"]["rule_ids"] == ["value_mismatch"]
    assert pub.result.proposal.strategy == "recompute"
    assert pub.result.claim["value"]["amount"] == c["value"]["amount"]


def test_verifier_only_sees_ingested_events(sc):
    o = Orchestrator(sc, MID)
    evs = match_events(sc)[MID]
    o.feed(evs[:300])
    view = o.state.view(sc)
    assert len(view.events) == 300 and view.events[-1] is evs[299]
    future = build_claim(sc, "xg", "match", {"kind": "team", "id": "t_nor"}, match_id=MID,
                         template_key="xg.stat", param_values=("amount",), extra_params={"team": "NOR"})
    res = o.verifier.check(ClaimProposal(future, "recap_line", evs[299]["event_id"], evs[299]["clock_sec"]), o.state)
    assert res.status == "blocked" and "missing_evidence" in res.claim["verification"]["rule_ids"]


# ---------- narrative ----------

def test_every_template_has_both_tones_and_only_param_numbers():
    for key, t in templates("en").items():
        assert set(t) == {"analyst", "casual"}, key
        for tone in t.values():
            assert not number_guard(tone, {}), (key, tone)     # no hard-coded numbers in templates


def test_number_guard_catches_missing_and_invented_numbers():
    params = {"team": "NOR", "amount": 1.1, "shots": 19, "xg_per_shot": 0.058}
    good = render("xg.volume_vs_value", params, "en")
    assert all(not number_guard(t, params) for t in good.values())
    assert number_guard("NOR: 1.1 xG from 19 shots.", params) == ["param xg_per_shot=0.058 missing"]
    assert number_guard("NOR: 1.1 xG from 19 shots, 0.058 each, 3 on target.", params) == ["number 3 is not a param"]
    assert number_guard("Momentum -35.2 to 40", {"a": -35.2, "b": 40.0}) == []


def test_fmt_writes_numbers_exactly():
    assert [fmt(x) for x in (64.6, 22.0, 8, 0.058, -35.2, 1.10)] == ["64.6", "22", "8", "0.058", "-35.2", "1.1"]


# ---------- personalization ----------

def _insights(pubs):
    out = []
    for p in pubs:
        c = p.result.claim
        out.append({"insight_type": p.result.proposal.insight_type, "teams": {"primary": c["subject"]["team_code"]},
                    "player_ids": [c["subject"]["id"]] if c["subject"]["kind"] == "player" else [],
                    "clock": {"start_sec": p.result.proposal.trigger_clock}, "text": p.text.as_contract()})
    return out


def test_personalization_selects_without_changing_numbers(run):
    _, pubs = run
    ins = _insights(pubs)
    agent = PersonalizationAgent()
    casual = agent.select(ins, UserProfile(mode="casual"))
    analyst = agent.select(ins, UserProfile(mode="analyst", favorite_club="NOR"))
    assert len(casual) == len(analyst) == len(ins)
    assert {i["display"]["text"] for i in casual}.isdisjoint({i["display"]["text"] for i in analyst})
    first_at = {}
    for i in analyst:
        first_at.setdefault(i["clock"]["start_sec"], i)
    assert all(i["display"]["favorite"] for t, i in first_at.items()
               if any(j["display"]["favorite"] for j in analyst if j["clock"]["start_sec"] == t))
    focus = agent.select(ins, UserProfile(player_focus="NOR_07"))
    assert focus and all("NOR_07" in i["player_ids"] for i in focus)
    single = agent.select(ins, UserProfile(single_metric="threat_pass"))
    assert single and {i["insight_type"] for i in single} == {"threat_pass"}
    with pytest.raises(ValueError):
        UserProfile(mode="pundit")
