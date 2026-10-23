"""Contact sheets and a distinctness measure for the Optix icon set (web/src/icons).

    python -m tools.icon_sheet [--out docs/screens-v5]

Writes icons-16.png, icons-24.png and icons-64.png: every icon on a dark and on a light background,
with its name. `correlations(size)` renders each icon alone at `size` px and returns the pairwise
normalised correlation of the grey rasters (tests/test_icons.py fails above 0.92).

The icons are JSX files of plain SVG elements with literal attributes. `icon_svgs` turns each one back
into a standalone SVG with the same root attributes as <Icon> (web/src/icons/Icon.tsx), so the
rasters are the shapes the app draws. The browser is the project's Chromium
(tools.check_dashboard.chromium_path); nothing is fetched.
"""
from __future__ import annotations

import argparse
import io
import re
from itertools import combinations
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
GLYPHS = ROOT / "web" / "src" / "icons" / "glyphs"
NAMES_TS = ROOT / "web" / "src" / "icons" / "names.ts"
# values of the colour tokens an icon may use (web/src/styles/tokens.css)
TOKENS = {"--card-yellow": "#f2c94c", "--card-red": "#e5484d", "--lane-fill": "#37e6a8"}
ROOT_ATTRS = ('viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
              'stroke-linecap="round" stroke-linejoin="round"')
THRESHOLD = 0.92
WHITELIST = {frozenset(("foul", "pattern-tactical-fouling"))}


def icon_names() -> list[str]:
    return re.findall(r'"([a-z0-9-]+)"', NAMES_TS.read_text().split("} as const")[0])


def _kebab(attr: str) -> str:
    return re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), attr)


def glyph_body(name: str) -> str:
    """The SVG children of one icon, from its JSX file."""
    src = (GLYPHS / f"{name}.tsx").read_text()
    m = re.search(r"<>(.*)</>", src, re.S)
    if not m:
        raise ValueError(f"{name}: no fragment")
    body = re.sub(r"\s+", " ", m.group(1)).strip()
    body = re.sub(r"\b(fillOpacity|strokeWidth|strokeDasharray|strokeLinecap|strokeLinejoin)=",
                  lambda k: _kebab(k.group(1)) + "=", body)
    return re.sub(r'="\{?([^"}]*)\}?"', r'="\1"', body)


def icon_svgs(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """name -> standalone SVG markup (currentColor resolved by the page's `color`)."""
    out = {}
    for n in icon_names():
        body = (overrides or {}).get(n) or glyph_body(n)
        out[n] = f"<svg xmlns='http://www.w3.org/2000/svg' {ROOT_ATTRS}>{body}</svg>"
    return out


def _page_css(fg: str, bg: str) -> str:
    vars_ = "".join(f"{k}:{v};" for k, v in TOKENS.items())
    return f":root{{{vars_}}} body{{margin:0;background:{bg};color:{fg};font:12px sans-serif}}"


def _browser(p):
    from tools.check_dashboard import chromium_path
    return p.chromium.launch(executable_path=chromium_path())


def rasters(size: int, overrides: dict[str, str] | None = None) -> dict[str, list[int]]:
    """Each icon alone, white on black at `size` px (scale 1), as a flat list of grey values."""
    from playwright.sync_api import sync_playwright
    svgs = icon_svgs(overrides)
    cells = "".join(f"<div id='i-{n}' style='width:{size}px;height:{size}px;padding:2px'>"
                    f"{s.replace('<svg ', f'<svg width={size} height={size} ', 1)}</div>" for n, s in svgs.items())
    out = {}
    with sync_playwright() as p:
        b = _browser(p)
        page = b.new_page(viewport={"width": size + 4, "height": 400}, device_scale_factor=1)
        page.set_content(f"<style>{_page_css('#fff', '#000')}</style>{cells}")
        for n in svgs:
            img = Image.open(io.BytesIO(page.locator(f"#i-{n}").screenshot())).convert("L")
            out[n] = list(img.tobytes())
        b.close()
    return out


def correlation(a: list[int], b: list[int]) -> float:
    """Normalised (Pearson) correlation of two grey rasters of the same size."""
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    da = [v - ma for v in a]
    db = [v - mb for v in b]
    num = sum(x * y for x, y in zip(da, db))
    den = (sum(x * x for x in da) * sum(y * y for y in db)) ** 0.5
    return num / den if den else 1.0


def correlations(size: int, overrides: dict[str, str] | None = None) -> dict[tuple[str, str], float]:
    r = rasters(size, overrides)
    return {(a, b): correlation(r[a], r[b]) for a, b in combinations(sorted(r), 2)}


def too_similar(corr: dict[tuple[str, str], float]) -> list[tuple[str, str, float]]:
    return sorted(((a, b, round(c, 3)) for (a, b), c in corr.items()
                   if c > THRESHOLD and frozenset((a, b)) not in WHITELIST), key=lambda t: -t[2])


def contact_sheet(size: int, out: Path) -> None:
    """Every icon at `size` px on a dark half and a light half, in sheet order, with its name."""
    from playwright.sync_api import sync_playwright
    svgs = icon_svgs()
    cell = max(size + 16, 92)

    def grid(fg, bg):
        items = "".join(
            f"<div style='width:{cell}px;display:flex;flex-direction:column;align-items:center;gap:6px;"
            f"padding:10px 0'>{s.replace('<svg ', f'<svg width={size} height={size} ', 1)}"
            f"<span style='font-size:10px;opacity:.75;text-align:center'>{n}</span></div>" for n, s in svgs.items())
        return (f"<div style='background:{bg};color:{fg};display:flex;flex-wrap:wrap;width:{cell * 9}px;"
                f"padding:12px'>{items}</div>")

    with sync_playwright() as p:
        b = _browser(p)
        # 16 and 24 px at 2x so the sheet shows the pixels clearly; 64 px is large enough at 1x
        page = b.new_page(viewport={"width": cell * 9 + 24, "height": 600}, device_scale_factor=2 if size < 64 else 1)
        page.set_content(f"<style>{_page_css('#e8edf6', '#05080f')}</style>"
                         f"{grid('#e8edf6', '#05080f')}{grid('#111827', '#f4f6fa')}")
        data = page.screenshot(full_page=True)
        b.close()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im = Image.frombytes(im.mode, im.size, im.tobytes())
    im.save(out, "PNG", optimize=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "screens-v5"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for s in (16, 24, 64):
        contact_sheet(s, out / f"icons-{s}.png")
        print(f"icons-{s}.png")
    for s in (16, 24):
        corr = correlations(s)
        top = sorted(corr.items(), key=lambda kv: -kv[1])[:8]
        print(f"{s} px: highest pairs", [(a, b, round(c, 3)) for (a, b), c in top])
        print(f"{s} px: over {THRESHOLD} (not whitelisted):", too_similar(corr))


if __name__ == "__main__":
    main()
