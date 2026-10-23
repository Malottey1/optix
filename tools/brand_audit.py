"""Third-party mark audit for the brand artwork: zoom crops, mark removal and before/after sheets.

    python -m tools.brand_audit

Reads the local originals in design/source/ (gitignored, never shipped) and writes:
  design/review/audit-<image>-boxes.png      the whole image with every suspect boxed and labelled
  design/review/audit-<id>-before-after.png  each suspect zoomed 4x, original left, cleaned right
  design/source/<image>-clean.png            the cleaned image (still local; derivatives are made from it)

Every suspect is listed in MARKS with its box in full-resolution pixels and the removal method:
  ("patch", dx, dy)  copy the same fabric from a nearby region along the stripe/hoop direction,
                     colour-matched on a ring around the box and blended with a feathered edge;
  ("match", kind, k)   exemplar fill: the nearby patch that best matches the unmarked surroundings
                     (masked template matching) supplies only the mark pixels, soft-edged;
  kind "white" picks low-saturation bright pixels instead of a top-hat; a trailing "stripe" redraws
  a pinstripe that ran under the mark (fitted from the rows above and below).
  ("inpaint", kind, k) OpenCV Telea inpainting of the mark pixels only (found with a white or black
                     top-hat of kernel k, so stripes and folds wider than k stay), plus fine grain.
Coordinates were read off gridded zoom sheets (see docs/brand-audit.md). The result still needs the
author's visual confirmation: a script cannot decide whether a patch reads as a logo.
"""
from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC = "design/source"
REVIEW = "design/review"

MARKS = {
    "hero-lineup": [
        ("H1", "AUR chest: chevron maker-style mark", (80, 1142, 137, 1190), ("inpaint", "white", 0)),
        ("H2", "AUR left sleeve: chevron mark and a small swoosh", (524, 1089, 616, 1148), ("inpaint", "light", 31)),
        ("H3", "AUR collar: small emblem", (318, 1053, 342, 1078), ("inpaint", "light", 25)),
        ("H3b", "AUR collar: scribble mark", (349, 1050, 383, 1078), ("inpaint", "light", 25)),
        ("H4", "AUR under crest: maker-style lettering", (304, 1189, 351, 1219), ("match", "light", 31)),
        ("H5", "CAL chest: chevron maker-style mark", (970, 1098, 1060, 1160), ("match", "light", 41)),
        ("H6", "CAL right sleeve: small emblem", (1529, 1255, 1567, 1301), ("inpaint", "light", 25)),
        ("H7", "CAL under crest: maker-style lettering", (1302, 1187, 1345, 1214), ("inpaint", "light", 25)),
        ("H8", "VES chest: chevron maker-style mark", (1503, 1082, 1566, 1139), ("inpaint", "white", 0, "stripe")),
        ("H9", "VES under crest: maker-style lettering", (1771, 1184, 1819, 1214), ("inpaint", "light", 25)),
        ("H10", "VES right sleeve: small emblem", (1899, 1247, 1925, 1293), ("inpaint", "light", 21)),
        ("H11", "HAR chest: tick/chevron maker-style mark", (1887, 1123, 1929, 1167), ("match", "light", 31)),
        ("H12", "Ball: small round emblem in the star panel", (1150, 1519, 1186, 1551), ("inpaint", "light", 21)),
    ],
    "players-trio": [
        ("T1", "AUR shirt: swoosh-style tick", (1031, 565, 1097, 601), ("match", "dark", 25)),
        ("T2", "AUR shorts: tick-like stroke under the number", (1213, 1199, 1281, 1251), ("inpaint", "light", 25)),
        ("T3", "NTG shirt: winged/chevron mark", (421, 751, 501, 801), ("match", "light", 41)),
        ("T4", "NTG glove: striped winged mark on the strap", (483, 548, 602, 600), ("match", "light", 31)),
        ("T5", "NTG shorts: small diagonal side mark", (339, 1299, 377, 1345), ("inpaint", "light", 21)),
        ("T7", "CAL right glove strap: patterned maker-style patch", (1711, 825, 1767, 868), ("inpaint", "light", 21)),
        ("T8", "CAL shirt hem: woven label", (1959, 1424, 1996, 1451), ("inpaint", "light", 21)),
        ("T9", "CAL left glove back: emblem in the pattern", (1349, 794, 1421, 841), ("inpaint", "dark", 21)),
    ],
}
# Checked and judged not to be a mark (listed so the audit is complete; see docs/brand-audit.md).
CHECKED_CLEAR = {
    "hero-lineup": ["NTG shirt front (only the fictional crest)", "HAR sleeves and crest",
                    "Gloves (patterned, a faint unreadable strap texture)", "Ball panels"],
    "players-trio": ["Ball panels (generic star-panel pattern)", "CAL sleeve (tonal print only)",
                     "Boots (no visible mark)", "Socks (AUR lion crest only)"],
}


def _ring(a, x0, y0, x1, y1, w=6):
    h, wd = a.shape[:2]
    X0, Y0, X1, Y1 = max(0, x0 - w), max(0, y0 - w), min(wd, x1 + w), min(h, y1 + w)
    m = np.zeros(a.shape[:2], bool)
    m[Y0:Y1, X0:X1] = True
    m[y0:y1, x0:x1] = False
    return a[m]


def _feather(w, h, edge=5):
    m = np.zeros((h + 2 * edge, w + 2 * edge), np.float32)
    m[edge:-edge, edge:-edge] = 1
    m = cv2.GaussianBlur(m, (0, 0), edge / 2)
    return m[edge:-edge, edge:-edge][..., None]


def patch(a, box, dx, dy):
    x0, y0, x1, y1 = box
    src = a[y0 + dy:y1 + dy, x0 + dx:x1 + dx].astype(np.float32)
    shift = _ring(a, *box).mean(0) - _ring(a, x0 + dx, y0 + dy, x1 + dx, y1 + dy).mean(0)
    src = np.clip(src + shift, 0, 255)
    f = _feather(x1 - x0, y1 - y0)
    tgt = a[y0:y1, x0:x1].astype(np.float32)
    a[y0:y1, x0:x1] = (f * src + (1 - f) * tgt).astype(np.uint8)


def mark_mask(a, box, kind, k):
    """Mark pixels inside the box: a white (or black) top-hat finds strokes thinner than the kernel,
    so wide stripes, hoops and folds of the fabric are left alone."""
    x0, y0, x1, y1 = box
    pad = k
    X0, Y0 = max(0, x0 - pad), max(0, y0 - pad)
    X1, Y1 = min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad)
    m = np.zeros(a.shape[:2], np.uint8)
    if kind == "white":
        # white/grey print on coloured fabric: low saturation and bright, whatever the stroke width
        hsv = cv2.cvtColor(a[y0:y1, x0:x1], cv2.COLOR_RGB2HSV)
        greenish = (hsv[..., 0] > 35) & (hsv[..., 0] < 90) & (hsv[..., 1] > 40)
        sub = ((hsv[..., 1] < 80) & (hsv[..., 2] > 130) & ~greenish).astype(np.uint8) * 255
        m[y0:y1, x0:x1] = cv2.dilate(sub, np.ones((3, 3), np.uint8), iterations=4)
        return m
    gray = cv2.cvtColor(a[Y0:Y1, X0:X1], cv2.COLOR_RGB2GRAY)
    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    op = cv2.MORPH_TOPHAT if kind == "light" else cv2.MORPH_BLACKHAT
    hat = cv2.morphologyEx(gray, op, kern)
    sub = (hat > 22).astype(np.uint8) * 255
    inside = np.zeros_like(sub)
    inside[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0] = 255
    m[Y0:Y1, X0:X1] = cv2.dilate(sub & inside, np.ones((3, 3), np.uint8), iterations=2)
    return m


def inpaint(a, box, kind, k, seed):
    m = mark_mask(a, box, kind, k)
    x0, y0, x1, y1 = box
    pad = 20
    X0, Y0 = max(0, x0 - pad), max(0, y0 - pad)
    X1, Y1 = min(a.shape[1], x1 + pad), min(a.shape[0], y1 + pad)
    sub, mk = a[Y0:Y1, X0:X1].copy(), m[Y0:Y1, X0:X1]
    out = cv2.inpaint(sub, mk, 4, cv2.INPAINT_TELEA).astype(np.float32)
    # fabric grain: a little noise with the ring's fine-scale spread, so the fill is not a flat smear
    ring = _ring(a, *box).astype(np.float32)
    grain = float(np.clip(ring.std(0).mean() * 0.12, 1.0, 3.0))
    noise = cv2.GaussianBlur(np.random.default_rng(seed).normal(0, grain * 1.6, out.shape[:2]).astype(np.float32),
                             (0, 0), 0.7)[..., None]
    soft = cv2.GaussianBlur(mk.astype(np.float32) / 255, (0, 0), 1.2)[..., None]
    out = np.clip(out + noise * soft, 0, 255)
    a[Y0:Y1, X0:X1] = (soft * out + (1 - soft) * sub).astype(np.uint8)


def match(a, box, kind, k, search=170):
    """Exemplar fill: find the nearby patch whose unmarked pixels best match the area around the
    mark (masked squared difference), then copy only the mark pixels from it with a soft edge."""
    m = mark_mask(a, box, kind, k)
    x0, y0, x1, y1 = box
    pad = 14
    X0, Y0, X1, Y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    tmpl = a[Y0:Y1, X0:X1].astype(np.float32)
    keep = (m[Y0:Y1, X0:X1] == 0).astype(np.float32)
    SX0, SY0 = max(0, X0 - search), max(0, Y0 - search)
    SX1, SY1 = min(a.shape[1], X1 + search), min(a.shape[0], Y1 + search)
    res = cv2.matchTemplate(a[SY0:SY1, SX0:SX1].astype(np.float32), tmpl, cv2.TM_SQDIFF,
                            mask=np.repeat(keep[..., None], 3, 2))
    h, w = tmpl.shape[:2]
    oy, ox = np.mgrid[0:res.shape[0], 0:res.shape[1]]
    overlap = (np.abs(ox + SX0 - X0) < w) & (np.abs(oy + SY0 - Y0) < h)
    res[overlap] = np.inf
    res[~np.isfinite(res)] = np.inf
    iy, ix = np.unravel_index(np.argmin(res), res.shape)
    src = a[SY0 + iy:SY0 + iy + h, SX0 + ix:SX0 + ix + w].astype(np.float32)
    shift = ((tmpl - src) * keep[..., None]).sum((0, 1)) / max(1.0, keep.sum())
    src = np.clip(src + shift, 0, 255)
    soft = cv2.GaussianBlur(cv2.dilate(m[Y0:Y1, X0:X1], np.ones((3, 3), np.uint8), iterations=2)
                            .astype(np.float32) / 255, (0, 0), 2.0)[..., None]
    a[Y0:Y1, X0:X1] = (soft * src + (1 - soft) * tmpl).astype(np.uint8)
    return (SX0 + ix + pad - x0, SY0 + iy + pad - y0)


def redraw_stripe(a, box, orig):
    """Redraw a thin pinstripe that ran under a removed mark: its position is fitted from the rows
    just above and below the box in the original, and it is drawn anti-aliased in its own colour."""
    x0, y0, x1, y1 = box
    pts = []
    for ys in (range(y0 - 14, y0 - 2), range(y1 + 2, y1 + 14)):
        xs = []
        for y in ys:
            row = cv2.cvtColor(orig[y:y + 1, x0:x1], cv2.COLOR_RGB2GRAY)[0].astype(np.float32)
            xs.append(x0 + int(np.argmax(row - cv2.blur(row[None], (15, 1))[0])))
        pts.append((float(np.median(xs)), (ys[0] + ys[-1]) / 2))
    (xa, ya), (xb, yb) = pts
    col = orig[int(ya), int(round(xa))].astype(np.float32)
    layer = np.zeros(a.shape[:2], np.float32)
    def at(y):
        return xa + (xb - xa) * (y - ya) / (yb - ya)
    cv2.line(layer, (int(round(at(y0 - 2) * 4)), (y0 - 2) * 4), (int(round(at(y1 + 2) * 4)), (y1 + 2) * 4),
             1.0, 1, cv2.LINE_AA, shift=2)
    layer = np.clip(cv2.GaussianBlur(layer, (0, 0), 0.5) * 1.6, 0, 1)[..., None] * 0.9
    a[:] = (layer * col + (1 - layer) * a).astype(np.uint8)


def clean(name):
    a = np.array(Image.open(f"{SRC}/{name}.png").convert("RGB"))
    orig = a.copy()
    for i, (_, _, box, method) in enumerate(MARKS[name]):
        if method[0] == "patch":
            patch(a, box, method[1], method[2])
        elif method[0] == "match":
            match(a, box, method[1], method[2])
        else:
            inpaint(a, box, method[1], method[2], seed=i + 1)
        if "stripe" in method:
            redraw_stripe(a, box, orig)
    Image.fromarray(a).save(f"{SRC}/{name}-clean.png")
    return orig, a


def _font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def review(name, orig, cleaned):
    im = Image.fromarray(orig)
    d = ImageDraw.Draw(im)
    f = _font(28)
    for mid, _, (x0, y0, x1, y1), _ in MARKS[name]:
        d.rectangle((x0 - 4, y0 - 4, x1 + 4, y1 + 4), outline=(255, 0, 255), width=4)
        d.text((x0, y0 - 34), mid, fill=(255, 0, 255), font=f)
    im.save(f"{REVIEW}/audit-{name}-boxes.png")
    for mid, label, (x0, y0, x1, y1), _ in MARKS[name]:
        pad = 40
        b = (max(0, x0 - pad), max(0, y0 - pad), min(orig.shape[1], x1 + pad), min(orig.shape[0], y1 + pad))
        z = 4
        tiles = []
        for arr in (orig, cleaned):
            t = Image.fromarray(arr).crop(b)
            t = t.resize((t.width * z, t.height * z), Image.LANCZOS)
            ImageDraw.Draw(t).rectangle(((x0 - b[0]) * z, (y0 - b[1]) * z, (x1 - b[0]) * z, (y1 - b[1]) * z),
                                        outline=(255, 0, 255), width=2)
            tiles.append(t)
        w, h = tiles[0].size
        sheet = Image.new("RGB", (2 * w + 30, h + 50), "white")
        sheet.paste(tiles[0], (0, 50))
        sheet.paste(tiles[1], (w + 30, 50))
        ImageDraw.Draw(sheet).text((6, 10), f"{mid} {label}: before | after", fill="black", font=_font(22))
        sheet.save(f"{REVIEW}/audit-{mid}-before-after.png")


def main():
    for name in MARKS:
        orig, cleaned = clean(name)
        review(name, orig, cleaned)
        print(f"{name}: {len(MARKS[name])} suspects cleaned -> {SRC}/{name}-clean.png")


if __name__ == "__main__":
    main()
