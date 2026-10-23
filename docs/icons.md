# Icons

Optix has one icon set: 54 icons drawn by hand as SVG from the author's design sheet ("OPTIX ICON
SET"). They live in `web/src/icons/`. The audit of what they replaced is in docs/icons-plan.md. The
contact sheets are in docs/screens-v5/icons-16.png, icons-24.png and icons-64.png, each on a dark and
a light background.

```tsx
import { Icon } from "../../icons";

<Icon name="verdict-passed" />                                       // decorative, 20 px
<Icon name="live" size={18} className="text-accent" />
<Icon name="pressure" title="Pressure" />                             // role="img", named by the title
```

## The set

| Group | Icons |
|---|---|
| Navigation | live, home, teams, players, tech, settings |
| Playback | play, pause, restart, speed, scrub |
| Event types | pass, shot, goal, tackle, interception, pressure, possession-change, foul, yellow-card, red-card, substitution, corner |
| Lanes | lane-left-flank, lane-left-half-space, lane-centre, lane-right-half-space, lane-right-flank |
| Verdicts | verdict-passed, verdict-revised, verdict-blocked, verdict-context, evidence-drawer, trace-to-data |
| Style labels | style-high-press, style-low-block, style-patient-possession, style-direct-play, style-wing-play, style-central-play |
| Metric glyphs | metric-xg, metric-xt, metric-field-tilt, metric-momentum, metric-territorial-stress, metric-rhythm |
| Pattern icons | pattern-bait-switch, pattern-cutback, pattern-flank-isolation, pattern-elastic-low-block, pattern-counter-press, pattern-rest-defence, pattern-starved-finisher, pattern-tactical-fouling |

`src/icons/semantic.ts` maps data to icons: insight types and claim metrics, lanes, event types
(types without an icon, such as carry, duel, block or clearance, keep a ring in the evidence chain),
Team Board style labels, and a team's main attacking lane.

Interface glyphs that are not on the sheet (close, arrow, swap, the Focus Pitch ball marker, cloud)
are `Glyph` in `src/components/icons.tsx`. They follow the same drawing rules.

## Rules

- viewBox 0 0 24 24; stroke 1.75; round caps and joins; `fill="none"`, except small dots and marks
  (`fill="currentColor"`); default size 20 px.
- Colour comes only from `currentColor`, with three token exceptions (tokens.css):
  - `--card-yellow` and `--card-red` fill the two card icons;
  - `--lane-fill` (the accent) fills the emphasised band of a lane icon, at 70%, plus a
    full-strength stroke.
- Verdict colours (green, amber, red) come from the chip that holds the icon, never from the glyph.
  The high-press icon is neutral: never verdict red.
- Decorative by default (`aria-hidden`). With `title` an icon is `role="img"` with that name. An
  icon-only button carries its own `aria-label` (en/es/fr via i18n).
- No raster, no `<text>`, no `<image>`, no external or data: references. The icons are drawn by hand,
  not traced; no raster of the sheet is embedded anywhere.
- Lane icons follow the Focus Pitch: every team attacks left to right, and the attacker's left flank
  is the top band. Band i covers the y-fraction [i/5, (i+1)/5). A Vitest test compares each glyph's
  band with the Focus Pitch lane band.
- Foul and pattern-tactical-fouling are a deliberate pair (the same whistle; the second adds a
  clock). Every other pair must stay clearly distinct.

## Checks

- `web/src/icons/icons.test.tsx` (Vitest):
  - exactly the 54 names, in their groups;
  - every icon is a 24 x 24 outline SVG with the stroke rules;
  - only the allowed paints and tokens;
  - no raster, text or remote reference;
  - accessible name with a title;
  - lane bands match the Focus Pitch.
- `tests/test_icons.py` (pytest; needs Playwright, so it runs locally and is skipped in CI like
  test_dashboard):
  - each icon is rendered alone at 16 and 24 px in Chromium (`tools/icon_sheet.py`);
  - every pair is compared by normalised correlation and the test fails above 0.92, except the
    foul pair;
  - named pairs (live and territorial stress, live and pressure, players and teams, tech and
    settings, revised and restart, revised and possession change, ...) are asserted below the
    threshold;
  - a mutation (pressure drawn as a copy of live) must be caught.
- `python -m tools.icon_sheet` writes the contact sheets and prints the most similar pairs.

## Adding an icon

1. Draw it in a 24 x 24 box following the rules above. Look at it at 16 px on dark and light.
2. Add `web/src/icons/glyphs/<name>.tsx` exporting `<Pascal>Icon` that returns the SVG children (a
   fragment). Put the name in its group in `names.ts` and in `registry.ts`.
3. If it stands for a data value, map it in `semantic.ts`.
4. Run `npm test`, `.venv/bin/python -m tools.icon_sheet` (look at the sheets) and
   `.venv/bin/python -m pytest tests/test_icons.py`. Update the expected list in both tests: the
   manifest is deliberately exact.

Bundle: the whole set is one module of small path lists. It added about 3 KB gzip to the initial
JavaScript, under the 12 KB at which the pattern and metric groups would be lazy-loaded.
