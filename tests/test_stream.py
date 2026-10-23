"""Timed insight stream: schema, context chips, numbers traced to the claim, latency, runner."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agents.run_match import main as run_main
from agents.stream import InsightStream
from data_gen.generate import main as generate
from engine.tables import load

ROOT = Path(__file__).resolve().parent.parent
MID = "m_showcase"
LATENCY_BUDGET_MS = 1000


@pytest.fixture(scope="module")
def paths(tmp_path_factory):
    root = tmp_path_factory.mktemp("stream")
    generate(2026, root / "season", root / "showcase")
    return root


@pytest.fixture(scope="module")
def stream(paths):
    ds = load(paths / "showcase", baseline="season", season_dir=paths / "season")
    s = InsightStream(ds, MID)
    s.run()
    return s, ds


@pytest.fixture(scope="module")
def insight_validator():
    return Draft202012Validator(json.loads((ROOT / "contracts" / "insight.schema.json").read_text()))


def test_every_insight_validates(stream, insight_validator):
    s, _ = stream
    assert len(s.insights) >= 20
    for ins in s.insights:
        errs = [e.message for e in insight_validator.iter_errors(ins)]
        assert not errs, (ins["insight_id"], errs)


def test_insights_are_timed_in_match_order(stream):
    s, ds = stream
    starts = [i["clock"]["start_sec"] for i in s.insights]
    # the clock runs on through stoppage time: insights end by the last event, not at 90:00
    assert starts == sorted(starts) and starts[-1] <= ds.events[-1]["clock_sec"]
    assert len({i["insight_id"] for i in s.insights}) == len(s.insights)


def test_context_chip_iff_published_with_context(stream):
    s, _ = stream
    claims = {p.result.claim["claim_id"]: p.result.claim for p in s.orc.state.published}
    for ins in s.insights:
        c = claims[ins["claim_id"]]
        assert ins["verification_status"] == c["verification"]["status"]
        if ins["verification_status"] == "published_with_context":
            assert ins["context_chip"] == {"standard_metric": c["metric"], "standard_value": c["value"]["amount"],
                                           "note_key": c["verification"]["context_note"]}
        else:
            assert ins["context_chip"] is None


def test_payload_numbers_come_from_the_claim_and_points_from_evidence(stream):
    s, ds = stream
    claims = {p.result.claim["claim_id"]: p.result.claim for p in s.orc.state.published}
    by_id = {e["event_id"]: e for e in ds.events + ds.baseline.events}    # the preview cites the season
    for ins in s.insights:
        c = claims[ins["claim_id"]]
        backed = {c["value"]["amount"], *(c.get("supporting_values") or {}).values(),
                  *(v for v in c["params"].values() if isinstance(v, (int, float)))}
        for k, v in ins["payload"]["metrics"].items():
            if isinstance(v, (int, float)):
                assert v in backed, (ins["insight_id"], k, v)
        assert set(ins["evidence_event_ids"]) <= set(by_id)
        for pt in ins["payload"].get("points", []):
            assert pt["event_id"] in c["evidence_event_ids"]
            e = by_id[pt["event_id"]]
            assert (pt["x"], pt["y"], pt["x_end"], pt["y_end"]) == (e["x_start"], e["y_start"], e["x_end"], e["y_end"])


def test_planted_traps_reach_the_stream_with_context(stream):
    s, _ = stream
    kinds = {(i["insight_type"], i["teams"]["primary"]) for i in s.insights}
    assert ("perimeter_lock", "NTG") in kinds
    assert ("volume_vs_value", "NTG") in kinds
    assert ("set_piece_inflation", "NTG") in kinds
    assert ("matchup_mismatch", "AUR") in kinds
    lock = next(i for i in s.insights if i["insight_type"] == "perimeter_lock")
    assert lock["context_chip"]["note_key"] == "field_tilt.trailing_vs_deep_block"
    assert any(p["kind"] == "box_entry" for p in lock["payload"]["points"])
    for i in s.insights:
        if i["insight_type"] == "rhythm_wave":
            assert len(i["payload"]["series"]) == 15
        if i["insight_type"] == "momentum_shift":
            assert 0 < len(i["payload"]["series"]) <= 15
            assert i["payload"]["series"][-1] == pytest.approx(i["payload"]["metrics"]["momentum"], abs=0.1)


def test_latency_under_one_second(stream):
    s, _ = stream
    lat = [i["clock"]["emitted_latency_ms"] for i in s.insights]
    assert max(lat) < LATENCY_BUDGET_MS, max(lat)
    assert max(s.event_ms) < LATENCY_BUDGET_MS


def test_runner_writes_stream_claims_and_logs(paths, tmp_path, insight_validator, capsys):
    out = tmp_path / "out" / "insights.jsonl"
    run_main(["--match", MID, "--data", str(paths / "showcase"), "--season", str(paths / "season"),
              "--out", str(out)])
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows and all(not list(insight_validator.iter_errors(r)) for r in rows)
    attempts = [json.loads(line) for line in (out.parent / "claims.jsonl").read_text().splitlines()]
    blocked = [a for a in attempts if a["claim"]["verification"]["status"] == "blocked"]
    assert blocked
    revised = {a["revision_of"]: a for a in attempts if a["revision_of"]}
    for b in blocked:
        assert revised[b["claim"]["claim_id"]]["claim"]["verification"]["attempt"] == 2
    logs = [json.loads(line) for line in (out.parent / "agent_log.jsonl").read_text().splitlines()]
    assert {r["agent"] for r in logs} >= {"analyst", "verifier", "narrative", "orchestrator", "stream"}
    assert "insights ->" in capsys.readouterr().out


def test_two_exports_are_byte_identical_and_runtime_fields_are_kept_aside(paths, tmp_path):
    files = ("insights.jsonl", "claims.jsonl", "timeline.json", "ui.json")
    for n in (1, 2):
        run_main(["--match", MID, "--data", str(paths / "showcase"), "--season", str(paths / "season"),
                  "--out", str(tmp_path / str(n) / "insights.jsonl")])
    for f in files:
        assert (tmp_path / "1" / f).read_bytes() == (tmp_path / "2" / f).read_bytes(), f
    rows = [json.loads(line) for line in (tmp_path / "1" / "insights.jsonl").read_text().splitlines()]
    assert all(r["clock"]["emitted_latency_ms"] is None for r in rows)
    runtime = [json.loads(line) for line in (tmp_path / "1" / "runtime.jsonl").read_text().splitlines()]
    lat = [r["emitted_latency_ms"] for r in runtime if r["kind"] == "insight"]
    assert len(lat) == len(rows) and all(isinstance(x, int) and x < LATENCY_BUDGET_MS for x in lat)
    assert all(r["verified_at"] for r in runtime if r["kind"] == "attempt")
