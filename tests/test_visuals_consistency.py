"""The visual consistency checks can fail (slow; skipped without Playwright or a built web/dist).

tools/check_web.check_consistency compares each visual on the built dashboard with the engine output.
This serves throwaway copies of web/dist, each with one visual's data changed (a claim's lane, one
shot, one stress spell, route pass counts, player values), and asserts that the matching check fails.
The committed data is never touched."""
import shutil
from pathlib import Path

import pytest

pytest.importorskip("playwright")
pytestmark = pytest.mark.slow

from playwright.sync_api import sync_playwright        # noqa: E402

from tools import check_web                             # noqa: E402
from tools.check_dashboard import chromium_path         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def test_every_visual_check_fails_when_its_data_changes(tmp_path):
    if not (ROOT / "web" / "dist" / "index.html").exists():
        pytest.skip("needs a built web/dist (cd web && npm ci --ignore-scripts && npm run build)")
    ref = tmp_path / "ref"
    shutil.copytree(ROOT / "web" / "dist" / "data", ref)
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path=chromium_path())
        proof = check_web.mutation_proof(browser, ROOT / "web" / "dist", ref, tmp_path)
        browser.close()
    assert set(proof) == set(check_web.MUTATIONS)
    assert all(v["caught"] for v in proof.values()), proof
