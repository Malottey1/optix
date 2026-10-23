# Brand assets: provenance

Every image the app or the repository ships, where it comes from, and how it was checked. The
originals are **not** in the repository: they stay local in `design/source/` (gitignored). Only the
optimised derivatives below are committed. The originals were never edited; each derivative is made
by a script from a copy.

## Sources

| Original (local only) | What it is | Source | Audit |
|---|---|---|---|
| `design/source/hero-lineup.png` | five players over five colour bands | author's own photos and prompts, AI-assisted; AI tool terms to be confirmed by the author | 13 maker-style marks removed → `hero-lineup-clean.png`; **used** |
| `design/source/players-trio.png` | three players on white | author's own photos and prompts, AI-assisted; AI tool terms to be confirmed by the author | **BLOCKED**: 4 of 8 removals smudged, no clean alpha; **not used** |
| `design/source/kit-sheet.png` | five crests, home and away shirts | author's own prompts, AI-assisted; AI tool terms to be confirmed by the author | no maker marks found; crest concerns noted; **used** |
| `design/source/logo-mark.png` | Optix mark (O, X, arrow) | author's own design | n/a; **used** (traced) |
| `design/source/logo-wordmark.png` | Optix wordmark | author's own design | n/a; **used** (traced) |
| `design/source/icon-sheet.png` | "OPTIX ICON SET": 54 icons in 8 groups | author's design sheet, AI-assisted; AI tool terms to be confirmed by the author | reference only: the icons are **redrawn by hand** as SVG; nothing of the raster is embedded or traced |

The audit and what the author must visually confirm are in [docs/brand-audit.md](../docs/brand-audit.md).
The clubs (Aurelia Rovers, Northgate Town, Calder Athletic, Veston United, Harbor Wanderers) and
the players are fictional.

## Shipped derivatives

| File | Made from | Made by |
|---|---|---|
| `web/public/brand/optix-mark.svg`, `optix-logo.svg` (currentColor), `*-accent.svg` | logo-mark, logo-wordmark | `tools/make_brand_assets.py logos` (vtracer) |
| `web/src/components/brand/logoPaths.ts` | the same traced paths | `tools/make_brand_assets.py logos` |
| `web/public/favicon.ico`, `web/public/icons/*.png`, `web/public/manifest.webmanifest` | logo-mark (a small-size variant without the arrow below 64 px) | `tools/make_brand_assets.py icons` |
| `web/public/brand/teams/badge-{aur,ntg,cal,ves,har}-{48,96,192}.webp` | kit-sheet crests | `tools/make_brand_assets.py teams` |
| `web/public/brand/teams/kit-{code}-{home,away}.webp` | kit-sheet shirts | `tools/make_brand_assets.py teams` |
| `web/public/brand/hero-lineup-{1600,800}.webp` | hero-lineup-clean | `tools/make_brand_assets.py hero` |
| `web/public/brand/og-1200x630.jpg` | the OG card below | `tools/make_brand_images.py` |
| `design/social/*.png` (GitHub social, OG, devpost thumbnail, video title and end cards) | the logo, crests and hero above | `tools/make_brand_images.py` |
| `web/src/icons/glyphs/*.tsx` (54 icons) | icon-sheet, as a drawing reference | drawn by hand as SVG path data (docs/icons.md); no raster, no tracing |
| `docs/screens-v5/icons-{16,24,64}.png` | the icons above | `python -m tools.icon_sheet` |
| `README.md` hero screenshot (`docs/screens-v4/home_desktop.png`) | the running app | `python -m tools.check_web` |

The mark-removal tool is `tools/brand_audit.py`. Rerunning any tool needs the local originals and
`requirements-design.txt`.

## Metadata

Every raster is rebuilt from pixel data before saving, so no EXIF, XMP, ICC profile or text chunk is
carried over from the originals. `tests/test_brand_assets.py` checks every shipped image for EXIF,
XMP, ICC and PNG text chunks, and checks the size budgets: at most 300 KB per file; the hero at most
220 KB (1600 px) and 90 KB (800 px).

## Fonts and icons

| Asset | Licence | How it is shipped |
|---|---|---|
| Inter (variable) via `@fontsource-variable/inter` | SIL Open Font License 1.1 | bundled by Vite from node_modules; also used by the social-card templates |
| Barlow Condensed via `@fontsource/barlow-condensed` | SIL Open Font License 1.1 | as above |
| Icon set (`web/src/icons`) | drawn for this project from the author's sheet | inline SVG components; no icon font, no third-party set |
| Interface glyphs (`web/src/components/icons.tsx`) | drawn for this project | inline SVG |
| Home feature drawings (`web/src/features/home/HomePage.tsx`) | drawn for this project | inline SVG in the app's tokens; no stock art |

No third-party logos, no real club or league marks and no stock photography are shipped.
