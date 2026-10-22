"""Headless check of the dashboard (app/): serve the repo, open every route at desktop and phone
width in Chromium, save screenshots to docs/screens/, and report every gate in docs/dashboard.md:

  * no console error, page error, failed request, HTTP error, or request to a host other than
    localhost; no horizontal scroll; no overlapping text; Tab reaches every control;
  * Tailwind applied (a known utility produces its computed style);
  * the evidence drawer opens and lists event ids that are in the stream;
  * every number on every route traces to the source data (out/*.json*) or to a documented
    formula (football clock time from clock seconds; counts of listed items);
  * switching language never changes a number, and every sentence passes the number guard;
  * no forbidden word (real club names, prediction or betting language);
  * the page still works with storage blocked and with reduced motion;
  * replay frame times while playing (reported, not a hard gate).

    python -m tools.check_dashboard            # needs out/ from agents.run_match
Requires requirements-ui.txt (Playwright, Pillow). Uses Playwright's own Chromium, or the one in
/opt/pw-browsers or the local Playwright cache when the bundled revision is missing.
"""
from __future__ import annotations

import argparse
import functools
import glob
import http.server
import io
import json
import os
import re
import threading
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
ROUTES = ("live", "teams", "players", "tech")
WIDTHS = {"desktop": (1440, 900), "mobile": (390, 844)}
QUERY = {"live": "t=2760"}               # the half-time moment: a rewritten Perimeter Lock card on top
MAX_SCREEN_BYTES = 300_000
FORBIDDEN = ("Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley", "Chelsea", "Crystal Palace",
             "Everton", "Fulham", "Ipswich", "Leeds United", "Leicester", "Liverpool", "Luton", "Manchester", "Newcastle",
             "Nottingham", "Sheffield United", "Southampton", "Sunderland", "Tottenham", "West Ham", "Wolverhampton",
             "Wolves", "Premier League", "predict", "will win", "going to win", "betting", "odds", "forecast",
             "bookmaker", "wager", "favourite to", "favorite to", "60,000", "60000")
LOCAL_HOSTS = {"127.0.0.1", "localhost"}


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


def serve(root=None):
    handler = functools.partial(_Quiet, directory=str(root or ROOT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ---------- source data: what a number on screen may be ----------

NUM = re.compile(r"-?\d+(?:[.,]\d+)?")
CLOCK = re.compile(r"(?<![\d.:])(\d{1,3}):(\d{2})(?![\d:])")
STOPPAGE = re.compile(r"(?<![\d.])(45|90)\+(\d{1,2})'?")
IDLIKE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*")


def load_sources(out_dir: Path) -> dict:
    rows = []
    for name in ("insights.jsonl", "claims.jsonl"):
        rows += [json.loads(l) for l in (out_dir / name).read_text(encoding="utf-8").splitlines() if l.strip()]
    timeline = json.loads((out_dir / "timeline.json").read_text(encoding="utf-8"))
    ui = json.loads((out_dir / "ui.json").read_text(encoding="utf-8"))
    nums, words = set(), set()

    def walk(v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            nums.add(round(abs(float(v)), 6))
        elif isinstance(v, str):
            words.add(v)
            words.update(re.split(r"[\s,;()\[\]|`*]+", v))
            for n in NUM.findall(v):
                nums.add(round(abs(float(n.replace(",", "."))), 6))
        elif isinstance(v, dict):
            nums.add(float(len(v)))
            for k, x in v.items():
                walk(k)
                walk(x)
        elif isinstance(v, list):
            nums.add(float(len(v)))
            for x in v:
                walk(x)
    walk(rows)
    walk(timeline)
    walk(ui)
    return dict(nums=nums, words={w.strip(".:") for w in words if w}, timeline=timeline, ui=ui,
                insights={r["insight_id"]: r for r in rows if "insight_id" in r})


def untraced_numbers(text: str, src: dict) -> list:
    """Numbers in rendered text that are neither in the source data nor a clock time."""
    dur = src["timeline"]["duration_sec"]
    bad = []

    def clock_ok(m):
        mm, ss = int(m.group(1)), int(m.group(2))
        return ss < 60 and mm * 60 + ss <= dur + 3600       # football time can run past elapsed seconds
    text = CLOCK.sub(lambda m: " " if clock_ok(m) else m.group(0), text)
    text = STOPPAGE.sub(" ", text)
    for w in IDLIKE.findall(text):
        if w.strip(".:") not in src["words"]:
            bad.append(w)
    text = IDLIKE.sub(" ", text)
    for n in NUM.findall(text):
        v = round(abs(float(n.replace(",", "."))), 6)
        if v not in src["nums"]:
            bad.append(n)
    return bad


def numbers_of(text: str) -> list:
    text = IDLIKE.sub(" ", text)
    return sorted(round(abs(float(n.replace(",", "."))), 6) for n in NUM.findall(text))


# ---------- page scripts ----------

OVERLAP_JS = """() => {
  const main = document.querySelector('main');
  const clipCache = new Map();
  const clipOf = (el) => {
    if (!el || el === document.documentElement) return {l: -1e9, t: -1e9, r: 1e9, b: 1e9};
    if (clipCache.has(el)) return clipCache.get(el);
    const p = clipOf(el.parentElement);
    const cs = getComputedStyle(el);
    let c = p;
    if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
      const b = el.getBoundingClientRect();
      c = {l: Math.max(p.l, b.left), t: Math.max(p.t, b.top), r: Math.min(p.r, b.right), b: Math.min(p.b, b.bottom)};
    }
    clipCache.set(el, c);
    return c;
  };
  const rects = [];
  const w = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  let n, k = 0;
  while ((n = w.nextNode())) {
    k++;
    const s = n.textContent.trim();
    if (!s) continue;
    const el = n.parentElement;
    if (el.closest('svg') || el.closest('.sr-only') || !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) continue;
    const c = clipOf(el);
    const r = document.createRange();
    r.selectNodeContents(n);
    for (const b of r.getClientRects()) {
      const l = Math.max(b.left, c.l), t = Math.max(b.top, c.t), rr = Math.min(b.right, c.r), bb = Math.min(b.bottom, c.b);
      if (rr - l > 1 && bb - t > 1) rects.push({l, t, r: rr, b: bb, s: s.slice(0, 40), k});
    }
  }
  rects.sort((a, b) => a.t - b.t);
  const out = [];
  for (let i = 0; i < rects.length; i++) {
    const a = rects[i];
    for (let j = i + 1; j < rects.length && rects[j].t < a.b; j++) {
      const b = rects[j];
      if (a.k === b.k) continue;            // one text node's own line boxes
      const ix = Math.min(a.r, b.r) - Math.max(a.l, b.l), iy = Math.min(a.b, b.b) - Math.max(a.t, b.t);
      if (ix > 2 && iy > 3) out.push(`${a.s} | ${b.s}`);
    }
  }
  return {count: rects.length, overlaps: out.slice(0, 20)};
}"""

FOCUSABLE_JS = """() => {
  const sel = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea, summary, [tabindex]';
  const els = [...document.querySelectorAll(sel)].filter((e) => e.tabIndex >= 0
    && (e.checkVisibility({checkVisibilityCSS: true}) || e.matches('.sr-only, .sr-only *'))
    && !e.closest('[inert]'));
  els.forEach((e, i) => e.setAttribute('data-tabcheck', String(i)));
  return els.length;
}"""

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

FRAMES_JS = """(ms) => new Promise((resolve) => {
  const d = []; let last = 0; const start = performance.now(); const longs = [];
  let po = null;
  try { po = new PerformanceObserver((l) => l.getEntries().forEach((e) => longs.push(e.duration))); po.observe({entryTypes: ['longtask']}); } catch (e) {}
  const f = (t) => { if (last) d.push(t - last); last = t; if (t - start < ms) requestAnimationFrame(f); else { po && po.disconnect(); resolve({d, longs}); } };
  requestAnimationFrame(f);
})"""


# ---------- views ----------

def _context(browser, w, h, **extra):
    ctx = browser.new_context(viewport={"width": w, "height": h}, **extra)
    page = ctx.new_page()
    log = {"problems": [], "remote": []}
    page.on("console", lambda m: log["problems"].append(f"console {m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: log["problems"].append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: log["problems"].append(f"requestfailed: {r.url}"))
    page.on("response", lambda r: log["problems"].append(f"http {r.status}: {r.url}") if r.status >= 400 else None)

    def on_request(r):
        u = urlparse(r.url)
        if u.scheme not in ("data", "blob") and u.hostname not in LOCAL_HOSTS:
            log["remote"].append(r.url)
    page.on("request", on_request)
    return ctx, page, log


def _open(page, base, route, query=""):
    page.goto(f"{base}#/{route}" + (f"?{query}" if query else ""))
    page.wait_for_selector("body[data-ready='1']", timeout=20000)
    page.wait_for_selector(f"[data-page='{route}']", timeout=20000)
    page.wait_for_timeout(500)


ACTIVE_JS = "() => document.activeElement && document.activeElement.getAttribute('data-tabcheck')"


def _tab_order(page, focusable_js=FOCUSABLE_JS, active_js=ACTIVE_JS) -> dict:
    n = page.evaluate(focusable_js)
    page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    seen = set()
    for _ in range(n + 5):
        page.keyboard.press("Tab")
        k = page.evaluate(active_js)
        if k is not None:
            seen.add(int(k))
    missing = sorted(set(range(n)) - seen)
    names = page.evaluate("(ids) => ids.map((i) => { const e = document.querySelector(`[data-tabcheck='${i}']`); "
                          "return e ? `${e.tagName.toLowerCase()} ${(e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 30)}` : String(i); })",
                          missing[:10])
    page.evaluate("() => window.scrollTo(0, 0)")
    return {"controls": n, "missing": names}


def _shrink_png(png: bytes) -> bytes:
    from PIL import Image
    img = Image.open(io.BytesIO(png)).convert("RGB")
    scale = 1.0
    while True:
        im = img if scale == 1.0 else img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(buf, "PNG", optimize=True)
        if buf.tell() <= MAX_SCREEN_BYTES or scale < 0.3:
            return buf.getvalue()
        scale *= 0.85


def check_route(browser, base, route, width_name, src, screens: Path | None) -> dict:
    w, h = WIDTHS[width_name]
    ctx, page, log = _context(browser, w, h)
    _open(page, base, route, QUERY.get(route, ""))
    r = dict(route=route, width=w, **page.evaluate("""() => ({
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth })"""))
    r["tailwind"] = page.evaluate(TAILWIND_JS)
    expected_pad = "24px" if w >= 640 else "16px"
    r["tailwind_ok"] = (r["tailwind"]["mainPadding"] == expected_pad and r["tailwind"]["radius"] == "16px"
                        and r["tailwind"]["hiddenDisplay"] == "none")
    r["overlap"] = page.evaluate(OVERLAP_JS)
    text = page.evaluate("() => document.body.innerText")
    r["untraced"] = untraced_numbers(text, src)
    full = page.evaluate("() => document.body.textContent")
    r["forbidden"] = [wd for wd in FORBIDDEN if re.search(rf"\b{re.escape(wd)}", full, re.I)]
    if screens is not None:
        png = page.screenshot(full_page=True)
        (screens / f"{route}_{width_name}.png").write_bytes(_shrink_png(png))
    r["tab"] = _tab_order(page)
    r["problems"], r["remote"] = log["problems"], log["remote"]
    ctx.close()
    return r


def check_evidence_drawer(browser, base, src) -> dict:
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "live", QUERY["live"])
    out = {}
    buttons = page.locator("button[data-evidence]")
    for i in range(min(3, buttons.count())):
        b = buttons.nth(i)
        iid = b.get_attribute("data-evidence")
        b.click()
        page.wait_for_selector("#drawer", timeout=5000)
        ids = page.eval_on_selector_all("#drawer tr[data-event-id]", "els => els.map((e) => e.dataset.eventId)")
        want = src["insights"][iid]["evidence_event_ids"]
        out[iid] = dict(listed=len(ids), expected=len(want),
                        unknown=[x for x in ids if x not in want or x not in src["ui"]["evidence"]])
        page.keyboard.press("Escape")
        page.wait_for_selector("#drawer", state="detached", timeout=5000)
    out["_problems"] = log["problems"] + [f"remote: {u}" for u in log["remote"]]
    ctx.close()
    return out


def check_language_switch(browser, base, src) -> dict:
    """Headlines at full time in en, es, fr: same numbers, and each passes the number guard."""
    from agents.narrative import number_guard
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "live", "t=99999")
    texts = {}
    for lang in ("en", "es", "fr"):
        page.click("#open-settings")
        page.click(f"label:has(input[data-lang='{lang}'])")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
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
    full = page.evaluate("() => document.body.textContent")
    forbidden = [wd for wd in FORBIDDEN if re.search(rf"\b{re.escape(wd)}", full, re.I)]
    # the language is persisted; reset it for the next context (each context has its own storage anyway)
    ctx.close()
    return dict(cards=len(texts["en"]), changed=changed, guard=guard, forbidden_fr=forbidden, problems=log["problems"])


def check_robustness(browser, base) -> dict:
    """Storage blocked, and reduced motion: still renders, no errors."""
    out = {}
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    page.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('storage blocked'); } });")
    _open(page, base, "live", QUERY["live"])
    page.click("#open-settings")
    page.click("label[for='set-contrast']")
    page.keyboard.press("Escape")
    out["storage_blocked"] = dict(cards=page.locator("li[data-insight-id]").count(), problems=log["problems"])
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
        return dict(frames=0)
    pick = lambda q: round(d[min(len(d) - 1, int(q * len(d)))], 1)
    return dict(frames=len(d), mean_ms=round(sum(d) / len(d), 1), p50_ms=pick(0.5), p95_ms=pick(0.95),
                max_ms=round(d[-1], 1), over_33ms=sum(1 for x in d if x > 33.4), over_50ms=sum(1 for x in d if x > 50),
                long_tasks=len(res["longs"]), clock_after=clock, problems=log["problems"])


def demo_screen(browser, base, screens: Path):
    """The first screen of #/live at 1080p, for the demo video."""
    ctx, page, log = _context(browser, 1920, 1080)
    _open(page, base, "live", QUERY["live"])
    (screens / "live_1080p.png").write_bytes(_shrink_png(page.screenshot()))
    ctx.close()
    return log["problems"]


def run(out_dir: Path | None = None, site_root: Path | None = None, screens: bool = True) -> dict:
    from playwright.sync_api import sync_playwright
    site = Path(site_root or ROOT)
    src = load_sources(site / "out")
    shots = Path(out_dir or ROOT / "docs" / "screens") if screens else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    httpd = serve(site)
    base = f"http://127.0.0.1:{httpd.server_address[1]}/app/"
    report = {"routes": []}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            path = chromium_path()
            if not path:
                raise
            browser = p.chromium.launch(executable_path=path)
        for route in ROUTES:
            for wn in WIDTHS:
                report["routes"].append(check_route(browser, base, route, wn, src, shots))
        report["drawer"] = check_evidence_drawer(browser, base, src)
        report["language"] = check_language_switch(browser, base, src)
        report["robustness"] = check_robustness(browser, base)
        report["frames"] = check_replay_frames(browser, base)
        if shots:
            report["demo_problems"] = demo_screen(browser, base, shots)
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
    d = report["drawer"]
    f += [f"drawer: {x}" for x in d["_problems"]]
    for iid, v in d.items():
        if iid != "_problems" and (v["unknown"] or not v["listed"]):
            f.append(f"drawer {iid}: {v}")
    if len(d) < 2:
        f.append("drawer: no evidence button found")
    L = report["language"]
    f += [f"language: numbers changed on {x}" for x in L["changed"]]
    f += [f"language: number guard {x}" for x in L["guard"]]
    f += [f"language: {x}" for x in L["problems"]]
    if L["forbidden_fr"]:
        f.append(f"language: forbidden words {L['forbidden_fr']}")
    if not L["cards"]:
        f.append("language: no cards at full time")
    R = report["robustness"]
    f += [f"storage blocked: {x}" for x in R["storage_blocked"]["problems"]]
    if not R["storage_blocked"]["cards"]:
        f.append("storage blocked: no cards rendered")
    f += [f"reduced motion: {x}" for x in R["reduced_motion"]["problems"]]
    if R["reduced_motion"]["autoplay"] != "false" or R["reduced_motion"]["motion"] != "reduce":
        f.append(f"reduced motion: {R['reduced_motion']}")
    f += [f"frames: {x}" for x in report["frames"].get("problems", [])]
    f += [f"demo screen: {x}" for x in report.get("demo_problems", [])]
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "docs" / "screens"), help="screenshot directory")
    ap.add_argument("--json", default=None, help="also write the full report here")
    a = ap.parse_args(argv)
    report = run(Path(a.out))
    for r in report["routes"]:
        print(f"{r['route']:8s} {r['width']:5d}px  overflow_x={r['overflowX']!s:5s} tailwind={r['tailwind_ok']!s:5s} "
              f"text_runs={r['overlap']['count']:4d} overlaps={len(r['overlap']['overlaps'])} untraced={len(r['untraced'])} "
              f"controls={r['tab']['controls']:3d} tab_missing={len(r['tab']['missing'])} problems={len(r['problems'])} remote={len(r['remote'])}")
    print("drawer:", {k: v for k, v in report["drawer"].items() if k != "_problems"})
    L = report["language"]
    print(f"language: {L['cards']} cards, numbers changed on {len(L['changed'])}, guard problems {len(L['guard'])}")
    print("robustness:", report["robustness"])
    print("replay frames:", report["frames"])
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=2, default=str))
    for x in report["failures"]:
        print("FAIL", x)
    if report["failures"]:
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main()
