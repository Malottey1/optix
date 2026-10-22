"""Headless check of the dashboard: serve the repo, open views in Chromium, save screenshots to
docs/screens/, and fail on any console error, page error or failed request.

    python -m tools.check_dashboard            # needs out/ from agents.run_match
Requires requirements-ui.txt (Playwright). Uses Playwright's own Chromium, or the one in
/opt/pw-browsers or the local Playwright cache when the bundled revision is missing.
"""
from __future__ import annotations

import argparse
import functools
import glob
import http.server
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

VIEWS = [
    # name, query, viewport, extra
    ("kickoff_matchup", "t=60&select=ins_0001", (1440, 1000), {}),
    ("perimeter_lock_halftime", "t=2760", (1440, 1000), {}),
    ("blocked_then_rewritten_drawer", "t=2760&mode=analyst&drawer=1&select={lock}", (1440, 1000), {}),
    ("full_time_analyst_es", "t=7200&mode=analyst&lang=es", (1440, 1000), {}),
    ("player_focus_fr", "t=7200&player=NOR_07&lang=fr", (1440, 1000), {}),
    ("dark_mode", "t=4600&theme=dark", (1440, 1000), {}),
    ("mobile", "t=2760", (390, 844), {}),
    ("reduced_motion", "t=1800", (1440, 1000), {"reduced_motion": "reduce"}),
]


def chromium_path():
    for pattern in ("/opt/pw-browsers/chromium*/chrome-*/chrome", "/opt/pw-browsers/chromium*/chrome-linux/chrome",
                    os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*"),
                    os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[-1]
    return None


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve():
    handler = functools.partial(_Quiet, directory=str(ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def lock_insight_id():
    import json
    for line in (ROOT / "out" / "insights.jsonl").read_text().splitlines():
        i = json.loads(line)
        if i["insight_type"] == "perimeter_lock":
            return i["insight_id"]
    raise SystemExit("no perimeter_lock insight in out/insights.jsonl")


def run(out_dir: Path) -> dict:
    from playwright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    httpd = serve()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/app/"
    lock = lock_insight_id()
    report = {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            path = chromium_path()
            if not path:
                raise
            browser = p.chromium.launch(executable_path=path)
        for name, query, (w, h), extra in VIEWS:
            ctx = browser.new_context(viewport={"width": w, "height": h}, **extra)
            page = ctx.new_page()
            problems = []
            page.on("console", lambda m: problems.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
            page.on("requestfailed", lambda r: problems.append(f"requestfailed: {r.url}"))
            page.on("response", lambda r: problems.append(f"http {r.status}: {r.url}") if r.status >= 400 else None)
            page.goto(base + "?" + query.format(lock=lock))
            page.wait_for_selector("body[data-ready='1']", timeout=10000)
            page.wait_for_timeout(400)
            checks = page.evaluate("""() => ({
                cards: document.querySelectorAll('#feed .card').length,
                rewrites: document.querySelectorAll('#feed .rewrite').length,
                pitchMarks: document.querySelectorAll('#pitch circle').length,
                drawerOpen: !document.getElementById('drawer').hidden,
                overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                score: document.getElementById('score').textContent,
            })""")
            page.screenshot(path=str(out_dir / f"{name}.png"), full_page=name != "blocked_then_rewritten_drawer")
            report[name] = {"problems": problems, **checks}
            ctx.close()
        browser.close()
    httpd.shutdown()
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "docs" / "screens"))
    a = ap.parse_args(argv)
    report = run(Path(a.out))
    bad = False
    for name, r in report.items():
        print(f"{name:32s} cards={r['cards']:2d} rewrites={r['rewrites']} pitch_marks={r['pitchMarks']:3d} "
              f"drawer={r['drawerOpen']} overflow_x={r['overflowX']} score={r['score']} problems={len(r['problems'])}")
        for pr in r["problems"]:
            print("   ", pr)
        bad |= bool(r["problems"]) or r["overflowX"]
    if bad:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main()
