"""The Azure status list is derived from repo facts and kept in step everywhere it appears."""
import json
import re
from pathlib import Path

from agents import azure_status as A

ROOT = Path(__file__).resolve().parent.parent
STATES = {A.VERIFIED_LIVE, A.VERIFIED_TESTS, A.BUILT, A.NOT_BUILT}


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
