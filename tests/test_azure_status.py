"""The Azure status list is derived from repo facts and kept in step everywhere it appears."""
import json
import re
from pathlib import Path

import pytest

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


def test_azure_md_names_the_verified_deployment_and_the_unverified_export(tmp_path):
    text = A.render()
    if A.live_check_ran():
        assert "`gpt-4.1-mini` on a Global Standard deployment in France Central" in text
    assert ("Application Insights is not yet verified live" in text) == (not A.telemetry_exported())
    rows = {r["id"]: r for r in A.status()}
    assert "guard-accepted model sentences" in rows["cache"]["note"]


class _FakeExporter:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.got = result, error, 0

    def export(self, spans):
        self.got += len(spans)
        if self.error:
            raise self.error
        return self.result

    def shutdown(self):
        pass


def _run_spans(inner, n=3):
    """n spans through a provider with the recorder behind a BatchSpanProcessor, flushed and shut down."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    from agents import telemetry
    from tools.azure_live_check import RecordingExporter
    rec = RecordingExporter(inner)
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(rec))
    for i in range(n):
        with provider.get_tracer("t").start_as_current_span(f"s{i}"):
            pass
    telemetry.shutdown_tracing(provider)
    return rec.record


def test_recorded_export_success_verifies_the_telemetry_row(tmp_path):
    from opentelemetry.sdk.trace.export import SpanExportResult

    from tools.azure_live_check import export_line
    rec = _run_spans(_FakeExporter(SpanExportResult.SUCCESS))
    assert rec["handed"] == rec["exported"] == 3 and rec["errors"] == []
    r = _rows(tmp_path, export_line(rec) + "\n")["appinsights"]
    assert r["state"] == A.VERIFIED_LIVE and r["note"].startswith("Spans exported")


@pytest.mark.parametrize("inner, err", [
    ("failure", "SpanExportResult.FAILURE"), ("raise", "ConnectionError")])
def test_recorded_export_failure_or_exception_is_not_verified_and_names_the_error(tmp_path, inner, err):
    """The old note said "no span has been sent" whatever the live report recorded; it must now name
    the error, and a failed or raising export never verifies the row."""
    from opentelemetry.sdk.trace.export import SpanExportResult

    from tools.azure_live_check import export_line
    fake = _FakeExporter(SpanExportResult.FAILURE) if inner == "failure" else _FakeExporter(error=ConnectionError("x"))
    rec = _run_spans(fake)
    assert rec["handed"] == 3 and rec["exported"] == 0 and rec["errors"] == [err]
    line = export_line(rec)
    assert not A.EXPORT_LINE.search(line)
    r = _rows(tmp_path, line + "\n")["appinsights"]
    assert r["state"] == A.BUILT and err in r["note"]
    mixed = dict(handed=4, exported=3, results=["success", "failure"], errors=["SpanExportResult.FAILURE"])
    assert _rows(tmp_path, export_line(mixed) + "\n")["appinsights"]["state"] == A.BUILT


def test_global_provider_is_registered_once_and_before_the_azure_exporter(monkeypatch):
    """The Azure Monitor exporter reads its Resource from the global provider: it must be registered
    (exactly once per process) before the exporter is built."""
    from agents import telemetry
    calls = []
    monkeypatch.setattr(telemetry, "_REGISTERED", None)
    monkeypatch.setattr(telemetry._trace, "set_tracer_provider", lambda p: calls.append(p))
    import azure.monitor.opentelemetry.exporter as az

    def fake_from(conn):
        assert telemetry._REGISTERED is not None, "exporter built before the global provider was registered"
        return _FakeExporter()
    monkeypatch.setattr(az.AzureMonitorTraceExporter, "from_connection_string", staticmethod(fake_from))
    env = {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=00000000-0000-0000-0000-000000000000"}
    p1, kind = telemetry.build_provider(env, register=True)
    p2, _ = telemetry.build_provider(env, register=True)
    assert kind == "azure-monitor" and calls == [p1] and telemetry._REGISTERED is p1
    assert p1.resource.attributes["service.name"] == "optix"
    assert telemetry.register_global(p2) is False and calls == [p1]
