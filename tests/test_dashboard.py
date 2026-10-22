"""Dashboard (web/, the current UI) in headless Chromium (slow; skipped without Playwright or a built
web/dist, see docs/dashboard.md).

Runs the showcase stream into a temp out/, copies the built web/dist with those four data files in
place of the committed ones, and runs every gate of tools/check_web.py on every route at desktop and
phone width: no console error, failed or remote request, horizontal scroll or overlapping text; Tab
reaches every control; Tailwind applied; axe finds nothing serious; the evidence drawer lists event
ids from the stream; every number traces to the data; each visual matches the engine output; in-app navigation; the language switch keeps
every number; no forbidden word; storage blocked and reduced motion work. The legacy app/ checks
live in test_dashboard_legacy.py."""
import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")
pytestmark = pytest.mark.slow

from agents.run_match import main as run_main          # noqa: E402
from tools import check_web                             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ("ui.json", "insights.jsonl", "claims.jsonl", "timeline.json")


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    if not (ROOT / "data" / "generated").exists():
        pytest.skip("needs data/generated (python -m data_gen.generate)")
    if not (ROOT / "web" / "dist" / "index.html").exists():
        pytest.skip("needs a built web/dist (cd web && npm ci --ignore-scripts && npm run build)")
    if not (ROOT / "web" / "node_modules" / "axe-core").exists():
        pytest.skip("needs web/node_modules for axe-core (cd web && npm ci --ignore-scripts)")
    tmp = tmp_path_factory.mktemp("web")
    out = tmp / "out"
    run_main(["--match", "m_showcase", "--out", str(out / "insights.jsonl")])
    dist = tmp / "dist"
    shutil.copytree(ROOT / "web" / "dist", dist)
    for f in DATA:
        shutil.copyfile(out / f, dist / "data" / f)
    return check_web.run(dist, tmp / "screens", ref_dir=out)


def test_every_gate_passes_on_every_route_and_width(report):
    assert {(r["route"], r["width"]) for r in report["routes"]} == {
        (route, w) for route in check_web.ROUTES for w, _ in check_web.WIDTHS.values()}
    assert not report["failures"], report["failures"]


def test_the_live_center_shows_a_rewritten_card_and_the_drawer_lists_its_events(report):
    drawer = {k: v for k, v in report["drawer"].items() if k != "_problems"}
    assert drawer and all(v["listed"] == v["expected"] > 0 and not v["unknown"] for v in drawer.values())
    assert report["language"]["cards"] > 0


def test_in_app_navigation_reaches_every_route(report):
    for v in report["navigation"].values():
        assert not v["problems"] and not any(r.endswith(":missing") for r in v["reached"]), v


def test_the_visuals_match_the_engine_output(report):
    c = report["consistency"]
    assert not c["problems"], c["problems"]
    assert c["pairs"] == 20 and c["cards"].get("crosshairs") and c["cards"].get("shot-blocks") and c["arrows"], c


def test_replay_frame_times_and_bundle_size_are_recorded(report):
    f = report["frames"]
    assert f["frames"] > 30, f
    assert report["bundle"]["total_kb"] < 250, report["bundle"]
    print("\nreplay frames:", f, "\ninitial JS:", report["bundle"])
