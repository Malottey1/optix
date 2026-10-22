"""Dashboard in headless Chromium (slow; skipped without Playwright, see requirements-ui.txt).

Runs the showcase stream into a temp out/, serves app/ with that out/, and runs every gate of
tools/check_dashboard.py on every route at desktop and phone width: no console error, failed or
remote request, horizontal scroll or overlapping text; Tab reaches every control; Tailwind applied;
the evidence drawer lists event ids from the stream; every number traces to the data; the
language switch keeps every number; no forbidden word; storage blocked and reduced motion work."""
import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")
pytestmark = pytest.mark.slow

from agents.run_match import main as run_main          # noqa: E402
from tools import check_dashboard                       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    if not (ROOT / "data" / "generated").exists():
        pytest.skip("needs data/generated (python -m data_gen.generate)")
    tmp = tmp_path_factory.mktemp("dash")
    site = tmp / "site"
    shutil.copytree(ROOT / "app", site / "app")
    run_main(["--match", "m_showcase", "--out", str(site / "out" / "insights.jsonl")])
    return check_dashboard.run(tmp / "screens", site_root=site)


def test_every_gate_passes_on_every_route_and_width(report):
    assert {(r["route"], r["width"]) for r in report["routes"]} == {
        (route, w) for route in check_dashboard.ROUTES for w, _ in check_dashboard.WIDTHS.values()}
    assert not report["failures"], report["failures"]


def test_the_live_center_shows_a_rewritten_card_and_the_drawer_lists_its_events(report):
    drawer = {k: v for k, v in report["drawer"].items() if k != "_problems"}
    assert drawer and all(v["listed"] == v["expected"] > 0 and not v["unknown"] for v in drawer.values())
    assert report["language"]["cards"] > 0


def test_replay_frame_times_are_recorded(report):
    f = report["frames"]
    assert f["frames"] > 30, f
    print("\nreplay frames:", f)
