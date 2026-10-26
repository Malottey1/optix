"""The Azure status list is derived from repo facts and kept in step everywhere it appears."""
import json
import re
from pathlib import Path

from agents import azure_status as A

ROOT = Path(__file__).resolve().parent.parent
STATES = {A.VERIFIED_LIVE, A.VERIFIED_TESTS, A.VERIFIED_CI, A.BUILT, A.NOT_BUILT}


def test_docs_azure_md_is_the_generated_table():
    assert (ROOT / "docs" / "AZURE.md").read_text(encoding="utf-8") == A.render(), \
        "run: python -m agents.azure_status --write"


def test_committed_ui_json_carries_the_same_status():
    ui = json.loads((ROOT / "web" / "public" / "data" / "ui.json").read_text(encoding="utf-8"))
    want = [{k: r[k] for k in ("id", "name", "tech", "state", "live", "note")} for r in A.status()]
    assert ui["azure_status"] == want


def test_states_follow_the_facts():
    rows = {r["id"]: r for r in A.status()}
    assert all(r["state"] in STATES for r in rows.values())
    for r in rows.values():
        if r["state"] == A.VERIFIED_TESTS:
            assert r["tests"] and all((ROOT / t).exists() for t in r["tests"])
        if r["state"] == A.VERIFIED_LIVE:
            assert A.live_check_ran()
    if not A.live_check_ran():
        assert A.VERIFIED_LIVE not in {r["state"] for r in rows.values()}
        assert rows["phraser"]["state"] == A.BUILT and rows["appinsights"]["state"] == A.BUILT
    assert rows["eventhubs"]["state"] == A.NOT_BUILT


def test_a_live_report_that_says_not_run_never_counts(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "azure-live-check.md").write_text("# Azure live check\n\n**Not run: ...**\n")
    assert not A.live_check_ran(tmp_path / "docs" / "azure-live-check.md")
    assert not A.live_check_ran(tmp_path / "missing.md")


def test_status_text_has_no_digits_for_the_number_tracer():
    for r in A.status():
        for k in ("name", "tech", "state", "live", "note"):
            assert not re.search(r"\d", r[k]), (r["id"], k, r[k])


def test_readme_status_block_is_generated():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert A.with_readme_block(text) == text, "run: python -m agents.azure_status --write"
    assert "Planned Azure integration" not in text


def test_ci_state_only_after_a_recorded_successful_run(monkeypatch):
    rows = lambda: {r["id"]: r for r in A.status()}
    monkeypatch.setattr(A, "live_check_ran", lambda report=A.LIVE_REPORT: False)   # CI alone, no live record
    monkeypatch.setattr(A, "ci_record", lambda root=A.ROOT: None)
    assert rows()["container"]["state"] == A.BUILT and rows()["iac"]["state"] == A.BUILT
    rec = {"run_id": 1, "url": "u", "head_sha": "abcdef0", "jobs": {"docker-build": "failure", "bicep-build": None}}
    monkeypatch.setattr(A, "ci_record", lambda root=A.ROOT: rec)
    assert rows()["container"]["state"] == A.BUILT and rows()["iac"]["state"] == A.BUILT
    rec["jobs"] = {"docker-build": "success", "bicep-build": "success"}
    r = rows()
    assert r["container"]["state"] == r["iac"]["state"] == A.VERIFIED_CI
    assert r["phraser"]["state"] == A.BUILT                       # CI never verifies a live service
    assert not re.search(r"\d", r["container"]["note"] + r["iac"]["note"])


def test_ci_record_refuses_an_unfinished_run():
    import pytest
    from tools.ci_record import record_from
    with pytest.raises(SystemExit):
        record_from({"status": "in_progress"})
    rec = record_from({"status": "completed", "databaseId": 7, "headSha": "s", "url": "u",
                       "jobs": [{"name": "docker-build", "conclusion": "success"}, {"name": "web", "conclusion": "success"}]})
    assert rec["jobs"] == {"docker-build": "success", "bicep-build": None}


LIVE_HEAD = "# Azure live check\n\nRun 2026-10-26: deployment `d`, auth entra-id, 3 model calls (cap 10).\n\n"


def _rows(tmp_path, body):
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "azure-live-check.md").write_text(LIVE_HEAD + body)
    for f in ("agents/phraser.py", "agents/telemetry.py", "infra/main.bicep"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("")
    return {r["id"]: r for r in A.status(tmp_path)}


def test_in_memory_spans_never_verify_the_telemetry_export(tmp_path):
    """A live report with model calls and spans captured in memory only: the phraser is verified
    live, the Application Insights export is not (the old logic said verified live for both)."""
    r = _rows(tmp_path, "- phraser.call spans captured in memory: 3\n"
                        "- application insights export: not attempted (APPLICATIONINSIGHTS_CONNECTION_STRING not set)\n")
    assert r["phraser"]["state"] == A.VERIFIED_LIVE
    assert r["appinsights"]["state"] == A.BUILT and r["appinsights"]["live"] == "not run"
    r = _rows(tmp_path, "- phraser.call spans captured: 3\n")          # the old report, no export record
    assert r["appinsights"]["state"] == A.BUILT


def test_telemetry_export_is_verified_only_by_a_successful_recorded_export(tmp_path):
    ok = "- application insights export: exported 4 spans, connection string set, result success\n"
    assert _rows(tmp_path, ok)["appinsights"]["state"] == A.VERIFIED_LIVE
    for bad in ("- application insights export: exported 4 spans, connection string set, result failure\n",
                "- application insights export: exported 0 spans, connection string set, result success\n"):
        assert _rows(tmp_path, bad)["appinsights"]["state"] == A.BUILT
    not_run = "**Not run: no Azure configuration present**\n" + ok
    assert _rows(tmp_path, not_run)["appinsights"]["state"] == A.BUILT


def test_live_check_writes_the_export_record():
    from tools.azure_live_check import export_line
    assert "not attempted" in export_line(None)
    assert A.EXPORT_LINE.search(export_line(dict(exported=2, results=["success"])))
    assert not A.EXPORT_LINE.search(export_line(dict(exported=2, results=["success", "failure"])))
