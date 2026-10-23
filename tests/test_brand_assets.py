"""Shipped brand images: no metadata, size budgets, the expected set, and no original or blocked art.

The originals live in design/source/ (gitignored); see design/ASSETS.md and docs/brand-audit.md.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from tools.image_meta import metadata_chunks

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "web" / "public"
SOCIAL = ROOT / "design" / "social"
RASTER = (".png", ".webp", ".jpg", ".jpeg", ".ico")
CODES = ["aur", "ntg", "cal", "ves", "har"]
MAX_BYTES = 300_000
HERO_MAX = {"hero-lineup-1600.webp": 220_000, "hero-lineup-800.webp": 90_000}


def shipped() -> list[Path]:
    return sorted(p for p in PUBLIC.rglob("*") if p.suffix.lower() in RASTER and "data" not in p.parts)


def test_the_brand_set_is_complete():
    names = {p.relative_to(PUBLIC).as_posix() for p in shipped()}
    for c in CODES:
        for s in (48, 96, 192):
            assert f"brand/teams/badge-{c}-{s}.webp" in names
        for k in ("home", "away"):
            assert f"brand/teams/kit-{c}-{k}.webp" in names
    for f in ("favicon.ico", "icons/icon-16.png", "icons/icon-32.png", "icons/icon-48.png",
              "icons/apple-touch-icon.png", "icons/icon-192.png", "icons/icon-512.png",
              "brand/hero-lineup-1600.webp", "brand/hero-lineup-800.webp", "brand/og-1200x630.jpg"):
        assert f in names, f
    for f in ("optix-mark.svg", "optix-logo.svg", "optix-mark-accent.svg", "optix-logo-accent.svg"):
        svg = (PUBLIC / "brand" / f).read_text()
        assert "<path" in svg and ("currentColor" in svg) == ("accent" not in f)


@pytest.mark.parametrize("path", shipped(), ids=lambda p: p.relative_to(PUBLIC).as_posix())
def test_no_metadata_and_within_budget(path):
    assert metadata_chunks(path) == [], path
    limit = HERO_MAX.get(path.name, MAX_BYTES)
    assert path.stat().st_size <= limit, f"{path.name}: {path.stat().st_size} bytes over {limit}"


def test_crests_and_kits_have_a_transparent_background():
    for c in CODES:
        for f in (f"badge-{c}-96.webp", f"kit-{c}-home.webp", f"kit-{c}-away.webp"):
            im = Image.open(PUBLIC / "brand" / "teams" / f)
            assert im.mode == "RGBA", f
            a = im.getchannel("A")
            corners = [a.getpixel((0, 0)), a.getpixel((im.width - 1, 0)), a.getpixel((0, im.height - 1))]
            assert max(corners) == 0, f"{f}: corners not transparent {corners}"
            assert a.getextrema()[1] == 255, f"{f}: nothing opaque"


def test_social_images():
    sizes = {"github-social-1280x640.png": (1280, 640), "og-1200x630.png": (1200, 630),
             "devpost-thumbnail-1500x1000.png": (1500, 1000), "video-title-card-1920x1080.png": (1920, 1080),
             "video-end-card-1920x1080.png": (1920, 1080)}
    for f, wh in sizes.items():
        p = SOCIAL / f
        assert Image.open(p).size == wh, f
        assert metadata_chunks(p) == [], f
    assert (SOCIAL / "github-social-1280x640.png").stat().st_size < 1_000_000


def test_originals_and_blocked_art_are_not_tracked():
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    assert not [f for f in tracked if f.startswith(("design/source/", "design/review/"))]
    assert not [f for f in tracked if "trio" in f.lower() and f.endswith(RASTER)], "players-trio is BLOCKED"
