"""Dashboard in headless Chromium (slow; skipped without Playwright, see requirements-ui.txt).

Runs the showcase stream into a temp out/, serves the repo with that out/, and checks every view
loads with no console error, page error or failed request, no horizontal scroll, and shows the
blocked-then-rewritten moment."""
import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")
pytestmark = pytest.mark.slow

from agents.run_match import main as run_main          # noqa: E402
from tools import check_dashboard                       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_dashboard_views_render_without_errors(tmp_path, monkeypatch):
    if not (ROOT / "data" / "generated").exists():
        pytest.skip("needs data/generated (python -m data_gen.generate)")
    site = tmp_path / "site"
    for d in ("app", "data/showcase"):
        shutil.copytree(ROOT / d, site / d)
    run_main(["--match", "m_showcase", "--out", str(site / "out" / "insights.jsonl")])
    monkeypatch.setattr(check_dashboard, "ROOT", site)
    report = check_dashboard.run(tmp_path / "screens")
    for name, r in report.items():
        assert not r["problems"], (name, r["problems"])
        assert not r["overflowX"], name
        assert r["cards"] > 0, name
    assert report["perimeter_lock_halftime"]["rewrites"] >= 1
    assert report["blocked_then_rewritten_drawer"]["drawerOpen"]
    assert report["full_time_analyst_es"]["score"] == "2 – 1"
