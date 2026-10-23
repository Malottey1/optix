# Brand artwork audit

**Author must visually confirm** every result on this page before the artwork is shown publicly. The
checks below were made by zooming in and by eye; a script cannot decide whether a patch still reads as a
logo. The originals and all review crops stay local (`design/source/`, `design/review/`, both gitignored).

## Uploaded files

Identified by content, copied (not moved, not edited) into `design/source/`:

| Role | Content | Original file | Copied to |
|---|---|---|---|
| players-trio | three players (NTG, AUR, CAL goalkeeper) on white | `~/Downloads/optix-graphics/3-player cutout-white-background.png` | `design/source/players-trio.png` |
| kit-sheet | five crests with names, home and away shirts on light grey | `~/Downloads/optix-graphics/badges-and-kits.png` | `design/source/kit-sheet.png` |
| logo-mark | O and X with a curved arrow, black on white | `~/Downloads/optix-graphics/favicon.png` | `design/source/logo-mark.png` |
| logo-wordmark | "Optix" with a curved arrow and a large X, black on white | `~/Downloads/optix-graphics/logo-optix.png` | `design/source/logo-wordmark.png` |
| hero-lineup | five players over five colour bands (AUR, NTG, CAL, VES, HAR) | `~/Downloads/optix-graphics/website-hero-image.png` | `design/source/hero-lineup.png` |

All five are 2304×1728 RGB PNG. Note that the file named `favicon.png` is the logo mark, not a favicon.

## Third-party marks (Step 1)

Tool: `python -m tools.brand_audit`. It records the boxes and methods (see `MARKS` in
`tools/brand_audit.py`) and writes:
- `design/review/audit-<image>-boxes.png`: the whole image with every suspect boxed;
- `design/review/audit-<id>-before-after.png`: each suspect at 4x, original left, cleaned right.

Methods:
- OpenCV Telea inpainting of the mark pixels only, found with a top-hat or a low-saturation mask;
- exemplar fill by masked template matching;
- for H8, the pinstripe that ran under the mark is redrawn.

There are also actual-size and contact views (`design/review/hero-actual-size-before-after.png`, `contact-*.png`), plus the first zoom crops (`hero-zoom-*.png`, `trio-zoom-*.png`, `grid-*.png`).

### hero-lineup: cleaned, used (pending author confirmation)

| Id | Where | Suspected mark | Method | Result |
|---|---|---|---|---|
| H1 | AUR chest | chevron maker-style mark (resembles a real kit maker's logo) | inpaint, white mask | removed; at 4x a faint lighter area remains on the gold stripe, not visible at display size |
| H2 | AUR left sleeve | same chevron plus a small curved stroke | inpaint, top-hat | removed, clean |
| H3 | AUR collar | small emblem | inpaint | removed, clean |
| H3b | AUR collar | scribble mark | inpaint | removed, clean |
| H4 | AUR under crest | maker-style lettering | exemplar fill | removed; slight streak at 4x |
| H5 | CAL chest | chevron maker-style mark | exemplar fill | removed, fabric pattern continues |
| H6 | CAL right sleeve | small emblem | inpaint | removed, clean |
| H7 | CAL under crest | maker-style lettering | inpaint | removed, clean |
| H8 | VES chest | chevron maker-style mark across a pinstripe | inpaint plus pinstripe redrawn | removed; the stripe is a little thinner at 4x |
| H9 | VES under crest | maker-style lettering | inpaint | removed, clean |
| H10 | VES right sleeve | small emblem | inpaint | removed, clean |
| H11 | HAR chest | tick/chevron maker-style mark | exemplar fill | removed, clean |
| H12 | ball | small round emblem in the star panel | inpaint | removed, clean |

Checked and judged clear:
- NTG shirt front (only the fictional crest);
- HAR sleeves;
- gloves (patterned; a faint strap texture with nothing readable);
- the ball's panels.

Shorts and socks are not in the frame.

Verdict: **not blocked.** No mark is visible at display size (`hero-actual-size-before-after.png`), and none reads as a logo at 4x. Derivatives are made only from `hero-lineup-clean.png`.

### players-trio: BLOCKED (not used anywhere)

| Id | Where | Suspected mark | Result |
|---|---|---|---|
| T1 | AUR shirt | swoosh-style tick (resembles a real kit maker's logo) | removed, clean |
| T2 | AUR shorts | tick-like stroke under the number | **smudged**: the fill ate the foot of the "10" |
| T3 | NTG shirt | winged/chevron mark | removed, clean |
| T4 | NTG glove | striped winged mark on the strap | **smudged**: a dark blob over glove and skin |
| T5 | NTG shorts | small diagonal side mark | removed, clean |
| T7 | CAL right glove strap | patterned maker-style patch | **smudged**: green bleeds onto the strap |
| T8 | CAL shirt hem | woven label | removed, clean |
| T9 | CAL left glove | emblem in the pattern | **smudged**: a dark streak across the glove |

Checked and judged clear:
- the ball's panels (a generic star-panel pattern);
- the CAL sleeve (tonal print);
- the boots;
- the AUR socks (lion crest only).

Verdict: **BLOCKED**, because four regions are smudged. There is a second reason: the image has no alpha channel, and each player has a white cut-out outline, so a flood-fill alpha would leave a white halo on the dark UI. `players-trio-clean.png` exists locally for review only.

## kit-sheet: not altered (concerns noted)

- **Maker marks:** none visible on the ten shirts at full resolution.
- **Northgate Town crest:**
  - the ring text reads "ORTHGATE TOW": it starts mid-word (the N is missing) and is cut off at the end;
  - the code under the castle reads "NTS", not "NTG".
  - The crests on the NTG shirts in all three images carry similar garbled text.
  - Not redrawn (as instructed). The app shows the code NTG beside the crest, and below 40 px a code mini-mark is used (see Step 3).
- **Resemblance to real clubs** (to be judged by the author):
  - Veston United: a striped blue-and-white shield with a rampant beast, and blue-and-white kits. Similar to the general look of some real English clubs' crests; the name and the beast are different.
  - Harbor Wanderers: sky blue and navy with a ship on a round crest. Some real clubs use a ship and sky blue.
  - Aurelia Rovers: navy and gold with a lion.
  - Calder Athletic: green shield with mountains.
  - Northgate Town: red and black with a castle.
  - None copies a real crest's layout or text. All names are fictional.
- **Garbled lettering:** the small text on the shirt crests is AI-garbled. At kit-thumbnail size this is not legible.

## What the author must visually confirm

1. **hero-lineup:** the cleaned image, at full size, shows no kit-maker logo on any shirt, sleeve or ball. Look at H1, H4 and H8 in particular (`design/review/audit-H1-before-after.png` etc.).
2. **players-trio:** agree that it stays unused (BLOCKED), or supply a version without maker marks.
3. **Crests:** none of the five is too close to a real club's crest. Decide whether to fix the NTG crest text.
4. **AI tool terms:** the terms of the AI tool used allow this use of the outputs (see `design/ASSETS.md`).
