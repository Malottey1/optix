"""Headless check of the built dashboard (web/dist): serve it, open every route at desktop and phone
width in Chromium, save screenshots to docs/screens-v2/, and report every gate:

  * no console error, page error, failed request, HTTP error, or request to a host other than
    localhost; no horizontal scroll; no overlapping text; Tab reaches every control;
  * Tailwind applied (known utilities produce their computed style);
  * axe-core (injected from web/node_modules) finds no serious or critical violation;
  * every number on every route traces to the source data (web/dist/data, byte copies of out/) or
    to a documented formula: football clock time from clock seconds, the length of a listed
    collection, and the per-type counts of an insight's evidence events (the card's evidence
    summary: "15 events (pass 12, shot 3)");
  * the evidence drawer lists exactly the claim's event ids, and every one exists in the stream;
  * the SVG layers carry data attributes tests can read (data-event-id, data-lane, data-team,
    data-claim-id);
  * switching language never changes a number, and every sentence passes the number guard;
  * no forbidden word (real club names, prediction or betting language);
  * the page still works with storage blocked, and with reduced motion it does not autoplay;
  * replay frame times while playing (p50 / p95) and the initial JS size (gzip).

    python -m tools.check_web               # needs web/dist (cd web && npm run build)
Shares its helpers with tools/check_dashboard.py (the legacy app/ checker).
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
from collections import Counter
from pathlib import Path

from tools.check_dashboard import (FOCUSABLE_JS, FORBIDDEN, FRAMES_JS, OVERLAP_JS, _context, _shrink_png, _tab_order,
                                   chromium_path, load_sources, numbers_of, serve, untraced_numbers)

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
ROUTES = ("live", "teams", "players", "tech")
WIDTHS = {"desktop": (1440, 900), "mobile": (390, 844)}
QUERY = {"live": "t=2760"}               # half-time stoppage: the rewritten Perimeter Lock card on top
AXE_FAIL = {"serious", "critical"}
# what each route must expose for tests (selector -> attribute that must be non-empty)
DATA_ATTRS = {
    "live": [("#pitch [data-event-id]", "data-event-id"), ("#pitch [data-team]", "data-team"),
             ("[data-insight-id][data-claim-id]", "data-claim-id")],
    "teams": [("svg [data-lane]", "data-lane"), ("[data-team]", "data-team")],
    "players": [("[data-player] [data-event-id]", "data-event-id")],
    "tech": [("tr[data-claim-id]", "data-claim-id")],
}

# A Radix roving-focus group (toggle group, tab list) is one tab stop: its root takes focus and
# hands it to the active item (whose own tabindex is -1 until then). So the focused element counts
# for the nearest counted ancestor: reaching the item means the root's stop was reached.
WEB_ACTIVE_JS = """() => { const e = document.activeElement; const c = e && e.closest('[data-tabcheck]');
  return c ? c.getAttribute('data-tabcheck') : null; }"""

TAILWIND_JS = """() => {
  const main = document.querySelector('main');
  const panel = document.querySelector('.rounded-2xl');
  const probe = document.createElement('div');
  probe.className = 'hidden';
  document.body.appendChild(probe);
  const hidden = getComputedStyle(probe).display;
  probe.remove();
  return {mainPadding: getComputedStyle(main).paddingLeft, radius: panel ? getComputedStyle(panel).borderTopLeftRadius : null,
          hiddenDisplay: hidden, bodyBg: getComputedStyle(document.body).backgroundColor};
}"""

AXE_JS = """async () => {
  const r = await axe.run(document, {resultTypes: ['violations']});
  return r.violations.map((v) => ({id: v.id, impact: v.impact, help: v.help,
    nodes: v.nodes.slice(0, 4).map((n) => n.target.join(' '))}));
}"""


def web_sources(dist: Path) -> dict:
    """The tracer's sources: the data files, plus the evidence-summary counts (documented formula)."""
    src = load_sources(dist / "data")
    ev = src["ui"]["evidence"]
    for ins in src["insights"].values():
        counts = Counter(ev[i]["event_type"] for i in ins["evidence_event_ids"] if i in ev)
        src["nums"].update(float(c) for c in counts.values())
    return src


def initial_js_gzip(dist: Path) -> dict:
    """Gzip size of the JS the first page load needs: the entry script and its modulepreloads."""
    html = (dist / "index.html").read_text(encoding="utf-8")
    files = re.findall(r'<script[^>]+src="\./([^"]+\.js)"', html) + re.findall(r'<link[^>]+modulepreload[^>]+href="\./([^"]+)"', html)
    sizes = {f: len(gzip.compress((dist / f).read_bytes(), 9)) for f in files}
    return dict(files=sizes, total_kb=round(sum(sizes.values()) / 1024, 1))


def _open(page, base, route, query=""):
    page.goto(f"{base}#/{route}" + (f"?{query}" if query else ""))
    page.wait_for_selector("body[data-ready='1']", timeout=20000)
    page.wait_for_selector(f"[data-page='{route}']", timeout=20000)
    page.wait_for_timeout(700)


def check_route(browser, base, route, width_name, src, screens: Path | None, axe_src: str) -> dict:
    w, h = WIDTHS[width_name]
    ctx, page, log = _context(browser, w, h)
    _open(page, base, route, QUERY.get(route, ""))
    r = dict(route=route, width=w, **page.evaluate("""() => ({
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth })"""))
    r["tailwind"] = page.evaluate(TAILWIND_JS)
    r["tailwind_ok"] = (r["tailwind"]["mainPadding"] == ("24px" if w >= 640 else "16px")
                        and r["tailwind"]["radius"] == "16px" and r["tailwind"]["hiddenDisplay"] == "none")
    r["overlap"] = page.evaluate(OVERLAP_JS)
    r["untraced"] = untraced_numbers(page.evaluate("() => document.body.innerText"), src)
    full = page.evaluate("() => document.body.textContent")
    r["forbidden"] = [wd for wd in FORBIDDEN if re.search(rf"\b{re.escape(wd)}", full, re.I)]
    r["attrs"] = {sel: page.evaluate("([s, a]) => [...document.querySelectorAll(s)].filter((e) => e.getAttribute(a)).length",
                                     [sel, attr]) for sel, attr in DATA_ATTRS[route]}
    if screens is not None:
        (screens / f"{route}_{width_name}.png").write_bytes(_shrink_png(page.screenshot(full_page=True)))
    page.add_script_tag(content=axe_src)
    r["axe"] = page.evaluate(AXE_JS)
    r["tab"] = _tab_order(page, FOCUSABLE_JS, WEB_ACTIVE_JS)
    r["problems"], r["remote"] = log["problems"], log["remote"]
    ctx.close()
    return r


def check_evidence_drawer(browser, base, src) -> dict:
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "live", "t=99999")
    out = {}
    buttons = page.locator("button[data-evidence]")
    picks = sorted({0, 1, buttons.count() - 1} | {i for i in range(buttons.count())
                    if buttons.nth(i).get_attribute("data-evidence") in src["ui"]["rewrites"]}, key=int)[:5]
    for i in picks:
        b = buttons.nth(i)
        iid = b.get_attribute("data-evidence")
        b.click()
        page.wait_for_selector("#drawer tr[data-event-id]", timeout=5000)
        ids = page.eval_on_selector_all("#drawer tr[data-event-id]", "els => els.map((e) => e.dataset.eventId)")
        attempts = page.eval_on_selector_all("#drawer li[data-claim-id]", "els => els.length")
        want = src["insights"][iid]["evidence_event_ids"]
        out[iid] = dict(listed=len(ids), expected=len(want), attempts=attempts, same=ids == [x for x in want if x in src["ui"]["evidence"]],
                        unknown=[x for x in ids if x not in want or x not in src["ui"]["evidence"]])
        page.keyboard.press("Escape")
        page.wait_for_selector("#drawer", state="detached", timeout=5000)
    out["_problems"] = log["problems"] + [f"remote: {u}" for u in log["remote"]]
    ctx.close()
    return out


def _set_lang(page, lang):
    page.click("#open-settings")
    page.click(f"[data-name='lang'][data-value='{lang}']")
    page.keyboard.press("Escape")
    page.wait_for_timeout(350)


def check_language_switch(browser, base, src) -> dict:
    """Headlines at full time in en, es, fr: same numbers, and each passes the number guard.
    Also every route's numbers are unchanged by the switch (decimal mark aside)."""
    from agents.narrative import number_guard
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "live", "t=99999")
    texts, routes = {}, {}
    for lang in ("en", "es", "fr"):
        _set_lang(page, lang)
        texts[lang] = page.eval_on_selector_all("li[data-insight-id]", """els => els.map((e) => [e.dataset.insightId,
            e.querySelector('[data-role=headline]').innerText])""")
    changed, guard = [], []
    for (iid, en), (_, es), (_, fr) in zip(texts["en"], texts["es"], texts["fr"]):
        if not (numbers_of(en) == numbers_of(es) == numbers_of(fr)):
            changed.append(iid)
        params = src["insights"][iid]["text"]["params"]
        for lang, t in (("en", en), ("es", es), ("fr", fr)):
            p = number_guard(t, params, lang)
            if p:
                guard.append((iid, lang, p))
    forbidden = [wd for wd in FORBIDDEN if re.search(rf"\b{re.escape(wd)}", page.evaluate("() => document.body.textContent"), re.I)]
    for route in ROUTES:
        nums = {}
        for lang in ("en", "fr"):
            _set_lang(page, lang)
            _open(page, base, route, "t=99999" if route == "live" else "")
            nums[lang] = sorted(numbers_of(page.evaluate("() => document.querySelector('main').innerText")))
        routes[route] = nums["en"] == nums["fr"]
    _set_lang(page, "en")
    ctx.close()
    return dict(cards=len(texts["en"]), changed=changed, guard=guard, forbidden_other_lang=forbidden,
                route_numbers_same=routes, problems=log["problems"])


def check_robustness(browser, base) -> dict:
    out = {}
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    page.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('storage blocked'); } });")
    _open(page, base, "live", QUERY["live"])
    page.click("#open-settings")
    page.click("#set-contrast")
    page.keyboard.press("Escape")
    out["storage_blocked"] = dict(cards=page.locator("li[data-insight-id]").count(),
                                  contrast=page.evaluate("() => document.documentElement.dataset.contrast"),
                                  problems=log["problems"])
    ctx.close()
    ctx, page, log = _context(browser, *WIDTHS["desktop"], reduced_motion="reduce")
    _open(page, base, "live", "t=60&play=1")
    page.wait_for_timeout(600)
    out["reduced_motion"] = dict(autoplay=page.get_attribute("#play", "aria-pressed"),
                                 motion=page.evaluate("() => document.documentElement.dataset.motion"),
                                 problems=log["problems"])
    ctx.close()
    return out


def check_replay_frames(browser, base, ms=4000) -> dict:
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "live", "t=0")
    page.click("[data-name='speed'][data-value='fast']")
    page.click("#play")
    res = page.evaluate(FRAMES_JS, ms)
    clock = page.inner_text("#clock")
    ctx.close()
    d = sorted(res["d"])
    if not d:
        return dict(frames=0, problems=log["problems"])
    pick = lambda q: round(d[min(len(d) - 1, int(q * len(d)))], 1)
    return dict(frames=len(d), mean_ms=round(sum(d) / len(d), 1), p50_ms=pick(0.5), p95_ms=pick(0.95),
                max_ms=round(d[-1], 1), over_33ms=sum(1 for x in d if x > 33.4), long_tasks=len(res["longs"]),
                clock_after=clock, problems=log["problems"])


def demo_screen(browser, base, screens: Path):
    ctx, page, log = _context(browser, 1920, 1080)
    _open(page, base, "live", QUERY["live"])
    (screens / "live_1080p.png").write_bytes(_shrink_png(page.screenshot()))
    ctx.close()
    return log["problems"]


def run(dist: Path | None = None, screens_dir: Path | None = None, screens: bool = True, routes=ROUTES) -> dict:
    from playwright.sync_api import sync_playwright
    dist = Path(dist or WEB / "dist")
    src = web_sources(dist)
    axe_src = (WEB / "node_modules" / "axe-core" / "axe.min.js").read_text(encoding="utf-8")
    shots = Path(screens_dir or ROOT / "docs" / "screens-v2") if screens else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    httpd = serve(dist)
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    report = {"routes": [], "bundle": initial_js_gzip(dist)}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            path = chromium_path()
            if not path:
                raise
            browser = p.chromium.launch(executable_path=path)
        for route in routes:
            for wn in WIDTHS:
                report["routes"].append(check_route(browser, base, route, wn, src, shots, axe_src))
        if "live" in routes:
            report["drawer"] = check_evidence_drawer(browser, base, src)
            report["robustness"] = check_robustness(browser, base)
            report["frames"] = check_replay_frames(browser, base)
            if shots:
                report["demo_problems"] = demo_screen(browser, base, shots)
        if set(routes) == set(ROUTES):
            report["language"] = check_language_switch(browser, base, src)
        browser.close()
    httpd.shutdown()
    report["failures"] = failures(report)
    return report


def failures(report) -> list:
    f = []
    for r in report["routes"]:
        tag = f"{r['route']}@{r['width']}"
        f += [f"{tag}: {x}" for x in r["problems"]]
        f += [f"{tag}: remote request {x}" for x in r["remote"]]
        if r["overflowX"]:
            f.append(f"{tag}: horizontal scroll ({r['scrollWidth']}px)")
        if not r["tailwind_ok"]:
            f.append(f"{tag}: Tailwind not applied {r['tailwind']}")
        f += [f"{tag}: overlapping text: {x}" for x in r["overlap"]["overlaps"]]
        if r["untraced"]:
            f.append(f"{tag}: untraced numbers {r['untraced'][:15]}")
        if r["forbidden"]:
            f.append(f"{tag}: forbidden words {r['forbidden']}")
        if r["tab"]["missing"]:
            f.append(f"{tag}: Tab never reaches {r['tab']['missing']}")
        f += [f"{tag}: axe {v['impact']} {v['id']}: {v['help']} {v['nodes']}" for v in r["axe"] if v["impact"] in AXE_FAIL]
        f += [f"{tag}: no element matches {sel} with its data attribute" for sel, n in r["attrs"].items() if not n]
    d = report.get("drawer")
    if d is not None:
        f += [f"drawer: {x}" for x in d["_problems"]]
        for iid, v in d.items():
            if iid != "_problems" and (v["unknown"] or not v["listed"] or not v["same"] or not v["attempts"]):
                f.append(f"drawer {iid}: {v}")
        if len(d) < 3:
            f.append("drawer: fewer than two evidence buttons checked")
    L = report.get("language")
    if L is not None:
        f += [f"language: numbers changed on {x}" for x in L["changed"]]
        f += [f"language: number guard {x}" for x in L["guard"]]
        f += [f"language: {x}" for x in L["problems"]]
        f += [f"language: numbers differ between en and fr on #/{r}" for r, ok in L["route_numbers_same"].items() if not ok]
        if L["forbidden_other_lang"]:
            f.append(f"language: forbidden words {L['forbidden_other_lang']}")
        if not L["cards"]:
            f.append("language: no cards at full time")
    R = report.get("robustness")
    if R is not None:
        f += [f"storage blocked: {x}" for x in R["storage_blocked"]["problems"]]
        if not R["storage_blocked"]["cards"] or R["storage_blocked"]["contrast"] != "high":
            f.append(f"storage blocked: {R['storage_blocked']}")
        f += [f"reduced motion: {x}" for x in R["reduced_motion"]["problems"]]
        if R["reduced_motion"]["autoplay"] != "false" or R["reduced_motion"]["motion"] != "reduce":
            f.append(f"reduced motion: {R['reduced_motion']}")
    if "frames" in report:
        f += [f"frames: {x}" for x in report["frames"].get("problems", [])]
    f += [f"demo screen: {x}" for x in report.get("demo_problems", [])]
    if report["bundle"]["total_kb"] >= 250:
        f.append(f"initial JS {report['bundle']['total_kb']} KB gzip (budget 250)")
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dist", default=str(WEB / "dist"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "screens-v2"), help="screenshot directory")
    ap.add_argument("--no-screens", action="store_true")
    ap.add_argument("--routes", default=",".join(ROUTES))
    ap.add_argument("--json", default=None, help="also write the full report here")
    a = ap.parse_args(argv)
    report = run(Path(a.dist), Path(a.out), screens=not a.no_screens, routes=tuple(a.routes.split(",")))
    for r in report["routes"]:
        bad_axe = [v["id"] for v in r["axe"] if v["impact"] in AXE_FAIL]
        print(f"{r['route']:8s} {r['width']:5d}px overflow_x={r['overflowX']!s:5s} tailwind={r['tailwind_ok']!s:5s} "
              f"text_runs={r['overlap']['count']:4d} overlaps={len(r['overlap']['overlaps'])} untraced={len(r['untraced'])} "
              f"controls={r['tab']['controls']:3d} tab_missing={len(r['tab']['missing'])} axe_serious={len(bad_axe)} "
              f"axe_minor={len(r['axe']) - len(bad_axe)} problems={len(r['problems'])} remote={len(r['remote'])} attrs={r['attrs']}")
    for k in ("drawer", "language", "robustness", "frames", "bundle"):
        if k in report:
            print(f"{k}:", {x: y for x, y in report[k].items() if x != "_problems"} if isinstance(report[k], dict) else report[k])
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=2, default=str))
    for x in report["failures"]:
        print("FAIL", x)
    if report["failures"]:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main()
