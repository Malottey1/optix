# Engine (v1)

Pure, stdlib-only Python over the CSV tables. It never imports the generator and never reads
`ground_truth.json`; the loader (`engine/tables.py`) also drops the hidden generator columns in
`teams.csv` and `players.csv`. Only tests compare engine output with ground truth.

| Module | What it does |
|---|---|
| `zones.py` | lanes, thirds, final third, box; attacker point of view; `flip` to change frame |
| `tables.py` | load a data directory (`baseline="season"` attaches the season as the league baseline); per-team event index; game state of an event (`score_diff`, 3 and 5 brackets) |
| `metrics.py` | metric functions; each returns `MetricResult(value, evidence_event_ids, sample_size, sd, detail)` and documents definition, inputs and known limits |
| `profiles.py` | `team_style_profile(ds, team, bracket)` against the league average in the same bracket; `bracket_shift` for own-bracket changes |
| `matchup.py` | `lane_matchup` (attacker share lift + defender completion lift per lane, with intervals and confidence) and `matchup_claim` (pending claim object) |
| `threat.py` | xT: 12x8 possession-value grid fitted on the season (`xt_grid`), `xt_added` per pass, `pass_quality_ratio` (share of forward passes into high-threat central cells vs league) |
| `flow.py` | `xa_split` (open play vs set piece), `territorial_stress`, `shot_clusters`, `rhythm` (per-minute series), `momentum` (decayed xT + xG tug of war), `milestones` (within-dataset only) |
| `report.py` | `python -m engine.report --team AUR --opponent NOR [--data DIR] [--season-baseline DIR] [--json]` |

## Reading the numbers: effect size first, z only for ranking

Every comparison against the league reports **effect** (percentage points for shares, units for
means), a **95% interval** (Wilson score for shares, normal approximation for means), a
**confidence** label and the **sample size**. A sampling z-score is still computed, but only as an
internal tie-break signal.

Why not z: a sampling z grows with the square root of the sample. Over a season, a 1 pp difference on
5,000 passes has |z| > 2 while a 10 pp difference on 60 passes does not, so ranking by z ranks
"lots of data" rather than "big difference". Event-level observations within a match are also not
independent, so z overstates certainty. An effect plus an interval answers the two questions a
reader has: how big, and how sure.

- League average: the metric pooled over every team in the same game-state bracket of the
  **baseline dataset** (the dataset itself, or the season when a single match is loaded with
  `load(dir, baseline="season")`; a match is never its own baseline). A team is part of its own
  league average.
- Wilson intervals: they stay inside [0, 1] and behave at small n, where the normal approximation
  gives intervals below 0 or above 1.
- Confidence (shares, `metrics.share_confidence`): **high** = n >= 200, half-width <= 5 pp and the
  interval excludes the baseline; **medium** = n >= 50 and the interval excludes the baseline;
  **low** otherwise. Means use the same n and exclusion rules (`interval_confidence`).
- Matchup score per lane = attacker's share lift over the league (pp) + defender's conceded-entry
  **completion** lift over the league (pp). A lane only counts when both lifts are positive. The
  matchup's confidence is the lower of the two sides.

## Soft lanes: completion rate, not share

`metrics.entry_completion_by_lane(conceded=True)`: for the defending team, completed / attempted
final-third entry passes by its opponents, per lane (attacker point of view), against the league
rate for that lane. `profiles.soft_lane()` flags at most one lane per team: the largest lift, if
it is >= 6 pp (`SOFT_LANE_MIN_PP`) and the lower end of the team's Wilson interval is above the
league rate.

**Why HAR's right flank was missed.** The *share* of entries a defence concedes into a lane mostly
reflects where its opponents like to attack: every attacker has its own lane habits, and the
weak-lane bonus changes how often an entry succeeds, not how often it is tried. The generator's
true effect, measured from its own logged success probabilities (`tests/soft_lane_truth.py`: pass
difficulty = 1 - p, remove the 0.09 x weak_strength bonus), is the same for HAR and NOR:

| Team | Lane | weak_strength | true effect (pp, low-high) | completion lift found (pp) | attempts |
|---|---|---|---|---|---|
| NOR (small) | left_flank | 1.0 | 8.4-9.0 | +7.6 | 190 |
| HAR (small) | right_flank | 1.0 | 6.7-9.0 | not flagged | 186 |
| NOR (full) | left_flank | 1.0 | 7.7-9.0 | +11.2 | 290 |
| HAR (full) | right_flank | 1.0 | 7.3-9.0 | +7.2 | 505 |
| FWM | center | 1.0 | 7.8-9.0 | +8.9 | 555 |
| HBC | left_flank | 2.0 | 12.7-18.0 | +9.2 | 449 |
| MDL | right_half_space | 1.5 | 10.3-13.5 | +9.8 | 316 |
| OKP | right_flank | 2.5 | 11.1-22.5 | +17.8 | 426 |
| RVD | left_half_space | 0.6 | 5.1-5.4 | +7.4 | 335 |
| IRK | right_flank | 0.3 | 2.7 | not flagged | 435 |

(The low bound treats passes clamped at the 0.97 success ceiling as gaining nothing.)

Conclusions:
- Completion rate recovers HAR on the full league. On the 40-match season HAR has only 186 attempts
  into that lane: the 95% interval half-width is about 6 pp, as large as the effect, so it is not
  reliably recoverable there. That is a sample-size limit, not a broken metric.
- Stated recoverable size: a planted soft lane with true effect >= 5 pp is recovered on the full
  league (7 of 7; slow test `test_soft_lanes_recovered_above_stated_size`), with 0 of 12 unplanted
  teams flagged. IRK's 2.7 pp plant is below what ~400 attempts can resolve.

## Pressing: why ball-won height and PPDA mislead for CAL

CAL is the planted high-press team. On this data:
- **Ball-won height** (mean x of tackles and interceptions) puts CAL at 39.3 against AUR's 40.3. It
  mostly reflects where the *opponent* plays: a pinned-back team wins the ball low whatever it
  does (NOR: 26.0), and a team that dominates territory wins it high without pressing.
- **PPDA** (opponent passes in their own 60% per tackle or interception) gives CAL 5.68, about the
  same as VES at 5.57. Both its numerator and denominator depend on where the opponent chooses to
  play and on how many of its passes fail anywhere, so territory and opponent style blur the press
  signal. (Not diagnosed further; the observed numbers are what matter for the rule.)
- **press_intensity** (pressure events per opponent pass) isolates the behaviour: CAL 0.275, nearly
  double the next team (0.146), and the full league's high-press archetype teams all sit above the
  league average.

The Verifier rule `ppda_alone` refers to this: a pressing claim backed only by PPDA (or ball-won
height) is context-flagged, because on event data like this it can rank a non-pressing team level
with a pressing one.

## Step 4 metrics on the planted traps

- Volume passer NOR_07: pass_quality_ratio 0.19 (league 1.0); the other top-25 forward passers range
  0.27-2.28. His forward passes go into the channel, not into high-threat central cells.
- Corner specialist NOR_11: open-play xA per chance created 0.035, second lowest of the 20 players with
  15+ chances (median about 0.07); his set-piece xA (1.67) exceeds his open-play xA (1.27).

## Known gaps

- npxG equals xG because the data has no penalties yet.
- HAR's soft lane is not recoverable from the 40-match season (see above); it is on the full league.
