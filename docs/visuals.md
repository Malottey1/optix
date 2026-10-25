# Visuals

Football-native visuals in the web/ dashboard. Each one is evidence for a claim or a metric the
engine already produces; none invents data. They are hand-written SVG React components in
`web/src/components/viz/` (plus `web/src/features/live/Flow.tsx`), with pure geometry and scale
functions in `web/src/lib/viz.ts` (unit-tested in `viz.test.ts` and `components/viz/helpers.test.ts`).

Every visual:
- sits in a `<figure data-viz="…">` with an `aria-label` summary on the drawing, a visible caption
  and a visually hidden table with the exact numbers (`components/viz/Figure.tsx`);
- carries data attributes tests read (`data-lane`, `data-team`, `data-event-id`, `data-claim-id`,
  `data-value`);
- uses the dark tokens. Colour is never the only carrier: shape, pattern, a letter or a printed
  number says the same thing;
- shows no moving parts under reduced motion (the crosshair pulse stops; the rhythm and gauges
  jump to the playhead).

Data: `web/public/data/ui.json`, section `visuals` (written by `agents/dashboard_data.visuals_section`,
a plain export of existing engine output; see docs/visuals-plan.md), plus `teams`, `players`,
`track` and `evidence`. Every number on screen is either a data value or one of the formulas below.
`tools/check_web.py` recomputes those formulas independently in Python (`visual_numbers`) and fails
on any number that is neither.

## Built

### V1 Mismatch crosshairs (Match Hub Matchup, only with a verified lane claim; live matchup card)
- **Question:** where does this attacker's habit meet this defender's soft spot?
- **Fields:** `teams.head_to_head[].lanes[l].attack_share` and `.league_share`; the defender's
  `teams.teams[].entry_lanes_conceded[l].share` and `.league`; `head_to_head[].claim.lane`,
  `.status`. On Live: the `matchup_mismatch` card's claim (`zone.lane`, `verification.status`).
- **Formula:** per lane, a bar up = the attacker's share of final-third entries, a hatched bar down =
  the defender's share of entries conceded; white ticks = league. The crosshair is drawn only when
  a claim exists and is not blocked, on `claim.lane`.
- **Mirror:** all lanes are in the attacker's frame (both sides of a lane describe the same strip
  of grass). The caption names the defender's own side (`mirrorLane`).
- **Claim:** `matchup.weak_lane`. The lane table stays available under "Lane table".
- **Caveat:** season aggregates.

### V2 Shot blocks (live console: shot-quality panel and xG cards)
- **Question:** is a pile of shots worth much?
- **Fields:** `visuals.shots` = [event_id, clock_sec, team, player_id, x, y, xg, result, shot_type];
  the claim's `window` and `subject.team_code`.
- **Formula:** block side = 18·√xG, so the block's area is proportional to xG. Fill by result:
  goal solid, saved half fill, blocked hatched, off target outline. Caption: shots, Σ xG (2 dp),
  Σ xG / shots (3 dp), over the claim's window and team (cards) or up to the playhead (panel).
- **Claim:** `xg` team claims, in particular the twenty low-xG shots trap (shot spam).
- **Caveat:** shot location is the event location; xG comes from the generator's shot table.

### V3 Game-state swaps (Team Board, compact: one team, one-line caption)
- **Question:** how does a team's play change once it goes ahead?
- **Fields:** `visuals.states[code].{trailing,leading}.{field_tilt,press_intensity}` (value, league,
  n, interval, confidence); `visuals.state_min_n`.
- **Formula:** x = field tilt (share of the match's final-third passes), y = press intensity
  (pressure events per opponent pass), from `engine.profiles.team_style_profile` per bracket.
  Ring = trailing, diamond = leading, arrow from trailing to leading. Shown values: tilt × 100 to
  1 dp, press to 3 dp. A state is drawn only if both metrics have n ≥ `state_min_n` (50, the
  engine's medium-confidence sample size); otherwise "not enough data".
- **Claim:** the context rule for field tilt from a trailing side (a leader sitting deep hands over
  territory), the Perimeter Lock rewrite.
- **Caveat:** season data, the team's own score state; descriptive, not causal. Axes carry no
  tick numbers on purpose.

### V4 Pass routes (Player Console)
- **Question:** where do a player's passes go, and are they worth anything?
- **Fields:** `visuals.routes[player]` = [kind, from_zone, to_zone, passes, sum, hot];
  `visuals.league_hot_share`; `visuals.zones`.
- **Formula:** zone = third · 5 + lane (attacker's frame). Width ∝ √passes. Colour on a grey →
  green sequential scale: forward passes = route pass quality (hot / passes) / league_hot_share
  (the engine's `pass_quality_ratio` per route, 2 dp; top of scale 2×); chances = xA per chance
  (sum / passes, 3 dp; top of scale twice the league value). Forward routes need at least 2
  passes to be drawn; set-piece routes are dashed. League xA per chance = Σ xA / Σ chances over
  every player's chance routes.
- **Default view:** only the 8 busiest routes (by passes; ties by start zone, end zone, kind),
  each bent by 5% of its length and offset 1.1 pitch units to the right of travel, so a route and
  its reverse never overlap. "Show all routes (N)" draws every drawable route. The caption gives
  the routes drawn and their passes out of the total; the hidden table always lists every route.
- **Claims:** the volume passer (thick but grey: many forward passes, rarely central) and the
  set-piece creators (dashed corner routes).
- **Caveat:** coarse 3 × 5 zones; season totals.

### Live layout at 1600 px and wider
At 1600 px+ (the `wide` breakpoint) the Live Center is a three-column dashboard under the score
and scrubber: the rhythm strip runs full width under the scrubber (same time axis), then the
Focus Pitch | Perimeter Lock, gauges, momentum | shot quality over the stream. At 1920x1080 and
1600x900 every Live visual is on the first screen (`check_first_screen`). To fit 1600x900 some
subtitles are hidden at that width (pitch, Perimeter Lock, rhythm, gauges, shot quality); their
captions, aria labels and tables stay, and the pitch's caption card returns when the screen is at
least 1000 px tall. Below 1600 px the layout is unchanged.

### V5 Pinned-in-own-half gauges (Live, ADAPT of "Territorial Stress")
- **Question:** how long has each side been pinned back?
- **Fields:** `visuals.stress[code]` = [start_sec, end_sec, seconds, n_events].
- **Formula:** a team's gauge = cumulative seconds of the opponent's territorial-stress spells up
  to the playhead (`stressAt`), out of the full-match total. Updated per frame through refs.
- **Caveat:** the engine's spell is the opponent keeping the ball in this team's half (x ≥ 50)
  with no on-ball event by this team; it is not "own third", and territory is not threat (read it
  with the Perimeter Lock).

### V6 Rhythm pulse (Live, and the rhythm card)
- **Question:** is the game calm or chaotic right now?
- **Fields:** `visuals.rhythm` = [period, minute, start_sec, possession_changes, tempo_var].
- **Formula:** height = possession changes in the minute (`engine.flow.rhythm`, run per period),
  mirrored around the centre line; only the played part is drawn. Caption: the peak so far.
- **Caveat:** whole minutes; added time folds into the minute it is logged in. Static under
  reduced motion.

### V7 Evidence chain (Live evidence drawer, ADAPT)
- **Question:** what events back this claim, in order?
- **Fields:** `evidence[id]`; the insight's `evidence_event_ids`.
- **Formula:** the claim's evidence events in clock order as linked nodes; shape and colour by
  event type (pass circle, shot triangle, possession change square, tackle / interception diamond,
  foul cross). Clicking a node pins it on the drawer's pitch. The event table stays.
- **Caveat:** there is no sequence detection in the engine, so this is the evidence chain, not a
  detected move.

### V8 Percentile pizza (Player Console)
- **Question:** how does this player rank on involvement, pass quality and chances?
- **Fields:** `players[]`: involvement, forward_passes, pass_completion, pass_quality_ratio,
  chances_open_play, wide_share, chances_set_piece.
- **Formula:** percentile = 100 · (below + ½ · equal) / n against outfield players with at least
  100 passes (n shown), rounded to a whole number. Slice radius = percentile. Letters A–G link the
  slices to the list with value and percentile.
- **Caveat:** season totals, not per 90 (the data has no minutes).

### V10 Zone shift (retired from the Team Board; replaced by V12)
- **Question:** where did each side have the ball in the second half compared with the first?
- **Fields:** `track` = [clock_sec, x, y, team] (the showcase match's on-ball events, acting team's
  attacking frame); `timeline.periods`; `visuals.zones.third_x`.
- **Formula:** per half, the team's share of its on-ball events per zone (3 × 5); cell = second-half
  share − first-half share, in points (1 dp), with the signed number printed in the cell; purple →
  grey → green diverging colour scaled to the largest change. Event counts per half in the caption.
- **Claim:** supports the field-tilt-while-leading context: a side that leads and sits deep shows
  its share rising in its own third.
- **Caveat:** event locations, not tracking; on-ball share, not possession time; descriptive only.

### V12 Heat map (HeatPitch: Match Hub, Player Console touch map)
- **Question:** where did a side (or a player) have the ball, and where did that move between halves?
- **Fields:** `heat` in `matches/<id>.json`: raw on-ball event counts per bin, per team and half, on
  a zone-aligned 24 × 16 grid (8 columns per third; rows 3/3/4/3/3 per lane), attacking frame;
  `players-heat-<code>.json`: one season bin list per player.
- **Formula:** density = Gaussian-smoothed count (sigma 1 bin, separable, edge-normalised, so the
  mass is exact) per 1 % of the pitch area; volume uses `--heat-seq` as opacity, the legend's top is
  the largest density (1 dp); change = second-half density − first-half density, `--heat-fall` /
  `--heat-rise`, symmetric scale. View data: per zone, first- and second-half shares (%, 1 dp) and the
  change in points; zone shares from the bins equal the 15-zone shares of the track exactly.
- **Caveat:** event locations, not tracking; the smoothing is display only; heat colours are never
  verdict colours (tokens.test.ts).

### V13 Lineup pitch (Team Board)
- **Fields:** `lineups[code]`: the 11 players with most starts (ties by id), the `shirt` field,
  `line` (GK, DF, MF, FW), `slot` and `of` from the listed role's left-to-right order; label =
  DF-MF-FW counts.
- **Layout:** one column per line, slots spread evenly inside a line, so two nodes never share a
  spot. Footnote: "Most-used starting XI, laid out by listed position. Not a tracked shape."

### V14 Style pizza and lane-lift strip (Team Board)
- **Style pizza:** one slice per fingerprint measure; slice length = team value / league average
  (capped at 1.6), the dashed ring = the league.
- **Lane-lift strip:** five lane bands across one pitch, coloured by the team's share of
  final-third entries in the lane minus the league share (points, diverging heat tokens).

### V15 Percentile bars (Player Console)
- **Formula:** for each pizza slice, percentile − 50 (same group and rounding as V8), drawn as a bar
  left or right of the median. Not the skipped V9 (per-match values).

## Polished (already built)
- **Tug-of-war momentum bar:** shows who is pulling in words, never a raw percentage.
- **Perimeter Lock, evidence drawers, threshold tooltips, Rewritten chip:** unchanged apart from
  the event chain in the drawer.
- **Visual guide:** a short legend of every visual on the Tech Blueprint.

## Skipped
- **V9 Diverging performance bars:** needs per-match player values; ui.json has season totals only.
- **V11 Defensive footprint polygons:** needs a red card; the showcase has two yellows.
- **Off-ball attraction vectors:** needs tracking data; the data is event-based.
- **Weighted deficit stack:** needs fatigue data; no fitness data by design.
- **Radar equilibrium diamonds:** needs a service-starvation claim the Verifier does not have.
- **HIR decay lines:** needs GPS speed data.

## Checks
- Vitest: every geometry and scale function (area ∝ xG, √ widths, percentile, lane mirroring,
  zone index and shares, colour scales, stress accumulation, arcs, display rounding).
- `python -m tools.check_web --ref out --mutation-proof`: every number traces to data or a formula
  above; `check_consistency` compares each visual with the engine output (crosshair lane = the
  verified claim's lane on every final with a lane claim (and no Matchup section without one) and on
  the live cards; heat bins = the match file's counts; touch map = players-heat counts; lineup nodes
  = the most-used XI with its numbers; shot blocks = the claim window's shots
  and xG; gauges at full time = the spell totals; arrow count and width order = the pass counts;
  pizza = an independent percentile computation); the routes are checked in the default view and
  after "Show all routes"; the mutation proof changes one visual's data in a throwaway copy and
  shows the matching check fails (nine mutations: crosshair, heat, touch map, lineup, shot blocks,
  gauge, routes, routes default view, pizza; plus the text-budget and lane-wording proofs).
  `check_first_screen` asserts every Live visual is whole on the first screen at 1920x1080 and
  1600x900 with no overlapping text. `tests/test_visuals_consistency.py` runs
  the proof in the slow suite.
