"""The icon set (web/src/icons): no two icons read alike at 16 or 24 px.

Each icon is rendered alone in the project's Chromium and the grey rasters are compared pairwise by
normalised correlation (tools/icon_sheet.py). Only foul / pattern-tactical-fouling may exceed 0.92:
that pair is a deliberate match (the same whistle, plus a clock). Needs Playwright
(requirements-ui.txt), like tests/test_dashboard.py.
"""
from __future__ import annotations

import re

import pytest

pytest.importorskip("playwright.sync_api")

from tools import icon_sheet  # noqa: E402

PAIRS = [("live", "metric-territorial-stress"), ("live", "pressure"), ("pressure", "metric-territorial-stress"),
         ("players", "teams"), ("tech", "settings"), ("verdict-revised", "restart"),
         ("verdict-revised", "possession-change"),
         ("fixtures", "scrub"), ("search", "metric-xg")]
EXPECTED = {
    "live", "home", "fixtures", "teams", "players", "tech", "settings", "search",
    "play", "pause", "restart", "speed", "scrub",
    "pass", "shot", "goal", "tackle", "interception", "pressure", "possession-change", "foul", "yellow-card",
    "red-card", "substitution", "corner",
    "lane-left-flank", "lane-left-half-space", "lane-centre", "lane-right-half-space", "lane-right-flank",
    "verdict-passed", "verdict-revised", "verdict-blocked", "verdict-context", "evidence-drawer", "trace-to-data",
    "style-high-press", "style-low-block", "style-patient-possession", "style-direct-play", "style-wing-play",
    "style-central-play",
    "metric-xg", "metric-xt", "metric-field-tilt", "metric-momentum", "metric-territorial-stress", "metric-rhythm",
    "pattern-bait-switch", "pattern-cutback", "pattern-flank-isolation", "pattern-elastic-low-block",
    "pattern-counter-press", "pattern-rest-defence", "pattern-starved-finisher", "pattern-tactical-fouling",
}


def _key(a, b):
    return (a, b) if a < b else (b, a)


@pytest.fixture(scope="module", params=[16, 24])
def corr(request):
    return request.param, icon_sheet.correlations(request.param)


def test_the_names_are_the_sheet():
    assert len(EXPECTED) == 56
    assert set(icon_sheet.icon_names()) == EXPECTED


def test_no_two_icons_read_alike(corr):
    size, c = corr
    assert icon_sheet.too_similar(c) == [], f"{size} px"


def test_named_pairs_are_distinct(corr):
    size, c = corr
    for a, b in PAIRS:
        assert c[_key(a, b)] < icon_sheet.THRESHOLD, f"{a} / {b} at {size} px: {c[_key(a, b)]:.3f}"


def test_the_measure_catches_a_copied_icon():
    # mutation: pressure drawn as a copy of live must be reported
    c = icon_sheet.correlations(16, overrides={"pressure": icon_sheet.glyph_body("live")})
    assert ("live", "pressure", 1.0) in [(a, b, round(v, 2)) for a, b, v in icon_sheet.too_similar(c)]


def test_icon_sources_hold_no_raster_text_or_remote_reference():
    for n in EXPECTED:
        src = (icon_sheet.GLYPHS / f"{n}.tsx").read_text().split("\n", 1)[1]  # past the header comment
        assert not re.search(r"<image|<text|base64|data:|href|https?:", src), n
