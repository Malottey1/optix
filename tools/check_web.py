"""Headless check of the built dashboard (web/dist): serve it, open every route at desktop and phone
width in Chromium, save screenshots to docs/screens-v3/, and report every gate:

  * no console error, page error, failed request, HTTP error, or request to a host other than
    localhost; no horizontal scroll; no overlapping text; Tab reaches every control;
  * Tailwind applied (known utilities produce their computed style);
  * axe-core (injected from web/node_modules) finds no serious or critical violation;
  * every number on every route traces to the source data (web/dist/data, byte copies of out/) or
    to a documented formula: football clock time from clock seconds, the length of a listed
    collection, and the per-type counts of an insight's evidence events (the card's evidence
    summary: "15 events (pass 12, shot 3)"), and the visuals' formulas in docs/visuals.md (shot
    counts and xG sums per prefix, game-state values, route pass quality and xA per chance, pizza
    percentiles), each recomputed here independently of the page;
  * each visual matches the engine output (check_consistency): the crosshair sits on the verified
    claim's lane, the shot blocks are the claim window's shots and xG, the territorial-stress
    gauges end at the engine's spell totals, the arrows follow the pass counts (count and width
    order, in the default busiest-routes view and after "Show all routes"), the pizza shows the percentiles; --mutation-proof shows each check fails on a throwaway
    copy with that visual's data changed;
  * the evidence drawer lists exactly the claim's event ids, and every one exists in the stream;
  * the SVG layers carry data attributes tests can read (data-event-id, data-lane, data-team,
    data-claim-id);
  * switching language never changes a number, and every sentence passes the number guard;
  * SVG text renders at 11 px or more at phone width;
  * no forbidden word (real club names, prediction or betting language, invented statistics);
  * the page still works with storage blocked, and with reduced motion it does not autoplay;
  * the Live Center's first screen at 1920x1080 and 1600x900 shows every Live visual whole, with no
    overlapping text (check_first_screen);
  * replay frame p95 at most 20 ms (at 1440x900 and 1920x1080) and initial JS under 250 KB gzip.

    python -m tools.check_web               # needs web/dist (cd web && npm run build)
    python -m tools.check_web --ref out --mutation-proof
Shares its helpers with tools/check_dashboard.py (the legacy app/ checker).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
import shutil
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
    """The tracer's sources: the data files, plus the evidence-summary counts and the visuals'
    documented formulas (docs/visuals.md), recomputed here independently of the page."""
    src = load_sources(dist / "data")
    ev = src["ui"]["evidence"]
    for ins in src["insights"].values():
        counts = Counter(ev[i]["event_type"] for i in ins["evidence_event_ids"] if i in ev)
        src["nums"].update(float(c) for c in counts.values())
    src["nums"].update(round(abs(float(v)), 6) for v in visual_numbers(src["ui"], src["timeline"]["periods"]))
    return src


# ---------- the visuals' documented formulas (docs/visuals.md), independent of the page ----------

PIZZA_KEYS = ("involvement", "forward_passes", "pass_completion", "pass_quality_ratio", "chances_open_play",
              "wide_share", "chances_set_piece")
PIZZA_MIN_PASSES = 100
MIN_ROUTE_PASSES = 2
TOP_ROUTES = 8


def js_round(v: float, dp: int = 0) -> float:
    """Math.round(v * 10^dp) / 10^dp, as the page rounds (half up, not half to even)."""
    f = 10 ** dp
    return math.floor(v * f + 0.5) / f


def percentile(values, v):
    xs = [x for x in values if x is not None]
    if v is None or not xs:
        return None
    return 100 * (sum(1 for x in xs if x < v) + 0.5 * sum(1 for x in xs if x == v)) / len(xs)


def pizza(ui, pid) -> dict:
    """Displayed percentiles of one player against outfield players with >= 100 passes."""
    group = [p for p in ui["players"] if p["position"] != "GK" and p["passes"] >= PIZZA_MIN_PASSES]
    p = next(x for x in ui["players"] if x["id"] == pid)
    out = {}
    for k in PIZZA_KEYS:
        v = percentile([g[k] for g in group], p[k])
        out[k] = None if v is None else int(js_round(v))
    return out


def route_groups(rows, mode, top=None):
    """Routes of a mode, thickest first, ties by start zone, end zone, kind (fwd: only routes with
    >= MIN_ROUTE_PASSES passes); `top` keeps the busiest few, as the default view draws them."""
    g = [r for r in rows if (r[0] == "fwd" if mode == "fwd" else r[0] != "fwd")]
    g.sort(key=lambda r: (-r[3], r[1], r[2], r[0]))
    if top is not None:
        g = [r for r in g if r[3] >= MIN_ROUTE_PASSES] if mode == "fwd" else g
        return g[:top]
    return [r for r in g if r[3] >= MIN_ROUTE_PASSES] if mode == "fwd" else g


def stress_totals(ui) -> dict:
    """Per team: seconds pinned in its own half over the match (the opponent's spells)."""
    codes = sorted(ui["visuals"]["stress"])
    return {c: sum(s[2] for s in ui["visuals"]["stress"][o]) for c in codes for o in codes if o != c}


def zone_of(x, y, third_x):
    third = 2 if x >= third_x[1] else 1 if x >= third_x[0] else 0
    return third * 5 + min(4, int(y // 20))


def pct1(v):
    """Math.round(v * 1000) / 10, as ZoneShift shows a share in % to 1 dp."""
    return math.floor(v * 1000 + 0.5) / 10


def zone_shift_numbers(ui, periods, team) -> set:
    """V10: per half, the team's on-ball event count and share per zone (%, 1 dp); the shift in points."""
    if len(periods) < 2:
        return set()
    tx = ui["visuals"]["zones"]["third_x"]
    halves = []
    for p in periods[:2]:
        evs = [t for t in ui["track"] if t[3] == team and p["start_sec"] <= t[0] <= p["end_sec"]]
        c = Counter(zone_of(t[1], t[2], tx) for t in evs)
        halves.append((len(evs), [c[z] / len(evs) if evs else 0 for z in range(15)]))
    out = {float(halves[0][0]), float(halves[1][0])}
    for z in range(15):
        a, b = halves[0][1][z], halves[1][1][z]
        out |= {pct1(a), pct1(b), abs(pct1(b - a))}
    return out


def visual_numbers(ui, periods=()) -> set:
    v = ui["visuals"]
    out = set()
    for team in {s[2] for s in v["shots"]}:                 # shot panels and cards: every prefix
        xs = [s[6] for s in v["shots"] if s[2] == team]
        for k in range(1, len(xs) + 1):
            t = sum(xs[:k])
            out |= {k, js_round(t, 2), js_round(t / k, 3)}
    for st in v["states"].values():                          # V3 values as shown
        for b in st.values():
            if b["field_tilt"]["value"] is not None:
                out.add(js_round(b["field_tilt"]["value"] * 100, 1))
            if b["press_intensity"]["value"] is not None:
                out.add(js_round(b["press_intensity"]["value"], 3))
    ch = [r for rows in v["routes"].values() for r in rows if r[0] != "fwd"]
    league_xa = sum(r[4] for r in ch) / max(1, sum(r[3] for r in ch))
    out.add(js_round(league_xa, 3))
    for rows in v["routes"].values():                        # V4 per route and per player
        fwd = [r for r in rows if r[0] == "fwd"]
        for r in fwd:
            out.add(js_round(r[5] / r[3] / v["league_hot_share"], 2))
        n = sum(r[3] for r in fwd)
        if n:
            out.add(js_round(sum(r[5] for r in fwd) / n / v["league_hot_share"], 2))
        out.add(sum(r[3] for r in route_groups(rows, "fwd")))
        for mode in ("fwd", "chances"):                      # V4 default view and toggle
            full = route_groups(rows, mode)
            top = route_groups(rows, mode, TOP_ROUTES)
            out |= {len(full), len(top), sum(r[3] for r in top), sum(r[3] for r in full),
                    sum(r[3] for r in rows if (r[0] == "fwd") == (mode == "fwd"))}
        chances = [r for r in rows if r[0] != "fwd"]
        for r in chances:
            out.add(js_round(r[4] / r[3], 3))
        if chances:
            out.add(js_round(sum(r[4] for r in chances) / sum(r[3] for r in chances), 3))
    for team in {t[3] for t in ui["track"]}:                 # V10 per team and half, with the shift
        out |= zone_shift_numbers(ui, periods, team)
    for p in ui["players"]:                                  # V8
        out |= {x for x in pizza(ui, p["id"]).values() if x is not None}
    return out


def check_consistency(browser, base, ref_dir: Path) -> dict:
    """Each visual against the engine's own output in ref_dir (normally out/ or the committed data):
    the crosshair lane is the verified claim's lane, the shot blocks are the claim's shots and xG,
    the gauges end at the engine's spell totals, the arrows follow the pass counts (count and width
    order, default view and all routes), and the pizza shows the recomputed percentiles. Serving a mutated copy of the data makes these fail."""
    ref = load_sources(ref_dir)
    ui = ref["ui"]
    claims = {}
    for line in (ref_dir / "claims.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            a = json.loads(line)
            claims[a["claim"]["claim_id"]] = a["claim"]
    problems = []
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    # V1 on the Team Board: every ordered pair
    _open(page, base, "teams")
    pairs = 0
    for h in ui["teams"]["head_to_head"]:
        page.select_option("#h2h-attacker", h["attacker"])
        page.select_option("#h2h-defender", h["defender"])
        if (page.input_value("#h2h-attacker"), page.input_value("#h2h-defender")) != (h["attacker"], h["defender"]):
            page.select_option("#h2h-attacker", h["attacker"])
        got = page.get_attribute("#h2h [data-viz=crosshairs] svg[data-claim-lane]", "data-claim-lane")
        want = h["claim"]["lane"] if h["claim"] and h["claim"]["status"] != "blocked" else ""
        pairs += 1
        if got != want:
            problems.append(f"crosshair {h['attacker']}->{h['defender']}: lane {got!r}, claim says {want!r}")
    # V1, V2 and V5 on the Live Center at full time (a fresh page: the clock query is read on load)
    ctx.close()
    earlier = log["problems"]
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    log["problems"][:0] = earlier
    _open(page, base, "live", "t=99999")
    cards = page.eval_on_selector_all("[data-card-visual] svg[data-claim-id]", """els => els.map((e) => ({
        kind: e.closest('[data-card-visual]').dataset.cardVisual, claim: e.dataset.claimId,
        lane: e.dataset.claimLane ?? null, xg: e.dataset.xg ?? null,
        shots: [...e.querySelectorAll('rect[data-event-id]')].map((r) => r.dataset.eventId)}))""")
    seen = Counter(c["kind"] for c in cards)
    for c in cards:
        cl = claims.get(c["claim"])
        if cl is None:
            problems.append(f"card visual for unknown claim {c['claim']}")
            continue
        if c["kind"] == "crosshairs":
            want = (cl.get("zone") or {}).get("lane") if cl["verification"]["status"] != "blocked" else ""
            if c["lane"] != want:
                problems.append(f"card crosshair {c['claim']}: lane {c['lane']!r}, claim says {want!r}")
        if c["kind"] == "shot-blocks":
            w, team = cl["window"], cl["subject"]["team_code"]
            want_ids = [s[0] for s in ui["visuals"]["shots"] if s[2] == team and w["from_sec"] <= s[1] <= w["to_sec"]]
            if c["shots"] != want_ids or len(c["shots"]) != cl["value"]["sample_size"]:
                problems.append(f"shot blocks {c['claim']}: {len(c['shots'])} blocks, claim has {cl['value']['sample_size']}")
            if c["xg"] is None or abs(float(c["xg"]) - cl["value"]["amount"]) > 0.005:
                problems.append(f"shot blocks {c['claim']}: xG {c['xg']}, claim says {cl['value']['amount']}")
    for kind in ("crosshairs", "shot-blocks"):
        if not seen[kind]:
            problems.append(f"no {kind} card visual at full time")
    gauges = dict(page.eval_on_selector_all("[data-gauge]", """els => els.map((e) => [e.dataset.team,
        Number(e.querySelector('[data-role=stress-value]').dataset.value)])"""))
    for team, want in stress_totals(ui).items():
        if gauges.get(team) != want:
            problems.append(f"gauge {team}: {gauges.get(team)} s at full time, engine spells add up to {want} s")
    # V4 and V8 on the Player Deck: the default profile, in the default view (busiest routes) and
    # after "Show all routes"
    _open(page, base, "players")
    pid = page.get_attribute("#profile [data-viz=pass-routes] svg", "data-player")
    rows = ui["visuals"]["routes"].get(pid, [])
    views = {"top": route_groups(rows, "fwd", TOP_ROUTES), "all": route_groups(rows, "fwd")}
    arrows = {}
    for view, want in views.items():
        if view == "all":
            if len(views["all"]) <= TOP_ROUTES:
                problems.append(f"routes {pid}: no toggle to test (only {len(views['all'])} routes)")
                break
            page.click("#profile [data-role=route-toggle]")
            page.wait_for_selector("#profile [data-viz=pass-routes] svg[data-view=all]", timeout=5000)
        got = page.eval_on_selector_all("#profile [data-viz=pass-routes] [data-route]", """els => els.map((e) => [
            Number(e.dataset.value), Number(e.querySelector('path, circle').getAttribute('stroke-width'))])""")
        arrows[view] = len(got)
        if len(got) != len(want):
            problems.append(f"routes {pid} ({view}): {len(got)} arrows, data has {len(want)} routes")
        if sorted(a[0] for a in got) != sorted(r[3] for r in want):
            problems.append(f"routes {pid} ({view}): pass counts differ from the data")
        by_n = sorted(got)
        if any(b[1] < a[1] for a, b in zip(by_n, by_n[1:])):
            problems.append(f"routes {pid} ({view}): arrow width does not grow with the pass count")
    pz = dict(page.eval_on_selector_all("#profile [data-role=pizza-list] li", """els => els.map((e) => [
        e.dataset.metric, e.dataset.percentile === '' ? null : Number(e.dataset.percentile)])"""))
    if pz != pizza(ui, pid):
        problems.append(f"pizza {pid}: {pz} vs {pizza(ui, pid)}")
    ctx.close()
    return dict(pairs=pairs, cards=dict(seen), gauges=gauges, player=pid, arrows=arrows,
                problems=problems + log["problems"])


# ---------- mutation proof: each consistency check must fail when its data changes ----------

def _mut_crosshair(ui):
    h = next(h for h in ui["teams"]["head_to_head"] if h["claim"] and h["claim"]["status"] != "blocked")
    h["claim"]["lane"] = next(l for l in ("left_flank", "center") if l != h["claim"]["lane"])


def _mut_shots(ui):
    del ui["visuals"]["shots"][-1]


def _mut_gauge(ui):
    s = next(iter(ui["visuals"]["stress"].values()))[0]
    s[1] += 30
    s[2] += 30


def _mut_routes(ui):
    for rows in ui["visuals"]["routes"].values():
        r = next((r for r in rows if r[0] == "fwd" and r[3] >= MIN_ROUTE_PASSES), None)
        if r:
            r[3] += 5


def _mut_top_route(ui):
    for rows in ui["visuals"]["routes"].values():
        fwd = [r for r in rows if r[0] == "fwd"]
        if fwd:
            max(fwd, key=lambda r: r[3])[3] += 3


def _mut_pizza(ui):
    for p in ui["players"]:
        p["involvement"] = -p["involvement"]


# name: (mutation, the problem prefix that must appear, text that problem must contain)
MUTATIONS = {"crosshair": (_mut_crosshair, "crosshair", ""), "shot blocks": (_mut_shots, "shot blocks", ""),
             "gauge": (_mut_gauge, "gauge", ""), "routes": (_mut_routes, "routes", "(all)"),
             "routes default view": (_mut_top_route, "routes", "(top)"), "pizza": (_mut_pizza, "pizza", "")}


def mutation_proof(browser, dist: Path, ref_dir: Path, tmp: Path) -> dict:
    """Serve a throwaway copy of dist with one visual's data changed, run check_consistency against the
    unchanged ref_dir, and record whether that visual's check failed. The copy is left in tmp."""
    out = {}
    for name, (mutate, prefix, must) in MUTATIONS.items():
        copy = tmp / f"mut-{name.replace(' ', '-')}"
        shutil.copytree(dist, copy, dirs_exist_ok=True)   # always the current build
        ui = json.loads((ref_dir / "ui.json").read_text(encoding="utf-8"))
        mutate(ui)
        (copy / "data" / "ui.json").write_text(json.dumps(ui, separators=(",", ":")), encoding="utf-8")
        httpd = serve(copy)
        try:
            r = check_consistency(browser, f"http://127.0.0.1:{httpd.server_address[1]}/", ref_dir)
        finally:
            httpd.shutdown()
        hits = [x for x in r["problems"] if x.startswith(prefix) and must in x]
        out[name] = dict(caught=bool(hits), problems=hits[:3])
    return out


def initial_js_gzip(dist: Path) -> dict:
    """Gzip size of the JS the first page load needs: the entry script and its modulepreloads."""
    html = (dist / "index.html").read_text(encoding="utf-8")
    files = re.findall(r'<script[^>]+src="\./([^"]+\.js)"', html) + re.findall(r'<link[^>]+modulepreload[^>]+href="\./([^"]+)"', html)
    sizes = {f: len(gzip.compress((dist / f).read_bytes(), 9)) for f in files}
    return dict(files=sizes, total_kb=round(sum(sizes.values()) / 1024, 1))


MIN_SVG_PX = 11
SMALL_SVG_TEXT_JS = """() => [...document.querySelectorAll('svg text')]
  .filter((t) => t.getClientRects().length && t.textContent.trim())
  .map((t) => { const m = t.getScreenCTM();
    return [Math.round(parseFloat(getComputedStyle(t).fontSize) * Math.hypot(m.a, m.b) * 10) / 10,
            t.closest('[data-viz]')?.dataset.viz ?? t.closest('[id]')?.id ?? '', t.textContent.slice(0, 20)]; })
  .filter((x) => x[0] < %d)""" % MIN_SVG_PX


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
    r["small_svg_text"] = page.evaluate(SMALL_SVG_TEXT_JS) if w <= 400 else []
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


def check_navigation(browser, base) -> dict:
    """In-app navigation through the visible nav links at both widths (each route check opens a fresh
    page, so unmount and route-change bugs only show up here)."""
    out = {}
    for wn, (w, h) in WIDTHS.items():
        ctx, page, log = _context(browser, w, h)
        _open(page, base, "live", QUERY["live"])
        reached = []
        for route in [*ROUTES[1:], *ROUTES]:
            try:
                page.locator(f"a[href='#/{route}']:visible").last.click(timeout=5000)
                page.wait_for_selector(f"[data-page='{route}']", timeout=10000)
                reached.append(route)
            except Exception:
                reached.append(f"{route}:missing")
        out[wn] = dict(reached=reached, problems=log["problems"])
        ctx.close()
    return out


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


FRAME_P95_MS = 20
INITIAL_JS_KB = 250


def check_replay_frames(browser, base, ms=4000, size=WIDTHS["desktop"]) -> dict:
    ctx, page, log = _context(browser, *size)
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


FIRST_SCREENS = ((1920, 1080), (1600, 900))
# what the Live Center must show without scrolling on a wide screen (the demo video)
FIRST_SCREEN = {"focus pitch": "#focus", "perimeter lock": "#perimeter", "tug-of-war": "[data-testid=momentum-bar]",
                "stress gauges": "#stress", "rhythm pulse": "#rhythm", "shot quality": "#live-shots",
                "stream (top)": "#feed-panel > header"}


def check_first_screen(browser, base) -> dict:
    """At 1920x1080 and 1600x900 the Live Center's first screen, unscrolled, contains each visual's
    whole bounding box; no text overlaps; SVG text is at least MIN_SVG_PX."""
    out = {}
    for w, h in FIRST_SCREENS:
        ctx, page, log = _context(browser, w, h)
        _open(page, base, "live", QUERY["live"])
        boxes = page.evaluate("""(sel) => Object.fromEntries(Object.entries(sel).map(([k, s]) => {
            const e = document.querySelector(s); if (!e) return [k, null];
            const r = e.getBoundingClientRect(); return [k, [r.left, r.top, r.right, r.bottom]]; }))""", FIRST_SCREEN)
        problems = []
        for name, b in boxes.items():
            if b is None:
                problems.append(f"{name} missing")
            elif b[0] < 0 or b[1] < 0 or b[2] > w + 0.5 or b[3] > h + 0.5:
                problems.append(f"{name} not fully in the first screen: {[round(x) for x in b]}")
        ov = page.evaluate(OVERLAP_JS)
        small = page.evaluate(SMALL_SVG_TEXT_JS)
        problems += [f"overlapping text {x}" for x in ov["overlaps"][:5]]
        problems += [f"SVG text under {MIN_SVG_PX}px {x}" for x in small[:5]]
        out[f"{w}x{h}"] = dict(boxes={k: [round(x) for x in v] if v else None for k, v in boxes.items()},
                               problems=problems + log["problems"])
        ctx.close()
    return out


def demo_screen(browser, base, screens: Path):
    ctx, page, log = _context(browser, 1920, 1080)
    _open(page, base, "live", QUERY["live"])
    (screens / "live_1080p.png").write_bytes(_shrink_png(page.screenshot()))
    ctx.close()
    return log["problems"]


def run(dist: Path | None = None, screens_dir: Path | None = None, screens: bool = True, routes=ROUTES,
        ref_dir: Path | None = None) -> dict:
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
            report["frames_1080p"] = check_replay_frames(browser, base, size=(1920, 1080))
            report["first_screen"] = check_first_screen(browser, base)
            if shots:
                report["demo_problems"] = demo_screen(browser, base, shots)
        if set(routes) == set(ROUTES):
            report["consistency"] = check_consistency(browser, base, ref_dir or dist / "data")
            report["navigation"] = check_navigation(browser, base)
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
        if r.get("small_svg_text"):
            f.append(f"{tag}: SVG text under {MIN_SVG_PX}px {r['small_svg_text'][:5]}")
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
    f += [f"consistency: {x}" for x in report.get("consistency", {}).get("problems", [])]
    for wn, v in report.get("navigation", {}).items():
        f += [f"navigation@{wn}: {x}" for x in v["problems"]]
        f += [f"navigation@{wn}: never reached {x}" for x in v["reached"] if x.endswith(":missing")]
    R = report.get("robustness")
    if R is not None:
        f += [f"storage blocked: {x}" for x in R["storage_blocked"]["problems"]]
        if not R["storage_blocked"]["cards"] or R["storage_blocked"]["contrast"] != "high":
            f.append(f"storage blocked: {R['storage_blocked']}")
        f += [f"reduced motion: {x}" for x in R["reduced_motion"]["problems"]]
        if R["reduced_motion"]["autoplay"] != "false" or R["reduced_motion"]["motion"] != "reduce":
            f.append(f"reduced motion: {R['reduced_motion']}")
    for k in ("frames", "frames_1080p"):
        if k in report:
            f += [f"{k}: {x}" for x in report[k].get("problems", [])]
            if report[k].get("p95_ms", 0) > FRAME_P95_MS:
                f.append(f"{k}: p95 {report[k]['p95_ms']} ms over {FRAME_P95_MS} ms")
    for size, v in report.get("first_screen", {}).items():
        f += [f"first screen {size}: {x}" for x in v["problems"]]
    if report.get("bundle", {}).get("total_kb", 0) >= INITIAL_JS_KB:
        f.append(f"initial JS {report['bundle']['total_kb']} KB gzip, budget {INITIAL_JS_KB} KB")
    f += [f"demo screen: {x}" for x in report.get("demo_problems", [])]
    if report["bundle"]["total_kb"] >= 250:
        f.append(f"initial JS {report['bundle']['total_kb']} KB gzip (budget 250)")
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dist", default=str(WEB / "dist"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "screens-v3"), help="screenshot directory")
    ap.add_argument("--no-screens", action="store_true")
    ap.add_argument("--routes", default=",".join(ROUTES))
    ap.add_argument("--json", default=None, help="also write the full report here")
    ap.add_argument("--ref", default=None, help="engine output the visuals are checked against (default: dist/data)")
    ap.add_argument("--mutation-proof", action="store_true",
                    help="also show each consistency check fails on a throwaway copy with that visual's data changed")
    a = ap.parse_args(argv)
    report = run(Path(a.dist), Path(a.out), screens=not a.no_screens, routes=tuple(a.routes.split(",")),
                 ref_dir=Path(a.ref) if a.ref else None)
    if a.mutation_proof:
        import tempfile
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chromium_path())
            report["mutation_proof"] = mutation_proof(browser, Path(a.dist), Path(a.ref or Path(a.dist) / "data"), Path(tmp))
            report["failures"] += [f"mutation proof: {k} not caught" for k, v in report["mutation_proof"].items()
                                   if not v["caught"]]
    for r in report["routes"]:
        bad_axe = [v["id"] for v in r["axe"] if v["impact"] in AXE_FAIL]
        print(f"{r['route']:8s} {r['width']:5d}px overflow_x={r['overflowX']!s:5s} tailwind={r['tailwind_ok']!s:5s} "
              f"text_runs={r['overlap']['count']:4d} overlaps={len(r['overlap']['overlaps'])} untraced={len(r['untraced'])} "
              f"controls={r['tab']['controls']:3d} tab_missing={len(r['tab']['missing'])} axe_serious={len(bad_axe)} "
              f"axe_minor={len(r['axe']) - len(bad_axe)} problems={len(r['problems'])} remote={len(r['remote'])} attrs={r['attrs']}")
    for k in ("drawer", "consistency", "mutation_proof", "language", "robustness", "frames", "frames_1080p",
              "first_screen", "bundle"):
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
