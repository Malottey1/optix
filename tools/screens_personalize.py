"""Screenshots of the personalization views for docs/screens-v10 (Fan and Analyst Match Hub at 1440
and 390, the live hub with a followed player and a focus metric, Home with For you).

    python -m tools.screens_personalize            # serves web/dist, writes docs/screens-v10/*.png
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.check_dashboard import _shrink_png, chromium_path, serve
from tools.check_web import FOCUS_CLOCK, FOCUS_PLAYER, WEB, _context, _open

OUT = Path(__file__).resolve().parent.parent / "docs" / "screens-v10"
SIZES = {"1440": (1440, 900), "390": (390, 844)}
FAVS = {"teams": ["AUR"], "players": ["AUR_09", "NTG_10"], "fixtures": []}


def shots(browser, base) -> list:
    OUT.mkdir(parents=True, exist_ok=True)
    out, problems = [], []
    for wn, (w, h) in SIZES.items():
        for mode in ("fan", "analyst"):
            ctx, page, log = _context(browser, w, h, view={"mode": mode})
            _open(page, base, "hub_final_fan" if mode == "fan" else "hub_final")
            name = f"hub_{mode}_{wn}.png"
            (OUT / name).write_bytes(_shrink_png(page.screenshot(full_page=True)))
            out.append(name)
            problems += log["problems"]
            ctx.close()
        for mode in ("fan", "analyst"):
            ctx, page, log = _context(browser, w, h, view={"mode": mode, "focus": FOCUS_PLAYER})
            _open(page, base, "hub_live", f"t={FOCUS_CLOCK}")
            page.click("[data-metric-picker] [data-metric=xg]")
            page.wait_for_selector(f"[data-so-far='{FOCUS_PLAYER}'] [data-count=passes]", timeout=10000)
            page.wait_for_timeout(500)
            name = f"live_{mode}_follow_metric_{wn}.png"
            (OUT / name).write_bytes(_shrink_png(page.screenshot(full_page=wn == "390")))
            out.append(name)
            problems += log["problems"]
            ctx.close()
        ctx, page, log = _context(browser, w, h, view={"mode": "fan"})
        ctx.add_init_script(f"try{{localStorage.setItem('optix.favourites.v1', {json.dumps(json.dumps(FAVS))})}}catch(e){{}}")
        _open(page, base, "home")
        page.wait_for_selector("[data-for-you] [data-fixture]", timeout=10000)
        page.locator("[data-for-you]").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        name = f"home_for_you_{wn}.png"
        (OUT / name).write_bytes(_shrink_png(page.locator("[data-for-you]").screenshot()))
        out.append(name)
        problems += log["problems"]
        ctx.close()
    return out, problems


def main():
    from playwright.sync_api import sync_playwright
    httpd = serve(WEB / "dist")
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium_path())
        names, problems = shots(browser, base)
        browser.close()
    httpd.shutdown()
    print("\n".join(names))
    for x in problems:
        print("PROBLEM", x)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
