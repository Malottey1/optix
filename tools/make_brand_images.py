"""Social and submission images, rendered from small HTML templates with the project's Playwright.

    python -m tools.make_brand_images

Writes design/social/:
  github-social-1280x640.png      repository social preview (kept under GitHub's 1 MB limit)
  og-1200x630.png                 Open Graph card
  devpost-thumbnail-1500x1000.png 3:2 submission thumbnail
  video-title-card-1920x1080.png  first frame of the demo video
  video-end-card-1920x1080.png    last frame, with the repository address as text
and web/public/brand/og-1200x630.jpg, the copy the page's og:image points to (JPEG, so it stays under
the 300 KB image budget). Everything is local: the logo, crests and hero come from web/public/brand,
the fonts from web/node_modules (Inter, Barlow Condensed; OFL). No network, no `playwright install`:
the browser is the one the dashboard checks use (tools.check_dashboard.chromium_path).
The hero is the audited, cleaned artwork (docs/brand-audit.md).
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "design" / "social"
BRAND = ROOT / "web" / "public" / "brand"
FONTS = ROOT / "web" / "node_modules"
CODES = ["aur", "ntg", "cal", "ves", "har"]
REPO = "github.com/Malottey1/optix"
HEADLINE = "Match talking points you can trace back to the data."
SUB = "Every claim is checked against the events before it is worded, and translated without changing a number."
CAPTION = "Synthetic data. Illustrative artwork; clubs and players are fictional."

CSS = f"""
@font-face {{ font-family: Inter; font-weight: 100 900;
  src: url("file://{FONTS}/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2") format("woff2"); }}
@font-face {{ font-family: Barlow; font-weight: 700;
  src: url("file://{FONTS}/@fontsource/barlow-condensed/files/barlow-condensed-latin-700-normal.woff2") format("woff2"); }}
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ background: #05080f; color: #f1f4fa; font-family: Inter, sans-serif; }}
.frame {{ position: relative; overflow: hidden; background: #05080f; }}
.hero {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
.scrim {{ position: absolute; inset: 0; }}
.logo {{ display: block; }}
h1 {{ font-weight: 800; letter-spacing: -0.02em; line-height: 1.06; }}
.sub {{ color: #b9c2d6; line-height: 1.45; }}
.badges {{ display: flex; align-items: center; }}
.badges img {{ display: block; }}
.cap {{ color: #8d99b2; }}
.chip {{ display: inline-flex; align-items: center; gap: .5em; border: 1px solid rgba(55,230,168,.4);
  background: rgba(55,230,168,.12); color: #37e6a8; border-radius: 999px; font-weight: 700;
  letter-spacing: .12em; text-transform: uppercase; }}
"""


def _badges(size: int, gap: int) -> str:
    return f'<div class="badges" style="gap:{gap}px">' + "".join(
        f'<img src="file://{BRAND}/teams/badge-{c}-192.webp" width="{size}" height="{size}" alt="">' for c in CODES) + "</div>"


def _logo(width: int) -> str:
    return f'<img class="logo" src="file://{BRAND}/optix-logo-accent.svg" width="{width}" alt="Optix">'


HERO = f"file://{BRAND}/hero-lineup-1600.webp"


def wide_card(w: int, h: int) -> str:
    """Social preview / OG: text on the left over a dark scrim, the line-up on the right."""
    return f"""<div class="frame" style="width:{w}px;height:{h}px">
  <img class="hero" src="{HERO}" style="object-position:70% 34%;left:{int(w*0.28)}px;width:{int(w*0.72)}px">
  <div class="scrim" style="background:linear-gradient(90deg,#05080f 0%,#05080f 30%,rgba(5,8,15,.86) 44%,rgba(5,8,15,0) 62%)"></div>
  <div style="position:absolute;left:{int(w*0.05)}px;top:{int(h*0.1)}px;width:{int(w*0.47)}px">
    {_logo(int(w*0.15))}
    <h1 style="margin-top:{int(h*0.07)}px;font-size:{int(h*0.083)}px">{HEADLINE}</h1>
    <p class="sub" style="margin-top:{int(h*0.035)}px;font-size:{int(h*0.033)}px">{SUB}</p>
    <div style="margin-top:{int(h*0.06)}px">{_badges(int(h*0.075), int(h*0.018))}</div>
  </div>
  <p class="cap" style="position:absolute;left:{int(w*0.05)}px;bottom:{int(h*0.05)}px;font-size:{int(h*0.024)}px">{CAPTION}</p>
</div>"""


def devpost(w: int = 1500, h: int = 1000) -> str:
    """3:2 thumbnail: the full line-up, logo and headline on a dark band across the top bands."""
    return f"""<div class="frame" style="width:{w}px;height:{h}px">
  <img class="hero" src="{HERO}" style="object-position:50% 100%">
  <div class="scrim" style="background:linear-gradient(180deg,rgba(5,8,15,.95) 0%,rgba(5,8,15,.9) 30%,rgba(5,8,15,.55) 44%,rgba(5,8,15,0) 56%)"></div>
  <div style="position:absolute;left:72px;top:64px;right:72px;display:flex;align-items:flex-start;gap:56px">
    {_logo(250)}
    <div style="flex:1">
      <h1 style="font-size:58px">{HEADLINE}</h1>
      <p class="sub" style="margin-top:18px;font-size:24px;max-width:900px">{SUB}</p>
    </div>
  </div>
  <p class="cap" style="position:absolute;right:28px;bottom:20px;font-size:17px;color:#d6dbe6;background:rgba(5,8,15,.72);padding:6px 12px;border-radius:8px">{CAPTION}</p>
</div>"""


def title_card(w: int = 1920, h: int = 1080) -> str:
    return f"""<div class="frame" style="width:{w}px;height:{h}px">
  <img class="hero" src="{HERO}" style="left:{w//2 - 80}px;width:{w//2 + 80}px;object-position:60% 30%">
  <div class="scrim" style="background:linear-gradient(90deg,#05080f 0%,#05080f 42%,rgba(5,8,15,.8) 52%,rgba(5,8,15,0) 70%)"></div>
  <div style="position:absolute;left:140px;top:170px;width:880px">
    <span class="chip" style="font-size:20px;padding:8px 18px">Synthetic match insights engine</span>
    <div style="margin-top:56px">{_logo(330)}</div>
    <h1 style="margin-top:56px;font-size:70px">{HEADLINE}</h1>
    <p class="sub" style="margin-top:28px;font-size:30px">{SUB}</p>
    <div style="margin-top:56px">{_badges(76, 22)}</div>
  </div>
  <p class="cap" style="position:absolute;left:140px;bottom:56px;font-size:22px">{CAPTION}</p>
</div>"""


def end_card(w: int = 1920, h: int = 1080) -> str:
    return f"""<div class="frame" style="width:{w}px;height:{h}px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center">
  <div class="scrim" style="background:radial-gradient(ellipse 60% 55% at 50% 45%,#0f1727 0%,#05080f 100%)"></div>
  <div style="position:relative;display:flex;flex-direction:column;align-items:center">
    {_logo(420)}
    <p style="margin-top:56px;font-size:40px;font-weight:700">Facts first. Evidence on every claim.</p>
    <p class="sub" style="margin-top:14px;font-size:30px">Translation never changes a number.</p>
    <p style="margin-top:72px;font-family:Barlow,Inter,sans-serif;font-size:64px;letter-spacing:.01em;color:#37e6a8">{REPO}</p>
    <div style="margin-top:72px">{_badges(64, 26)}</div>
    <p class="cap" style="margin-top:44px;font-size:22px">{CAPTION}</p>
  </div>
</div>"""


CARDS = {
    "github-social-1280x640.png": (1280, 640, lambda: wide_card(1280, 640)),
    "og-1200x630.png": (1200, 630, lambda: wide_card(1200, 630)),
    "devpost-thumbnail-1500x1000.png": (1500, 1000, devpost),
    "video-title-card-1920x1080.png": (1920, 1080, title_card),
    "video-end-card-1920x1080.png": (1920, 1080, end_card),
}
LIMIT = {"github-social-1280x640.png": 1_000_000}  # GitHub caps the social preview at 1 MB


def _png(data: bytes, limit: int | None) -> bytes:
    """Re-encode without metadata; if over the limit, fall back to a 256-colour palette (which bands
    the gradients, so it is used only where a hard limit requires it)."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im = Image.frombytes(im.mode, im.size, im.tobytes())
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    if limit and b.tell() > limit:
        b = io.BytesIO()
        im.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(b, "PNG", optimize=True)
    return b.getvalue()


def main(argv=None):
    from playwright.sync_api import sync_playwright
    from tools.check_dashboard import chromium_path
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch(executable_path=chromium_path())
        for name, (w, h, make) in CARDS.items():
            page = browser.new_page(viewport={"width": w, "height": h})
            # a file:// page, so it may load the local logo, crests, hero and fonts
            html = Path(tmp) / f"{name}.html"
            html.write_text(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head>"
                            f"<body>{make()}</body></html>", encoding="utf-8")
            page.goto(html.as_uri())
            page.wait_for_load_state("load")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(300)
            data = _png(page.screenshot(), LIMIT.get(name))
            (OUT / name).write_bytes(data)
            print(f"{name}: {w}x{h}, {len(data) // 1024} KB")
            page.close()
        browser.close()
    og = Image.open(OUT / "og-1200x630.png").convert("RGB")
    og = Image.frombytes(og.mode, og.size, og.tobytes())
    og.save(BRAND / "og-1200x630.jpg", "JPEG", quality=84, optimize=True, progressive=True)
    print(f"web/public/brand/og-1200x630.jpg: {(BRAND / 'og-1200x630.jpg').stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
