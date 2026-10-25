"""Headless check of the built dashboard (web/dist): serve it, open every route at desktop and phone
width in Chromium, save screenshots to docs/screens-v7/, and report every gate:

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
  * no forbidden word (real club names, prediction or betting language, invented statistics) and no
    banned intent or causal wording (contracts/banned_language.json, all three languages);
  * the page still works with storage blocked, and with reduced motion it does not autoplay;
  * the Live Center's first screen at 1920x1080 and 1600x900 shows every Live visual whole, with no
    overlapping text (check_first_screen);
  * replay frame p95 at most 20 ms (at 1440x900 and 1920x1080) and initial JS under 250 KB gzip;
  * every route, Home (#/) included, is checked at 1440 and 390 px and also at 1920x1080 and 1600x900;
  * images (check_images): every <img> has alt (alt="" only with a visible name beside it) and
    width/height, the Home hero has fetchpriority=high, no shipped image carries EXIF/XMP/ICC/text,
    no file is over 300 KB (the hero 220 KB at 1600 px, 90 KB at 800 px); crests and mini-marks
    render at 24 and 32 px on the dark background (check_badges);
  * the Home hero text has at least 4.5:1 contrast against the pixels behind it, sampled from a
    screenshot with the text hidden (check_hero_contrast).

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
from urllib.parse import urlparse

from contracts import banned
from tools.check_dashboard import (FOCUSABLE_JS, FORBIDDEN, FRAMES_JS, OVERLAP_JS, _context, _shrink_png, _tab_order,
                                   chromium_path, load_sources, numbers_of, serve, untraced_numbers)

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
ROUTES = ("home", "fixtures", "hub_live", "hub_final", "teams", "team_board", "team_sheet", "players", "player",
          "player_df", "player_gk", "chance_drawer", "settings", "tech")
# hash path of a route when it is not the route's own name; `live` (the old link, redirected to the
# showcase hub) stays usable for the Live checks
SHOWCASE_HUB = "match/m_showcase"
FINAL_MATCH = "m_001"                    # a final with a verified lane claim (so the Matchup section shows)
BOARD_TEAM = "AUR"
CONSOLE_PLAYER = "NTG_07"                # has a fired context check (the Raw / With context toggle)
CONSOLE_DF = "CAL_05"                    # the defender console (defensive actions, action map)
CONSOLE_GK = "CAL_01"                    # the goalkeeper console (shots faced, distribution)
DRAWER_PLAYER = "NTG_11"                 # most chances created: the chance evidence drawer
PATH = {"home": "", "hub_live": SHOWCASE_HUB, "hub_final": f"match/{FINAL_MATCH}", "team_board": f"teams/{BOARD_TEAM}",
        "team_sheet": f"teams/{BOARD_TEAM}", "player": f"players/{CONSOLE_PLAYER}", "player_df": f"players/{CONSOLE_DF}",
        "player_gk": f"players/{CONSOLE_GK}", "chance_drawer": f"players/{DRAWER_PLAYER}", "settings": ""}
# the data-page a route renders when it is not the route's own name
PAGE = {"hub_live": "live", "hub_final": "hub", "team_board": "team-board", "team_sheet": "team-board",
        "player": "player", "player_df": "player", "player_gk": "player", "chance_drawer": "player",
        "settings": "home"}
# every route is also checked at the demo-video sizes (all gates, plus a first-screen shot)
EXTRA_SIZES = {r: {"1080p": (1920, 1080), "900p": (1600, 900)} for r in ROUTES}
WIDTHS = {"desktop": (1440, 900), "mobile": (390, 844)}
QUERY = {"live": "t=2760", "hub_live": "t=2760"}   # half-time stoppage: the rewritten Perimeter Lock card on top


def _open_sheet(page):
    """Team Board with the lineup mini-profile open (the first node)."""
    page.locator("[data-lineup] button[data-node]").first.click()
    page.wait_for_selector("#player-sheet a[data-ledger-link]", timeout=5000)
    page.wait_for_timeout(400)


def _open_drawer(page):
    """Player Console with the chance evidence drawer open."""
    page.locator("[data-open-chances]").click()
    page.wait_for_selector("#chance-evidence [data-chance-row]", timeout=10000)
    page.wait_for_timeout(400)


def _open_settings(page):
    """Home with the Settings sheet open."""
    page.locator("#open-settings").click()
    page.wait_for_selector("a[data-settings-tech]", timeout=5000)
    page.wait_for_timeout(400)


# what to do on a route after it loads, before the gates run
ACTIONS = {"team_sheet": _open_sheet, "chance_drawer": _open_drawer, "settings": _open_settings}
AXE_FAIL = {"serious", "critical"}
# what each route must expose for tests (selector -> attribute that must be non-empty)
DATA_ATTRS = {
    "home": [("[data-proof]", "data-proof"), ("[data-team-badge]", "data-team-badge"), ("img[data-hero]", "src")],
    "fixtures": [("a[data-fixture]", "href")],
    "hub_live": [("#pitch [data-event-id]", "data-event-id"), ("#pitch [data-team]", "data-team"),
                 ("[data-insight-id][data-claim-id]", "data-claim-id")],
    "hub_final": [("rect[data-bin]", "data-count"), ("[data-budget=card]", "data-budget"),
                  ("[data-matchup] svg[data-claim-lane]", "data-claim-lane")],
    "teams": [("a[data-team]", "data-team")],
    "team_board": [("button[data-node]", "data-node"), ("[data-signature-patterns]", "data-signature-patterns")],
    "team_sheet": [("#player-sheet a[data-ledger-link]", "href")],
    "players": [("a[data-player]", "href")],
    "player": [("[data-viz=pass-routes] [data-route]", "data-value"), ("#touch rect[data-bin]", "data-count"),
               ("[data-context]", "data-context")],
    "player_df": [("[data-def-rate]", "data-def-rate"), ("[data-points]", "data-count")],
    "player_gk": [("[data-viz=shots-faced] [data-result]", "data-count")],
    "chance_drawer": [("#chance-evidence a[data-play]", "href")],
    "settings": [("a[data-settings-tech]", "href")],
    "tech": [("tr[data-claim-id]", "data-claim-id"), ("[data-azure]", "data-state")],
}

# A Radix roving-focus group (toggle group, tab list) is one tab stop: its root takes focus and
# hands it to the active item (whose own tabindex is -1 until then). So the focused element counts
# for the nearest counted ancestor: reaching the item means the root's stop was reached.
# With a modal sheet open (team_sheet) focus is trapped by design: Tab must reach every control in
# the dialog and never leave it.
MODAL_FOCUSABLE_JS = FOCUSABLE_JS.replace("document.querySelectorAll(sel)",
                                          "document.querySelector('[role=dialog]').querySelectorAll(sel)")
assert MODAL_FOCUSABLE_JS != FOCUSABLE_JS

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

# Visible words: text a sighted reader sees. Skipped: closed <details> bodies (the summary counts),
# visually hidden text (sr-only, clipped, zero-size), display:none / visibility:hidden. A word is a
# whitespace token holding a letter or a digit. Grouped by the nearest [data-budget] ancestor
# (cards and sections declare their budget group), with the route total.
WORDS_JS = r"""() => {
  const hiddenCache = new Map();
  const hidden = (el) => {
    if (!el || el === document.body) return false;
    if (hiddenCache.has(el)) return hiddenCache.get(el);
    let h = false;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse') h = true;
    else if (el.classList.contains('sr-only')) h = true;
    else if (cs.position === 'absolute' && (cs.clip === 'rect(0px, 0px, 0px, 0px)' || cs.clipPath === 'inset(50%)')) h = true;
    else if (el.tagName === 'DETAILS' && false) h = true;
    else {
      const d = el.parentElement && el.parentElement.closest('details:not([open])');
      if (d && !el.closest('summary')) h = true;
      else h = hidden(el.parentElement);
    }
    hiddenCache.set(el, h);
    return h;
  };
  const groups = {};
  const each = new Map();   // budget element -> its words (nearest budget ancestor)
  let total = 0;
  const walker = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement;
    if (!el || ['SCRIPT', 'STYLE', 'TITLE', 'OPTION'].includes(el.tagName)) continue;
    if (el.closest('svg') && el.closest('title, desc')) continue;
    if (hidden(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 && r.height < 2) continue;
    const words = n.textContent.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
    if (!words) continue;
    total += words;
    const g = el.closest('[data-budget]');
    if (g) {
      const k = g.getAttribute('data-budget');
      groups[k] = (groups[k] || 0) + words;
      each.set(g, (each.get(g) || 0) + words);
    }
  }
  const label = (g) => g.dataset.team || g.dataset.player || g.dataset.insightId || g.dataset.fixture || g.id ||
    (g.textContent || '').trim().slice(0, 24);
  const elements = [...each].map(([g, n]) => [g.getAttribute('data-budget'), label(g), n]);
  return {total, groups, elements};
}"""

# Text budgets (words a sighted reader sees, WORDS_JS), one config: each element marked
# data-budget=<key> holds at most this many words of its own (text inside a nested budget element
# counts for that one). Match Hub recap sections are listed by their section id; the event log
# (budget "log") has none.
TEXT_BUDGETS = {"card": 30, "team-card": 20, "team-board": 180, "hub-header": 60, "turning": 60, "heat": 60,
                "cards": 60, "matchup": 60, "lineups": 120}


def budget_problems(words: dict) -> list:
    return [f"{k} {label!r}: {n} words, budget {TEXT_BUDGETS[k]}" for k, label, n in words["elements"]
            if k in TEXT_BUDGETS and n > TEXT_BUDGETS[k]]


# "lane" / "mismatch" in visible English text is allowed only inside [data-lane-ok]: the Tech
# worked example, the Match Hub's Matchup section (shown only with a verified lane claim), the
# lane-lift strip's label and the legend of a verified claim's crosshair.
LANE_JS = r"""() => {
  const out = [];
  const w = document.createTreeWalker(document.querySelector('main') || document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const el = n.parentElement;
    if (!el || !/\b(lanes?|mismatch\w*)\b/i.test(n.textContent)) continue;
    const cs = getComputedStyle(el);
    if (el.getBoundingClientRect().width < 2 || cs.visibility === 'hidden' || el.closest('.sr-only')) continue;
    if (el.closest('details:not([open])') && !el.closest('summary')) continue;
    if (el.closest('svg') && el.closest('title, desc')) continue;
    if (!el.closest('[data-lane-ok]')) out.push(n.textContent.trim().slice(0, 80));
  }
  return out;
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
    nums, words = match_sources(dist / "data")
    src["nums"] |= nums
    src["words"] |= words
    return src


def _walk(v, nums: set, words: set) -> None:
    """Every number and word in a JSON value, as load_sources collects them."""
    from tools.check_dashboard import NUM
    if isinstance(v, bool) or v is None:
        return
    if isinstance(v, (int, float)):
        nums.add(round(abs(float(v)), 6))
    elif isinstance(v, str):
        words.add(v.strip(".:"))
        words.update(w.strip(".:") for w in re.split(r"[\s,;()\[\]|`*]+", v) if w)
        nums.update(round(abs(float(n.replace(",", "."))), 6) for n in NUM.findall(v))
    elif isinstance(v, dict):
        nums.add(float(len(v)))
        for k, x in v.items():
            _walk(k, nums, words)
            _walk(x, nums, words)
    elif isinstance(v, list):
        nums.add(float(len(v)))
        for x in v:
            _walk(x, nums, words)


def _full_id(match_id: str, v) -> str:
    return f"{match_id}_e{v:05d}" if isinstance(v, int) else str(v)


def match_sources(data: Path) -> tuple:
    """The per-match recap files and player touch maps (data/matches): their numbers and words,
    the full event ids the page expands from the compact ones, and the heat maps' shown numbers
    recomputed here (heat_numbers)."""
    nums, words = set(), set()
    for p in sorted((data / "matches").glob("*.json")):
        f = json.loads(p.read_text(encoding="utf-8"))
        _walk(f, nums, words)
        mid = f.get("match_id")
        if mid:
            for row in f["events"]["rows"] + f["evidence"]["rows"]:
                words.add(_full_id(mid, row[0]))
            for c in f["claims"]:
                words.update(_full_id(mid, e) for e in c.get("evidence", []))
            for halves in f["heat"]["teams"].values():
                nums |= heat_numbers(f["heat"], halves)
        elif p.name.startswith("players-heat-"):
            for bins in f.get("players", {}).values():
                nums |= heat_numbers(f, bins)
        # players-<code>.json (defensive points, key passes, shots faced): every number is stored as
        # shown, so _walk above covers it
    return nums, words


# ---------- heat maps (web/src/lib/heat.ts), recomputed independently ----------

def _smooth(bins, cols, rows, sigma=1.0):
    r = max(1, math.ceil(3 * sigma))
    w = [math.exp(-(d * d) / (2 * sigma * sigma)) for d in range(-r, r + 1)]

    def one(src, along_x):
        n = cols if along_x else rows
        norm = [sum(w[d + r] for d in range(-r, r + 1) if 0 <= i + d < n) for i in range(n)]
        out = [0.0] * len(src)
        for row in range(rows):
            for col in range(cols):
                v = src[row * cols + col]
                if not v:
                    continue
                i = col if along_x else row
                for d in range(-r, r + 1):
                    j = i + d
                    if 0 <= j < n:
                        out[row * cols + j if along_x else j * cols + col] += v * w[d + r] / norm[i]
        return out
    return one(one(list(map(float, bins)), True), False)


def heat_density(grid, bins):
    cols, xe, ye = grid["cols"], grid["x_edges"], grid["y_edges"]
    sm = _smooth(bins, cols, grid["rows"])
    return [v / ((xe[b % cols + 1] - xe[b % cols]) * (ye[b // cols + 1] - ye[b // cols]) / 100)
            for b, v in enumerate(sm)]


def heat_zone_shares(grid, bins):
    lanes = [0, 0, 0, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 4, 4, 4]       # 3/3/4/3/3 rows per lane
    counts = [0] * 15
    for b, v in enumerate(bins):
        counts[(b % grid["cols"]) // 8 * 5 + lanes[b // grid["cols"]]] += v
    n = sum(counts)
    return [c / n if n else 0 for c in counts], n


def heat_numbers(grid, halves) -> set:
    """What a HeatPitch shows for one team or player: the legend's top (1 dp) for the whole match,
    each half and the change; the View data table's zone shares (%, 1 dp) and changes (points)."""
    out = set()
    a = halves[0]
    b = halves[1] if len(halves) > 1 else None
    views = [a] if b is None else [a, b, [x + y for x, y in zip(a, b)]]
    for bins in views:
        out.add(js_round(max(heat_density(grid, bins)), 1))
        out.add(float(sum(bins)))
    if b is not None:
        d1, d2 = heat_density(grid, a), heat_density(grid, b)
        out.add(js_round(max(abs(y - x) for x, y in zip(d1, d2)), 1))
        s1, _ = heat_zone_shares(grid, a)
        s2, _ = heat_zone_shares(grid, b)
        for x, y in zip(s1, s2):
            out |= {pct1(x), pct1(y), abs(js_round((y - x) * 1000) / 10)}
    return out


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


STYLE_IDS = ("tempo", "press", "directness", "territory", "counter")


def style_rows(ui, code) -> dict:
    """The Team Board's style rows recomputed from ui.json: id -> [value, chip] (StyleRows.tsx rule:
    highest / lowest of N only for a unique extreme, else about average within tolerance_rel of the
    league, else above / below)."""
    tol = ui["teams"]["style_rule"]["tolerance_rel"]
    teams = ui["teams"]["teams"]
    team = next(t for t in teams if t["code"] == code)
    out = {}
    for sid in STYLE_IDS:
        l = next((x for x in team["labels"] if x["id"] == sid), None)
        if not l or l["value"] is None or l["league"] is None:
            continue
        vals = [v for t in teams for x in t["labels"] if x["id"] == sid and (v := x["value"]) is not None]
        hi, lo = max(vals), min(vals)
        chip = ("highest" if l["value"] == hi and vals.count(hi) == 1 else
                "lowest" if l["value"] == lo and vals.count(lo) == 1 else
                "average" if abs(l["value"] - l["league"]) <= tol * abs(l["league"]) else
                "above" if l["value"] > l["league"] else "below")
        out[sid] = [l["value"], chip]
    return out


def pizza(ui, pid) -> dict:
    """Displayed percentiles of one player against players of the same listed position with >= 100
    passes."""
    p = next(x for x in ui["players"] if x["id"] == pid)
    group = [g for g in ui["players"] if g["position"] == p["position"] and g["passes"] >= PIZZA_MIN_PASSES]
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


def match_ref(ref_dir: Path) -> Path:
    """The per-match files to check against: ref_dir/matches (out/ after agents.match_export), else
    the committed web/public/data/matches (a freshly streamed showcase has no match files)."""
    return ref_dir / "matches" if (ref_dir / "matches").is_dir() else WEB / "public" / "data" / "matches"


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
    # The Match Hub's Matchup: every final with a verified lane claim at the display confidence
    # (ui teams.matchup_rule) shows its strips outlined on the claim's lane only, the lane's two season
    # lifts pass the claim's own thresholds, and a final without one has no Matchup section
    pairs = 0
    mref = match_ref(ref_dir)
    index = json.loads((mref / "index.json").read_text(encoding="utf-8"))
    for row in index["fixtures"]:
        if row["status"] != "final":
            continue
        f = json.loads((mref / f"{row['id']}.json").read_text(encoding="utf-8"))
        rule = ui["teams"]["matchup_rule"]
        want = {f"{mu['attacker']}-{mu['defender']}": mu["metrics"]["lane"] for mu in f.get("matchups", [])
                if mu.get("confidence") in rule["display_confidence"]}
        if not want and row["id"] not in (FINAL_MATCH, "m_007"):
            continue                                  # one final without a claim is enough
        page.goto(f"{base}#/match/{row['id']}")
        page.wait_for_selector(f"[data-page='hub'][data-match='{row['id']}']", timeout=20000)
        page.wait_for_timeout(300)
        got = dict(page.eval_on_selector_all("[data-matchup]", """els => els.map((e) => [e.dataset.matchup,
            [...e.querySelectorAll('svg[data-strip] [data-outline]')].map((o) => o.dataset.outline)])"""))
        pairs += len(want)
        if {k: v for k, v in got.items()} != {k: [l, l] for k, l in want.items()}:
            problems.append(f"matchup {row['id']}: page outlines {got}, verified claims {want}")
        h2h = {(h["attacker"], h["defender"]): h for h in ui["teams"]["head_to_head"]}
        for k, lane in want.items():
            a, d = k.split("-")
            l = h2h[(a, d)]["lanes"][lane]
            if not (l["attack_pp"] > rule["min_attack_pp"] and l["completion_pp"] > rule["min_completion_pp"]):
                problems.append(f"matchup {row['id']} {k}: lane {lane} lifts {l['attack_pp']}, {l['completion_pp']} fail the rule")
        if row["id"] == FINAL_MATCH:
            # heat: the bins' counts are the file's counts (both halves), team by team
            for code, halves in f["heat"]["teams"].items():
                if page.locator(f"[data-name='heat-team'][data-value='{code}']").count():
                    page.click(f"[data-name='heat-team'][data-value='{code}']")
                page.wait_for_selector(f"[data-viz=heat][data-team='{code}']", timeout=5000)
                counts = page.eval_on_selector_all("[data-viz=heat] rect[data-bin]", "els => els.map((e) => Number(e.dataset.count))")
                if counts != [x + y for x, y in zip(*halves[:2])]:
                    problems.append(f"heat {row['id']} {code}: bin counts differ from the match file")
    # the lineup pitch: the ref's most-used XI with the listed numbers, one node per player
    _open(page, base, "team_board")
    # Style against the league: each row's value and chip recomputed from ui.json
    page.wait_for_selector("[data-style-row]", timeout=10000)
    st = dict(page.eval_on_selector_all("[data-style-row]", """els => els.map((e) => [e.dataset.styleRow,
        [Number(e.dataset.value), e.dataset.chip]])"""))
    if st != style_rows(ui, BOARD_TEAM):
        problems.append(f"style rows {BOARD_TEAM}: page {st} vs {style_rows(ui, BOARD_TEAM)}")
    nodes = page.eval_on_selector_all("[data-lineup] button[data-node]", """els => els.map((e) => [e.dataset.node,
        Number(e.querySelector('svg text').textContent)])""")
    want_xi = [[n["id"], n["shirt"]] for n in ui["lineups"][BOARD_TEAM]["xi"]]
    if nodes != want_xi:
        problems.append(f"lineup {BOARD_TEAM}: {nodes} vs {want_xi}")
    # V1, V2 and V5 on the Live Center at full time (a fresh page: the clock query is read on load)
    ctx.close()
    earlier = log["problems"]
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    log["problems"][:0] = earlier
    _open(page, base, "hub_live", "t=99999")
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
        if c["kind"] == "shot-blocks" and (cl["metric"] == "pat_elastic_low_block" or "team_shots" in cl["params"]):
            # a deep-block card: the other side's shots (P4 claim) or the territory holder's own
            # shots (a territory claim the P4 rule rewrote), against the claim's count and xG per shot
            w, own = cl["window"], cl["metric"] != "pat_elastic_low_block"
            team = cl["subject"]["team_code"] if own else next(
                s[2] for s in ui["visuals"]["shots"] if s[2] != cl["subject"]["team_code"])
            n = cl["params"]["team_shots" if own else "opp_shots"]
            per = cl["params"]["team_xg_per_shot" if own else "xg_per_shot"]
            want_ids = [s[0] for s in ui["visuals"]["shots"] if s[2] == team and w["from_sec"] <= s[1] <= w["to_sec"]]
            if c["shots"] != want_ids or len(c["shots"]) != n:
                problems.append(f"shot blocks {c['claim']}: {len(c['shots'])} blocks of {team}, claim has {n}")
            if c["xg"] is None or not n or abs(float(c["xg"]) / n - per) > 0.001:
                problems.append(f"shot blocks {c['claim']}: xG {c['xg']} over {n} shots, claim says {per} a shot")
        elif c["kind"] == "shot-blocks":
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
    # V4 and V8 on the Player Console, in the default view (busiest routes) and after "Show all
    # routes"; the touch map's bins are the player's counts
    _open(page, base, "player")
    pid = page.get_attribute("#routes [data-viz=pass-routes] svg", "data-player")
    rows = ui["visuals"]["routes"].get(pid, [])
    views = {"top": route_groups(rows, "fwd", TOP_ROUTES), "all": route_groups(rows, "fwd")}
    arrows = {}
    for view, want in views.items():
        if view == "all":
            if len(views["all"]) <= TOP_ROUTES:
                problems.append(f"routes {pid}: no toggle to test (only {len(views['all'])} routes)")
                break
            page.click("#routes [data-role=route-toggle]")
            page.wait_for_selector("#routes [data-viz=pass-routes] svg[data-view=all]", timeout=5000)
        got = page.eval_on_selector_all("#routes [data-viz=pass-routes] [data-route]", """els => els.map((e) => [
            Number(e.dataset.value), Number(e.querySelector('path, circle').getAttribute('stroke-width'))])""")
        arrows[view] = len(got)
        if len(got) != len(want):
            problems.append(f"routes {pid} ({view}): {len(got)} arrows, data has {len(want)} routes")
        if sorted(a[0] for a in got) != sorted(r[3] for r in want):
            problems.append(f"routes {pid} ({view}): pass counts differ from the data")
        by_n = sorted(got)
        if any(b[1] < a[1] for a, b in zip(by_n, by_n[1:])):
            problems.append(f"routes {pid} ({view}): arrow width does not grow with the pass count")
    pz = dict(page.eval_on_selector_all("#pizza [data-role=pizza-list] li", """els => els.map((e) => [
        e.dataset.metric, e.dataset.percentile === '' ? null : Number(e.dataset.percentile)])"""))
    if pz != pizza(ui, pid):
        problems.append(f"pizza {pid}: {pz} vs {pizza(ui, pid)}")
    team = next(p["team"] for p in ui["players"] if p["id"] == pid)
    touch = json.loads((mref / f"players-heat-{team.lower()}.json").read_text(encoding="utf-8"))
    page.wait_for_selector("#touch rect[data-bin]", timeout=10000)
    counts = page.eval_on_selector_all("#touch rect[data-bin]", "els => els.map((e) => Number(e.dataset.count))")
    if counts != touch["players"][pid][0]:
        problems.append(f"touch map {pid}: bin counts differ from players-heat-{team.lower()}.json")
    problems += position_panel_problems(page, base, ui, mref)
    ctx.close()
    return dict(pairs=pairs, cards=dict(seen), gauges=gauges, player=pid, arrows=arrows,
                problems=problems + log["problems"])


def _lists(mref: Path, code: str) -> dict:
    return json.loads((mref / f"players-{code.lower()}.json").read_text(encoding="utf-8"))


def _player(ui, pid):
    return next(p for p in ui["players"] if p["id"] == pid)


def position_panel_problems(page, base, ui, mref: Path) -> list:
    """The defender map, the keeper shot map and the chance drawer against the team lists file, each
    recounted here, and their tiles against the profile."""
    problems = []
    df = _player(ui, CONSOLE_DF)
    page.goto("about:blank")                # a fresh document: every console shares data-page
    _open(page, base, "player_df")
    page.wait_for_selector("[data-viz=defence-map] [data-points]", timeout=10000)
    pts = _lists(mref, df["team"])["players"][CONSOLE_DF].get("defence", [])
    types = _lists(mref, df["team"])["point_types"]
    drawn = dict(page.eval_on_selector_all("[data-viz=defence-map] [data-points]", """els => els.map((e) => [
        e.dataset.points, e.querySelectorAll('circle, rect, path').length])"""))
    for i, k in enumerate(types):
        want = sum(1 for q in pts if q[2] == i)
        if drawn.get(k) != want:
            problems.append(f"defence map {CONSOLE_DF}: {k} {drawn.get(k)} markers, lists file has {want}")
    rows = dict(page.eval_on_selector_all("[data-def-rate]", """els => els.map((e) => [e.dataset.defRate,
        Number(e.querySelector('td').textContent)])"""))
    for r, v in rows.items():
        if v != df["profile"]["defence"][r]:
            problems.append(f"defensive actions {CONSOLE_DF}: {r} {v} vs profile {df['profile']['defence'][r]}")
    gk = _player(ui, CONSOLE_GK)
    page.goto("about:blank")
    _open(page, base, "player_gk")
    page.wait_for_selector("[data-viz=shots-faced] [data-result]", timeout=10000)
    shots = _lists(mref, gk["team"])["players"][CONSOLE_GK].get("shots_faced", [])
    got = dict(page.eval_on_selector_all("[data-viz=shots-faced] [data-result]", """els => els.map((e) => [
        e.dataset.result, e.querySelectorAll('circle').length])"""))
    for res in ("goal", "saved", "blocked", "off_target"):
        want = sum(1 for s in shots if s[4] == res)
        if got.get(res) != want:
            problems.append(f"shots faced {CONSOLE_GK}: {res} {got.get(res)} markers, lists file has {want}")
    k = gk["profile"]["keeper"]
    if got.get("saved") != k["saves"] or got.get("goal") != k["conceded"]:
        problems.append(f"shots faced {CONSOLE_GK}: saves/goals differ from the keeper profile")
    fw = _player(ui, DRAWER_PLAYER)
    page.goto("about:blank")
    _open(page, base, "chance_drawer")
    _open_drawer(page)
    chances = _lists(mref, fw["team"])["players"][DRAWER_PLAYER].get("chances", [])
    ids = page.eval_on_selector_all("#chance-evidence [data-chance-row]", "els => els.map((e) => e.dataset.chanceRow)")
    if ids != [c[0] for c in chances]:
        problems.append(f"chance drawer {DRAWER_PLAYER}: {len(ids)} rows, lists file has {len(chances)}")
    hrefs = page.eval_on_selector_all("#chance-evidence a[data-play]", "els => els.map((e) => e.getAttribute('href'))")
    want = [f"#/match/{c[0].rsplit('_e', 1)[0]}?t={c[1]}" for c in chances]
    if hrefs != want:
        problems.append(f"chance drawer {DRAWER_PLAYER}: play links differ from the chances' match and clock")
    if len(chances) != fw["profile"]["chances"]["total"]:
        problems.append(f"chance drawer {DRAWER_PLAYER}: lists file has {len(chances)}, profile total "
                        f"{fw['profile']['chances']['total']}")
    return problems


# ---------- mutation proof: each consistency check must fail when its data changes ----------

def _mut_file(copy: Path, name: str, change) -> None:
    p = copy / "data" / "matches" / name
    f = json.loads(p.read_text(encoding="utf-8"))
    change(f)
    p.write_text(json.dumps(f, separators=(",", ":")), encoding="utf-8")


def _mut_crosshair(ui, copy):
    def change(f):
        mu = next(m for m in f["matchups"] if m.get("confidence") in ui["teams"]["matchup_rule"]["display_confidence"])
        mu["metrics"]["lane"] = next(l for l in ("left_flank", "center") if l != mu["metrics"]["lane"])
    _mut_file(copy, f"{FINAL_MATCH}.json", change)


def _mut_heat(ui, copy):
    def change(f):
        f["heat"]["teams"][next(iter(f["heat"]["teams"]))][0][100] += 7
    _mut_file(copy, f"{FINAL_MATCH}.json", change)


def _mut_touch(ui, copy):
    team = next(p["team"] for p in ui["players"] if p["id"] == CONSOLE_PLAYER)
    _mut_file(copy, f"players-heat-{team.lower()}.json",
              lambda f: f["players"][CONSOLE_PLAYER][0].__setitem__(200, f["players"][CONSOLE_PLAYER][0][200] + 4))


def _mut_lineup(ui):
    xi = ui["lineups"][BOARD_TEAM]["xi"]
    xi[0]["shirt"], xi[1]["shirt"] = xi[1]["shirt"], xi[0]["shirt"]


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


def _mut_style(ui):
    team = next(t for t in ui["teams"]["teams"] if t["code"] == BOARD_TEAM)
    lab = next(x for x in team["labels"] if x["id"] == "press")
    lab["value"] = round(lab["value"] + 9.0, 1)


def _mut_defence_map(ui, copy):
    team = _player(ui, CONSOLE_DF)["team"]
    _mut_file(copy, f"players-{team.lower()}.json", lambda f: f["players"][CONSOLE_DF]["defence"].pop())


def _mut_shots_faced(ui, copy):
    team = _player(ui, CONSOLE_GK)["team"]

    def change(f):
        row = next(r for r in f["players"][CONSOLE_GK]["shots_faced"] if r[4] == "saved")
        row[4] = "off_target"
    _mut_file(copy, f"players-{team.lower()}.json", change)


def _mut_chances(ui, copy):
    team = _player(ui, DRAWER_PLAYER)["team"]

    def change(f):
        row = f["players"][DRAWER_PLAYER]["chances"][0]
        row[1] += 60
    _mut_file(copy, f"players-{team.lower()}.json", change)


def _mut_pizza(ui):
    for p in ui["players"]:
        p["involvement"] = -p["involvement"]


# name: (mutation, the problem prefix that must appear, text that problem must contain)
MUTATIONS = {"crosshair": (_mut_crosshair, "crosshair", ""), "heat": (_mut_heat, "heat", ""),
             "touch map": (_mut_touch, "touch map", ""), "lineup": (_mut_lineup, "lineup", ""),
             "shot blocks": (_mut_shots, "shot blocks", ""),
             "gauge": (_mut_gauge, "gauge", ""), "routes": (_mut_routes, "routes", "(all)"),
             "routes default view": (_mut_top_route, "routes", "(top)"), "pizza": (_mut_pizza, "pizza", ""),
             "style rows": (_mut_style, "style rows", ""),
             "defence map": (_mut_defence_map, "defence map", ""),
             "shots faced": (_mut_shots_faced, "shots faced", ""),
             "chance drawer": (_mut_chances, "chance drawer", "play links")}


def mutation_proof(browser, dist: Path, ref_dir: Path, tmp: Path) -> dict:
    """Serve a throwaway copy of dist with one visual's data changed, run check_consistency against the
    unchanged ref_dir, and record whether that visual's check failed. The copy is left in tmp."""
    out = {}
    for name, (mutate, prefix, must) in MUTATIONS.items():
        copy = tmp / f"mut-{name.replace(' ', '-')}"
        shutil.copytree(dist, copy, dirs_exist_ok=True)   # always the current build
        ui = json.loads((ref_dir / "ui.json").read_text(encoding="utf-8"))
        # a mutation changes ui.json, or (two arguments) a match file in the copy
        mutate(ui, copy) if mutate.__code__.co_argcount == 2 else mutate(ui)
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


def _path(route):
    return PATH.get(route, route)


def _open(page, base, route, query=""):
    page.goto(f"{base}#/{_path(route)}" + (f"?{query}" if query else ""))
    page.wait_for_selector("body[data-ready='1']", timeout=20000)
    page.wait_for_selector(f"[data-page='{PAGE.get(route, route)}']", timeout=20000)
    page.wait_for_timeout(700)


def check_route(browser, base, route, width_name, src, screens: Path | None, axe_src: str, size=None) -> dict:
    w, h = size or WIDTHS[width_name]
    ctx, page, log = _context(browser, w, h)
    _open(page, base, route, QUERY.get(route, ""))
    if route in ACTIONS:
        ACTIONS[route](page)
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
    r["forbidden"] = [wd for wd in FORBIDDEN if re.search(rf"\b{re.escape(wd)}", full, re.I)] + banned.find(full)
    r["images"] = page.evaluate(IMG_JS)
    r["words"] = page.evaluate(WORDS_JS)
    r["budget"] = budget_problems(r["words"])
    r["lane"] = page.evaluate(LANE_JS)
    r["attrs"] = {sel: page.evaluate("([s, a]) => [...document.querySelectorAll(s)].filter((e) => e.getAttribute(a)).length",
                                     [sel, attr]) for sel, attr in DATA_ATTRS[route]}
    if screens is not None:
        _load_lazy_images(page)
        (screens / f"{route}_{width_name}.png").write_bytes(
            _shrink_png(page.screenshot(full_page=size is None)))
    page.add_script_tag(content=axe_src)
    r["axe"] = page.evaluate(AXE_JS)
    modal = route in ACTIONS
    r["tab"] = _tab_order(page, MODAL_FOCUSABLE_JS if modal else FOCUSABLE_JS, WEB_ACTIVE_JS)
    if modal:
        page.keyboard.press("Tab")
        r["focus_trapped"] = page.evaluate("() => !!document.activeElement?.closest('[role=dialog]')")
    r["problems"], r["remote"] = log["problems"], log["remote"]
    ctx.close()
    return r


def check_evidence_drawer(browser, base, src) -> dict:
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "hub_live", "t=99999")
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
    _open(page, base, "hub_live", "t=99999")
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
    body = page.evaluate("() => document.body.textContent")
    forbidden = [wd for wd in FORBIDDEN if re.search(rf"\b{re.escape(wd)}", body, re.I)] + banned.find(body)
    for route in ROUTES:
        nums = {}
        for lang in ("en", "fr"):
            _set_lang(page, lang)
            _open(page, base, route, "t=99999" if route == "hub_live" else "")
            nums[lang] = sorted(numbers_of(page.evaluate("() => document.querySelector('main').innerText")))
        routes[route] = nums["en"] == nums["fr"]
    _set_lang(page, "en")
    ctx.close()
    return dict(cards=len(texts["en"]), changed=changed, guard=guard, forbidden_other_lang=forbidden,
                route_numbers_same=routes, problems=log["problems"])


NAV = ("fixtures", "teams", "players", "tech", "home")     # the nav bar's links; tech is reached through Settings


def check_text_budget_proof(browser, base) -> dict:
    """The text budget and the lane scan fail when the page breaks them: words added to a Team Grid
    card, a Player Deck card and the Team Board, and a lane sentence outside the allowed places."""
    out = {}
    cases = (("teams", "[data-budget=team-card]", 15, "team-card"), ("players", "[data-budget=card]", 25, "card"),
             ("team_board", "[data-budget=team-board] h1", 40, "team-board"))
    for route, sel, n, key in cases:
        ctx, page, log = _context(browser, *WIDTHS["desktop"])
        _open(page, base, route)
        page.eval_on_selector(sel, "(e, n) => { const p = document.createElement('p'); "
                                   "p.textContent = Array(n).fill('word').join(' '); e.appendChild(p); }", n)
        hits = [x for x in budget_problems(page.evaluate(WORDS_JS)) if x.startswith(key + " ")]
        out[f"budget {key}"] = dict(caught=bool(hits), problems=hits[:2])
        ctx.close()
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "hub_final")
    page.eval_on_selector("#turning", "(e) => { const p = document.createElement('p'); "
                                      "p.textContent = 'Lane mismatch on the left'; e.appendChild(p); }")
    hits = page.evaluate(LANE_JS)
    out["lane wording"] = dict(caught=bool(hits), problems=hits[:2])
    ctx.close()
    return out


HUB_GAP_PX = 96
HUB_GAP_JS = r"""() => {
  const out = {gaps: [], panel: null, vh: innerHeight};
  const secs = [...document.querySelectorAll('[data-hub-column=main] section[id], [data-hub-column=main] > a[data-ledger-link]')];
  const top = (e) => e.getBoundingClientRect().top + scrollY, bottom = (e) => e.getBoundingClientRect().bottom + scrollY;
  for (let i = 1; i < secs.length; i++) out.gaps.push([secs[i - 1].id || 'ledger', secs[i].id || 'ledger', Math.round(top(secs[i]) - bottom(secs[i - 1]))]);
  const p = document.querySelector('#insights[data-panel=side]');
  if (p) out.panel = Math.round(p.getBoundingClientRect().height);
  return out;
}"""
# reintroduces the old layout: Heat Maps beside a full-height card column, Matchup after the row
HUB_OLD_LAYOUT_JS = r"""() => {
  const heat = document.getElementById('heat'), panel = document.getElementById('insights');
  const row = document.createElement('div');
  row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start';
  heat.replaceWith(row); row.appendChild(heat);
  panel.style.position = 'static'; panel.style.height = 'auto';
  panel.querySelector('[data-scroll-region]').style.overflow = 'visible';
  row.appendChild(panel);
}"""


def hub_layout_problems(m: dict) -> list:
    f = [f"empty gap of {g}px between {a} and {b} (max {HUB_GAP_PX})" for a, b, g in m["gaps"] if g > HUB_GAP_PX]
    if m["panel"] is not None and m["panel"] > m["vh"]:
        f.append(f"insights panel {m['panel']}px taller than the viewport {m['vh']}px")
    return f


def check_hub_layout(browser, base) -> dict:
    """Match Hub (final): no empty gap over HUB_GAP_PX between consecutive sections of the main
    column, and the side panel never taller than the viewport, at every size; plus the proof that
    the old layout (cards beside Heat Maps, Matchup after the row) is caught."""
    out = {}
    for name, (w, h) in {**WIDTHS, "1080p": (1920, 1080), "900p": (1600, 900)}.items():
        ctx, page, log = _context(browser, w, h)
        _open(page, base, "hub_final")
        page.wait_for_selector("#insights", timeout=10000)
        m = page.evaluate(HUB_GAP_JS)
        out[name] = dict(gaps=m["gaps"], panel=m["panel"], problems=hub_layout_problems(m) + log["problems"])
        if name == "desktop":
            page.evaluate(HUB_OLD_LAYOUT_JS)
            page.wait_for_timeout(200)
            hits = hub_layout_problems(page.evaluate(HUB_GAP_JS))
            out["old_layout_proof"] = dict(caught=bool(hits), problems=hits[:2])
        ctx.close()
    return out


def check_navigation(browser, base) -> dict:
    """In-app navigation through the visible nav links at both widths (each route check opens a fresh
    page, so unmount and route-change bugs only show up here)."""
    out = {}
    for wn, (w, h) in WIDTHS.items():
        ctx, page, log = _context(browser, w, h)
        _open(page, base, "hub_live", QUERY["hub_live"])
        reached = []
        for route in [*NAV, *NAV]:
            try:
                if route == "tech":      # not in the primary nav: Settings -> Technical details
                    page.locator("#open-settings").click(timeout=5000)
                    page.locator("a[data-settings-tech]").click(timeout=5000)
                else:
                    page.locator(f"nav a[href='#/{_path(route)}']:visible").last.click(timeout=5000)
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
    _open(page, base, "hub_live", QUERY["hub_live"])
    page.click("#open-settings")
    page.click("#set-contrast")
    page.keyboard.press("Escape")
    out["storage_blocked"] = dict(cards=page.locator("li[data-insight-id]").count(),
                                  contrast=page.evaluate("() => document.documentElement.dataset.contrast"),
                                  problems=log["problems"])
    ctx.close()
    ctx, page, log = _context(browser, *WIDTHS["desktop"], reduced_motion="reduce")
    _open(page, base, "hub_live", "t=60&play=1")
    page.wait_for_timeout(600)
    out["reduced_motion"] = dict(autoplay=page.get_attribute("#play", "aria-pressed"),
                                 motion=page.evaluate("() => document.documentElement.dataset.motion"),
                                 problems=log["problems"])
    ctx.close()
    return out


def _serve_api(dist: Path):
    """The Optix API (service/app.py) on a free local port, serving `dist` and its data."""
    import socket
    import threading
    import time

    import uvicorn

    from service.app import create_app
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(create_app(dist / "data", dist), host="127.0.0.1", port=port,
                                           log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}/"


def check_live_stream(browser, dist: Path, static_base: str) -> dict:
    """Served by the API: the chip says Live stream, cards arrive one by one over SSE, and every
    request is same-origin (the page, its data, /healthz and /api/...). Served statically: Replay."""
    out = {"problems": []}
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, static_base, "hub_live")
    out["static_chip"] = page.get_attribute("[data-source]", "data-source")
    out["problems"] += [f"static: {x}" for x in log["problems"] + log["remote"]]
    ctx.close()
    server, base = _serve_api(dist)
    try:
        ctx, page, log = _context(browser, *WIDTHS["desktop"])
        urls = []
        page.on("request", lambda r: urls.append(r.url))
        _open(page, base, "hub_live")
        page.wait_for_selector("[data-source='live']", timeout=10000)
        first = page.locator("li[data-insight-id]").count()
        page.wait_for_function("() => document.querySelectorAll('li[data-insight-id]').length >= 3", timeout=20000)
        out.update(live_chip=page.get_attribute("[data-source]", "data-source"),
                   chip_text=page.inner_text("[data-source]"), cards_at_open=first,
                   cards_later=page.locator("li[data-insight-id]").count(),
                   api_calls=sorted({urlparse(u).path for u in urls if "/api/" in u or u.endswith("/healthz")}),
                   other_origin=[u for u in urls if not u.startswith(base) and not u.startswith(("data:", "blob:"))])
        out["problems"] += [f"live: {x}" for x in log["problems"] + log["remote"]]
        ctx.close()
    finally:
        server.should_exit = True
    return out


FRAME_P95_MS = 20
INITIAL_JS_KB = 250


def check_replay_frames(browser, base, ms=4000, size=WIDTHS["desktop"]) -> dict:
    ctx, page, log = _context(browser, *size)
    _open(page, base, "hub_live", "t=0")
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


# ---------- images, crests and the Home hero ----------

IMG_JS = """() => [...document.querySelectorAll('img')].map((i) => {
  let named = false;
  for (let e = i.parentElement, k = 0; e && k < 3; e = e.parentElement, k++) {
    if ((e.innerText || '').trim()) { named = true; break; }
  }
  return {src: i.getAttribute('src'), alt: i.getAttribute('alt'), w: i.getAttribute('width'),
          h: i.getAttribute('height'), fp: i.getAttribute('fetchpriority'), hero: i.hasAttribute('data-hero'),
          loading: i.getAttribute('loading'), named};
})"""
IMG_MAX = 300_000
IMG_BUDGET = {"hero-lineup-1600.webp": 220_000, "hero-lineup-800.webp": 90_000}
RASTER = (".png", ".webp", ".jpg", ".jpeg", ".ico", ".gif", ".avif")


def image_problems(images, route) -> list:
    out = []
    for i in images:
        tag = i["src"]
        if i["alt"] is None:
            out.append(f"{tag}: no alt")
        elif i["alt"] == "" and not i["named"]:
            out.append(f"{tag}: alt=\"\" with no visible name beside it")
        if not (i["w"] and i["h"]):
            out.append(f"{tag}: no width/height")
        if not i["hero"] and i["loading"] != "lazy":
            out.append(f"{tag}: not lazy-loaded")
    if route == "home":
        heroes = [i for i in images if i["hero"]]
        if len(heroes) != 1 or heroes[0]["fp"] != "high":
            out.append(f"Home hero missing or without fetchpriority=high: {heroes}")
    return out


def check_image_files(dist: Path) -> dict:
    """Every shipped raster: no EXIF/XMP/ICC/text, and within its size budget."""
    from tools.image_meta import metadata_chunks
    files = [p for p in dist.rglob("*") if p.suffix.lower() in RASTER and "data" not in p.relative_to(dist).parts]
    problems = []
    for p in files:
        meta = metadata_chunks(p)
        if meta:
            problems.append(f"{p.relative_to(dist)} carries {meta}")
        limit = IMG_BUDGET.get(p.name, IMG_MAX)
        if p.stat().st_size > limit:
            problems.append(f"{p.relative_to(dist)} is {p.stat().st_size} bytes, budget {limit}")
    largest = max(files, key=lambda p: p.stat().st_size) if files else None
    return dict(files=len(files), problems=problems,
                largest=[str(largest.relative_to(dist)), largest.stat().st_size] if largest else None,
                hero={n: (dist / "brand" / n).stat().st_size for n in IMG_BUDGET if (dist / "brand" / n).exists()})


BADGE_SHEET_JS = """(sizes) => {
  const codes = ['AUR', 'NTG', 'CAL', 'VES', 'HAR'];
  const box = document.createElement('div');
  box.id = 'badge-sheet';
  box.style.cssText = 'position:fixed;left:0;top:0;z-index:99;background:#05080f;padding:12px;display:grid;gap:10px';
  for (const s of sizes) {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:12px;align-items:center';
    for (const c of codes) {
      const mini = document.querySelector(`[data-badge=mini][data-team-badge=${c}]`).cloneNode(true);
      Object.assign(mini.style, {width: s + 'px', height: s + 'px', fontSize: Math.max(9, Math.round(s * 0.37)) + 'px'});
      mini.dataset.check = `mini-${c}-${s}`;
      const img = document.createElement('img');
      img.src = `./brand/teams/badge-${c.toLowerCase()}-96.webp`; img.width = s; img.height = s; img.alt = '';
      img.dataset.check = `crest-${c}-${s}`;
      row.append(mini, img);
    }
    box.append(row);
  }
  document.body.append(box);
  return Promise.all([...box.querySelectorAll('img')].map((i) => i.decode().then(() => i.naturalWidth)));
}"""


def _ink(png: bytes, bg=(5, 8, 15)) -> tuple:
    """Share of pixels that differ from the dark background, and share of dark pixels (the code text)."""
    import io
    from PIL import Image
    b = Image.open(io.BytesIO(png)).convert("RGB").tobytes()
    px = [tuple(b[i:i + 3]) for i in range(0, len(b), 3)]
    far = sum(1 for p in px if sum(abs(a - b) for a, b in zip(p, bg)) > 60) / len(px)
    return far, px


def check_badges(browser, base, shots: Path | None) -> dict:
    """Crests and code mini-marks at 24 and 32 px on the dark background: each shows ink, and each
    mini-mark's disc carries dark code text (a disc alone would be one flat colour)."""
    ctx, page, log = _context(browser, *WIDTHS["desktop"])
    _open(page, base, "players")
    loaded = page.evaluate(BADGE_SHEET_JS, [24, 32])
    page.wait_for_timeout(200)
    problems, cells = [], {}
    if not all(loaded):
        problems.append(f"crest image did not decode: {loaded}")
    for el in page.query_selector_all("#badge-sheet [data-check]"):
        name = el.get_attribute("data-check")
        far, px = _ink(el.screenshot())
        cells[name] = round(far, 2)
        if name.startswith("crest") and far < 0.3:
            problems.append(f"{name}: crest barely visible on dark ({far:.2f} of pixels)")
        if name.startswith("mini"):
            disc = sum(1 for p in px if max(p) > 90)
            text = sum(1 for p in px if max(p) < 60)
            if far < 0.55 or text / len(px) < 0.03 or disc / len(px) < 0.4:
                problems.append(f"{name}: disc {disc / len(px):.2f}, code text {text / len(px):.2f}")
    if shots:
        (shots / "badges_24_32.png").write_bytes(page.locator("#badge-sheet").screenshot())
    ctx.close()
    return dict(cells=cells, problems=problems + log["problems"])


HERO_SIZES = {"1440": WIDTHS["desktop"], "1080p": (1920, 1080), "900p": (1600, 900), "390": WIDTHS["mobile"]}


def _lum(rgb) -> float:
    def f(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def check_hero_contrast(browser, base) -> dict:
    """Hide the hero text, screenshot the boxes it occupied, and compare the text colour with the
    lightest pixels behind it (99.5th percentile of luminance): at least 4.5:1."""
    import io
    from PIL import Image
    out = {}
    for name, (w, h) in HERO_SIZES.items():
        ctx, page, log = _context(browser, w, h)
        _open(page, base, "home")
        page.wait_for_function("() => document.querySelector('img[data-hero]').complete")
        colours = page.eval_on_selector_all("[data-hero-text]", "els => els.map((e) => getComputedStyle(e).color)")
        page.add_style_tag(content="[data-hero-text] { color: transparent !important; }")
        page.wait_for_timeout(100)
        res, problems = [], []
        for el, col in zip(page.query_selector_all("[data-hero-text]"), colours):
            text = tuple(int(x) for x in re.findall(r"[\d.]+", col)[:3])
            raw = Image.open(io.BytesIO(el.screenshot())).convert("RGB").tobytes()
            px = sorted(_lum(raw[i:i + 3]) for i in range(0, len(raw), 3))
            light = px[min(len(px) - 1, int(len(px) * 0.995))]
            lt = _lum(text)
            ratio = (max(lt, light) + 0.05) / (min(lt, light) + 0.05)
            res.append(round(ratio, 2))
            if ratio < 4.5:
                problems.append(f"text {col} on background luminance {light:.3f}: {ratio:.2f}:1")
        out[name] = dict(ratios=res, problems=problems + log["problems"])
        ctx.close()
    return out


def check_first_screen(browser, base) -> dict:
    """At 1920x1080 and 1600x900 the Live Center's first screen, unscrolled, contains each visual's
    whole bounding box; no text overlaps; SVG text is at least MIN_SVG_PX."""
    out = {}
    for w, h in FIRST_SCREENS:
        ctx, page, log = _context(browser, w, h)
        _open(page, base, "hub_live", QUERY["hub_live"])
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


def _load_lazy_images(page) -> None:
    """Scroll through the page so loading=lazy images below the fold load before a full-page
    screenshot, wait for them, then return to the top."""
    page.evaluate("""async () => {
        const step = window.innerHeight;
        for (let y = 0; y < document.documentElement.scrollHeight; y += step) {
            window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
        // images that are display:none never load, so the wait is capped
        const pending = [...document.images].filter((im) => !im.complete && im.offsetParent !== null);
        await Promise.race([new Promise((r) => setTimeout(r, 3000)), Promise.all(pending.map((im) =>
            new Promise((r) => { im.addEventListener("load", r); im.addEventListener("error", r); })))]);
        window.scrollTo(0, 0); }""")
    page.wait_for_timeout(150)


def screens_1080p(browser, base, screens: Path, routes) -> list:
    """First-screen 1920x1080 shots of the routes not already shot at that size (Live: demo_screen,
    Home: its extra size check)."""
    problems = []
    for route in routes:
        ctx, page, log = _context(browser, 1920, 1080)
        _open(page, base, route, QUERY.get(route, ""))
        (screens / f"{route}_1080p.png").write_bytes(_shrink_png(page.screenshot()))
        problems += log["problems"]
        ctx.close()
    return problems


def demo_screen(browser, base, screens: Path):
    ctx, page, log = _context(browser, 1920, 1080)
    _open(page, base, "hub_live", QUERY["hub_live"])
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
            for wn, size in EXTRA_SIZES.get(route, {}).items():
                report["routes"].append(check_route(browser, base, route, wn, src, shots, axe_src, size=size))
        if shots:
            report["screens_1080p"] = screens_1080p(
                browser, base, shots, [r for r in routes if "1080p" not in EXTRA_SIZES.get(r, {})])
        report["image_files"] = check_image_files(dist)
        if "home" in routes:
            report["badges"] = check_badges(browser, base, shots)
            report["hero_contrast"] = check_hero_contrast(browser, base)
        if "hub_live" in routes:
            report["drawer"] = check_evidence_drawer(browser, base, src)
            report["robustness"] = check_robustness(browser, base)
            report["frames"] = check_replay_frames(browser, base)
            report["frames_1080p"] = check_replay_frames(browser, base, size=(1920, 1080))
            report["first_screen"] = check_first_screen(browser, base)
            report["live_stream"] = check_live_stream(browser, dist, base)
            if shots:
                report["demo_problems"] = demo_screen(browser, base, shots)
        if set(routes) == set(ROUTES):
            report["text_budget_proof"] = check_text_budget_proof(browser, base)
            report["consistency"] = check_consistency(browser, base, ref_dir or dist / "data")
            report["navigation"] = check_navigation(browser, base)
            report["hub_layout"] = check_hub_layout(browser, base)
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
        f += [f"{tag}: text budget {x}" for x in r.get("budget", [])]
        f += [f"{tag}: lane/mismatch wording outside its allowed places: {x!r}" for x in r.get("lane", [])]
        if r.get("focus_trapped") is False:
            f.append(f"{tag}: focus left the open sheet")
        if r["tab"]["missing"]:
            f.append(f"{tag}: Tab never reaches {r['tab']['missing']}")
        f += [f"{tag}: axe {v['impact']} {v['id']}: {v['help']} {v['nodes']}" for v in r["axe"] if v["impact"] in AXE_FAIL]
        f += [f"{tag}: no element matches {sel} with its data attribute" for sel, n in r["attrs"].items() if not n]
        f += [f"{tag}: image {x}" for x in image_problems(r["images"], r["route"])]
    f += [f"image file: {x}" for x in report.get("image_files", {}).get("problems", [])]
    f += [f"badges: {x}" for x in report.get("badges", {}).get("problems", [])]
    for size, v in report.get("hero_contrast", {}).items():
        f += [f"hero contrast {size}: {x}" for x in v["problems"]]
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
    for k, v in report.get("hub_layout", {}).items():
        if k == "old_layout_proof":
            if not v["caught"]:
                f.append("hub layout proof: the old layout was not caught")
        else:
            f += [f"hub layout@{k}: {x}" for x in v["problems"]]
    f += [f"text budget proof: {k} not caught" for k, v in report.get("text_budget_proof", {}).items()
          if not v["caught"]]
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
    L = report.get("live_stream")
    if L is not None:
        f += [f"live stream: {x}" for x in L["problems"]]
        if L.get("static_chip") != "replay":
            f.append(f"live stream: static hosting shows {L.get('static_chip')!r}, not replay")
        if L.get("live_chip") != "live" or L.get("other_origin") or not L.get("cards_later", 0) >= 3:
            f.append(f"live stream: {L}")
        if not any(p.startswith("/api/match/") and p.endswith("/stream") for p in L.get("api_calls", [])):
            f.append(f"live stream: no SSE request {L.get('api_calls')}")
    for size, v in report.get("first_screen", {}).items():
        f += [f"first screen {size}: {x}" for x in v["problems"]]
    if report.get("bundle", {}).get("total_kb", 0) >= INITIAL_JS_KB:
        f.append(f"initial JS {report['bundle']['total_kb']} KB gzip, budget {INITIAL_JS_KB} KB")
    f += [f"demo screen: {x}" for x in report.get("demo_problems", [])]
    f += [f"1080p screen: {x}" for x in report.get("screens_1080p", [])]
    if report["bundle"]["total_kb"] >= 250:
        f.append(f"initial JS {report['bundle']['total_kb']} KB gzip (budget 250)")
    return f


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dist", default=str(WEB / "dist"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "screens-v8"), help="screenshot directory")
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
        print(f"{r['route']:10s} {r['width']:5d}px overflow_x={r['overflowX']!s:5s} tailwind={r['tailwind_ok']!s:5s} "
              f"text_runs={r['overlap']['count']:4d} overlaps={len(r['overlap']['overlaps'])} untraced={len(r['untraced'])} "
              f"controls={r['tab']['controls']:3d} tab_missing={len(r['tab']['missing'])} axe_serious={len(bad_axe)} "
              f"axe_minor={len(r['axe']) - len(bad_axe)} problems={len(r['problems'])} remote={len(r['remote'])} attrs={r['attrs']}")
    for r in report["routes"]:
        top = {}
        for k, _, n in r.get("words", {}).get("elements", []):
            top[k] = max(top.get(k, 0), n)
        print(f"words {r['route']:10s} {r['width']:5d}px total={r.get('words', {}).get('total')} max_per_budget={top}")
    for k in ("hub_layout", "text_budget_proof", "drawer", "consistency", "mutation_proof", "language", "robustness", "frames", "frames_1080p",
              "first_screen", "live_stream", "bundle", "image_files", "badges", "hero_contrast"):
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
