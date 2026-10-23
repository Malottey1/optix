# Icon plan (A0 audit)

Audit of every icon-like glyph in `web/src` before the icon set (branch `ui-visuals-icons`). The
registry (`web/src/icons/`) holds the 54 icons of the design sheet. Interface glyphs that are not on
the sheet (close, arrow, swap, ball marker, cloud) stay in `components/icons.tsx` as `Glyph`.

## Focus Pitch lane convention (recorded before drawing the lane icons)

- Data frame (engine/zones.py): x 0 to 100 from the acting team's own goal to the opponent goal,
  y 0 to 100 across, **y = 0 is the attacker's left touchline**. Lanes are 20 wide in y:
  left_flank [0, 20), left_half_space [20, 40), center [40, 60), right_half_space [60, 80),
  right_flank [80, 100].
- Drawing (components/pitch/Pitch.tsx): every team attacks **left to right**, and SVG y = data y x
  0.68, so **the left flank is the top band** and the right flank the bottom band. The matchup lane
  band is a rect from `y_min * PY` to `y_max * PY` on a 68-high pitch.
- The sheet draws the left flank at the top of a landscape pitch too, so no flip is needed. The lane
  icons draw a landscape pitch with band i covering the y-fraction [i/5, (i+1)/5); a Vitest test
  compares it with the Focus Pitch band.

## Replacements

| Location | Current glyph | Replacement | Notes |
|---|---|---|---|
| Header nav and phone tab bar (AppShell) | live, teams (pitch), players (one person), tech (sliders) | `live`, `teams`, `players`, `tech` | teams becomes the shield with a band; players gets a second person |
| Header settings button | settings (gear path) | `settings` | |
| Header brand link | traced wordmark (Logo) | unchanged | the logo is not an icon |
| Transport play / pause | filled triangle, filled bars | `play`, `pause` | outline, per the sheet |
| Transport restart | restart | `restart` | |
| Transport speed control | none | `speed` | added before Slow / Normal / Fast |
| Scrubber | none | `scrub` | decorative, before the timeline |
| Verdict chips (ui/badge StatusChip), ledger filters, Tech steps | check, info, rewrite, block | `verdict-passed`, `verdict-context`, `verdict-revised`, `verdict-blocked` | colour stays on the chip (tokens), never in the glyph |
| Feed evidence summary, drawer | evidence (document) | `evidence-drawer` | |
| Evidence chain nodes and their legend (EvidenceChain NodeShape) | circle, triangle, square, diamond, cross, ring | event icons: `pass`, `shot`, `tackle`, `interception`, `pressure`, `foul`, `possession-change`, `substitution`, `yellow-card`/`red-card`, `goal` (saves and goals), `corner` | the event colour is kept; types without an icon (carry, duel, block, clearance, claim, dribble, offside, half_end) keep the ring |
| Feed card type chip | text only | metric glyph per insight type (see below) | |
| Team Board lane rows (LaneLift) and soft-lane line | lane name text | `lane-*` before the name | |
| Team Board style-label chips | info | style or metric icon by label (below); the info glyph becomes `verdict-context` | |
| Team Board "Attacks from" line | text | `style-wing-play` (flank), `style-central-play` (centre), lane icon (half-spaces) | |
| Team Board head-to-head swap button | swap | unchanged (`Glyph swap`) | not on the sheet |
| Home CTAs | live, shield | `live`, `verdict-passed` | |
| Home feature cards | inline drawings (ArtFacts, ArtEvidence, ArtTranslate) | drawings kept; `trace-to-data`, `evidence-drawer`, `verdict-passed` beside the titles | the drawings are illustrations, not glyphs |
| Home clubs link, Feed and Focus Pitch links | arrow | unchanged (`Glyph arrow`) | not on the sheet |
| Focus Pitch ball-marker note | ball | unchanged (`Glyph ball`) | a pitch marker, not an event type |
| Tech pipeline steps | live, chart, shield, layers, check, flag | `pass` (event stream), `metric-xt` (analyst), `verdict-passed` (verifier), `evidence-drawer` (narrative), `trace-to-data` (number guard), `live` (insight stream) | |
| Tech Azure states | check, cloud | `verdict-passed`; `Glyph cloud` (not built) | |
| Sheet close button | close | unchanged (`Glyph close`) | |

### Insight type -> glyph (Feed card chip)

| insight_type | Icon |
|---|---|
| matchup_mismatch | the lane icon of the claim's lane (fallback `lane-centre`) |
| perimeter_lock | `metric-field-tilt` (its standard stat) |
| threat_pass | `metric-xt` |
| momentum_shift, turning_point | `metric-momentum` |
| rhythm_wave | `metric-rhythm` |
| volume_vs_value | `pass` |
| set_piece_inflation | `corner` |
| player_focus | `players` |
| shot quality cards (xG) | `metric-xg` |
| recap_line, milestone and others | `evidence-drawer` |

### Style label -> icon (Team Board)

| Label id | Above the league | Below | Typical |
|---|---|---|---|
| tempo | `metric-rhythm` | `metric-rhythm` | `metric-rhythm` |
| press | `style-high-press` | `pressure` | `pressure` |
| directness | `style-direct-play` | `style-patient-possession` | `pass` |
| territory | `metric-field-tilt` | `style-low-block` | `metric-field-tilt` |
| counter | `possession-change` | `possession-change` | `possession-change` |

The pattern icons are drawn now and used by Part B.
