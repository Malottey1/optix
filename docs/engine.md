# Engine (v1, updated for realism v2)

Realism v2 changed the data, not the engine's design. Engine-side changes: PPDA counts fouls as
defensive actions (the standard definition; `metrics.PPDA_ACTIONS`); ball-won height counts won
tackles and interceptions only; the soft-lane rule gained a lift-based own-lanes gate; two Verifier
rules were retuned on the v2 full league (see "Verifier"); the Analyst's half-time summaries fire on
the first-half `half_end` event instead of at 2,700 s, because the clock now runs through stoppage
time. New event types (fouls, cards, substitutions, duels, saves and others) need no special
handling: metrics select the event types they define, and players who come off the bench are
ordinary players.

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
| `claims.py` | `compute` (recompute registry: metric -> values + evidence predicate) and `build_claim` (pending claim objects) |
| `verifier.py` | fact check and context check on claim objects; rules in `rules/` |
| `report.py` | `python -m engine.report --team AUR --opponent NTG [--data DIR] [--season-baseline DIR] [--json]` |

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
it is >= 4 pp (`SOFT_LANE_MIN_PP`), the lower end of the team's Wilson interval is above the
league rate, and the lane's lift over the league rate stands out from the team's pooled lift in
its other lanes (z >= 2.33, `SOFT_LANE_MIN_Z_OWN`: one-sided 5% Bonferroni-corrected for five
lanes; lifts rather than raw rates because lanes have different league baselines). The last gate stops a
side that often sits deep, and so concedes completions everywhere, from being read as soft in one
lane. (Realism v2: was >= 6 pp with no own-lanes gate.)

**Why HAR's right flank was missed.** The *share* of entries a defence concedes into a lane mostly
reflects where its opponents like to attack: every attacker has its own lane habits, and the
weak-lane bonus changes how often an entry succeeds, not how often it is tried. The generator's
true effect, measured from its own logged success probabilities (`tests/soft_lane_truth.py`: pass
difficulty = 1 - p, remove the 0.09 x weak_strength bonus), is the same for HAR and NTG:

| Team | Lane | weak_strength | true effect (pp, low-high) | completion lift found (pp) | attempts |
|---|---|---|---|---|---|
| NTG (small) | left_flank | 1.0 | 8.4-9.0 | +7.6 | 190 |
| HAR (small) | right_flank | 1.0 | 6.7-9.0 | not flagged | 186 |
| NTG (full) | left_flank | 1.0 | 7.7-9.0 | +11.2 | 290 |
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
- Stated recoverable size (v1): a planted soft lane with true effect >= 5 pp was recovered on the
  v1 full league (7 of 7), with 0 of 12 unplanted teams flagged.
- **Detection limit (v2): soft lanes below roughly 7 percentage points are not reliably detected.**
  A season gives about 600 conceded entry attempts per lane (sd about 1.9 pp), so 5 pp is only
  2.6 sd. On the five full leagues of seeds 2026-2030 every plant with a true effect >= 7 pp is found
  (6 of 6 per league) with 0 of 12 unplanted teams flagged, and the two weaker plants (IRK about
  2.6 pp, RVD about 5.2 pp) are never found (docs/robustness.md; slow test
  `test_soft_lanes_recovered_above_stated_size` pins 7 pp).

## Pressing: PPDA, ball-won height and press intensity

CAL is the planted high-press team. On the v2 small league (seed 2026):

| Team | PPDA | press_intensity | ball-won height |
|---|---|---|---|
| CAL | 10.2 | 0.274 | 44.6 |
| VES | 13.9 | 0.168 | 40.6 |
| AUR | 14.6 | 0.137 | 39.9 |
| HAR | 16.0 | 0.149 | 41.9 |
| NTG | 18.9 | 0.094 | 36.7 |

In v1 PPDA put CAL level with VES and ball-won height put it below AUR. With realistic failed-pass
outcomes, fouls counted as defensive actions and only won tackles in ball-won height, all three now
single out CAL. The `ppda_alone` rule stays: PPDA still depends on where the opponent chooses to
play, and press_intensity (pressure events per opponent pass) is the direct measure of the behaviour.

## Step 4 metrics on the planted traps

- Volume passer NTG_07: pass_quality_ratio 0.19 (league 1.0); the other top-25 forward passers range
  0.27-2.28. His forward passes go into the channel, not into high-threat central cells.
- Corner specialist NTG_11: open-play xA per chance created 0.035, second lowest of the 20 players with
  15+ chances (median about 0.07); his set-piece xA (1.67) exceeds his open-play xA (1.27).

## Verifier

`verify(claim, ds)` returns a copy with `verification` filled in; `verdict` gives the same as a
dataclass with the per-rule details.

Fact check (on the claim object only):
1. evidence_event_ids non-empty and all known, else **missing_evidence**;
2. each evidence event satisfies the metric's evidence predicate (e.g. a field tilt claim's evidence
   are the subject's completed final-third passes) and lies inside the claim's match/window, else
   **missing_evidence**;
3. value.amount and every supporting_values entry recomputed from scope + subject + params within half
   the last rounding step, else **value_mismatch**;
4. every number in params equals value.amount or a supporting value, else **value_mismatch**.

Context rules (one module each in `engine/rules/`, thresholds documented in the module):

| rule | applies to | fires when | action, context_note |
|---|---|---|---|
| causal_claim | claim_type causal | always | block, causal.not_supported_by_event_data |
| causal_red_card | a claim mentioning a red card (metric, template_key or params) | it is causal (claim_type causal, or template_key with caused/because/due_to/cost) | block, red_card.descriptive_only |
| single_match_fatigue | fatigue.* on a match/window scope | always | block, fatigue.single_match_not_supported |
| field_tilt_with_lead | field_tilt / territorial_stress, team, match/window | tilt >= 60%, trailing for >= 50% of its final-third passes, box entries while trailing <= 18% of its final-third passes while trailing, and chance xG (shots > 0.08) no more than the league's 75th percentile of chasers for that scope length | context, field_tilt.trailing_vs_deep_block |
| shot_spam | xg / npxg, team | >= 12 non-penalty shots, >= 65% of them with xG <= 0.08, their mean <= 0.08 | context, xg.volume_of_low_quality_shots |
| set_piece_inflation | chances_created | >= 4 chances, >= 50% from set pieces | context, chances_created.mostly_set_pieces |
| wide_forward_passes | forward_passes, player | >= 15, >= 70% wide, pass_quality_ratio <= 0.5 | context, forward_passes.wide_low_threat |
| small_sample_xg | xg / npxg, match/window | < 8 shots | context, xg.small_sample |
| ppda_alone | ppda | press_intensity not in supporting_values | context, ppda.read_with_press_intensity |

A fired **context** rule also names the params the sentence must carry (`REQUIRES`): field_tilt_with_lead
box_entries; shot_spam shots and xg_per_shot; set_piece_inflation open_play; wide_forward_passes
pass_quality_ratio; small_sample_xg shots; ppda_alone press_intensity. With them in params the claim
is `published_with_context`; without them it is `blocked` and `verification.revision_hint` lists
the missing params (the Analyst's revision loop, docs/ARCHITECTURE.md).

Full-league precision/recall: v1 in docs/PROGRESS.md (Step 5); for the match-level rules on five
v2 full leagues, with every miss classified, docs/verifier-recall.md (`python -m tools.verifier_recall`).
On a full-match claim per team every rule fires on <= 6% of non-trap cases (the slow test allows 10%).

### Reading the field tilt caveat: two false-fire measures

`field_tilt_with_lead` is scored two ways, and they answer different questions.

- **Unplanted fire rate**: the share of (match, team) cases whose opponent is not a planted sit-deep
  team on which the rule fires. It measures how specific the rule is to the plant, not whether
  the caveat was wrong. Every generated team drops deeper when it leads (sit_deep 0.15-0.53 outside
  the plants), so a chaser circulating around a block with few box entries is a real pattern on
  unplanted teams too. In the Analyst pipeline the rate is high (16-19% of cases across the rule
  versions in docs/verifier-recall.md, 16.0% now) because the Analyst proposes a field tilt claim
  for every 30-minute window above 60% tilt, several per match, and one fire per match is enough.
  On one full-match claim per team it is 3.2% now (2.7-3.5% by seed group).
- **Outcome-based precision**: independent of the rule's inputs (which are passes). For each fire,
  the chaser's non-penalty xG in the claim's scope is compared with what an average side makes in
  the same time in the same game states (`metrics.chaser_threat`: league npxG per second while
  leading / level / trailing). A fire is *justified* at or below that average (territory without
  threat, which is what the caveat says), a *false positive* above the league's 75th percentile
  of that ratio for scopes of the same length in which the subject trailed at least half the time
  (`metrics.chaser_threat_line`), and *unclear* in between.

On the five leagues (docs/verifier-recall.md), before the threat condition, 576 of 3230 unplanted
cases (17.8%) drew a pipeline fire: 355 justified (11.0% of all cases), 92 unclear (2.8%) and 129
real false positives (4.0%). The rule now also requires that the chaser did not clearly
out-create an average chaser from real chances (shots above the 0.08 low-xG line, against the
league's 75th percentile line). Speculative shots are left out on purpose: twenty 0.05 shots make
1.0 xG without making a side dangerous, and a chaser circulating around a deep block shoots from
range. Counting them, the showcase's NTG (a shot-spam chaser) would read as a threat (1.12x the
average against a 1.03x line) and the planted caveat would be suppressed; from real chances it
made 0.59x. After the change the pipeline fires on 516 of 3230 unplanted cases (16.0%), of which
17 (0.5% of all cases) are false positives by the total-xG label. Because the rule now uses the
chance-xG line itself, the chance-xG label is no longer an independent check (it shows 0 by
construction); the total-xG label still is. Split the same way, the 16.0% is 12.8% justified,
2.7% unclear and 0.5% real false positives (before: 11.0%, 2.8%, 4.0%).

The cost is recall on planted cases where the chaser did create real chances. The changes,
including the 75th-percentile threat line, were chosen on the tuning seeds 2026-2028, and seeds
2029-2030 are a hold-out, so the hold-out figures are the ones to quote:

| field_tilt_with_lead recall, true cases | tuning 2026-2028 | hold-out 2029-2030 |
|---|---|---|
| one full-match claim per team | 0.62 [0.49-0.73], n=60 | 0.42 [0.29-0.57], n=45 |
| Analyst pipeline (what users see) | 0.90 [0.80-0.95], n=60 | 0.82 [0.69-0.91], n=45 |

The two levels differ because the pipeline proposes a field tilt claim for every 30-minute window
above 60% tilt, several per match, and a case is caught when any of them fires, so a window the
rule misses is often caught by a neighbour. A full-match claim has one chance; its box-entry and
threat figures are averaged over the whole match; and the league's threat line is tighter for full
matches than for 30-minute windows (1.06-1.09 against 1.29-1.37 on the five leagues). Full-match
recall is a weak spot: it is lower than before these changes (0.70 pooled), and the cases it drops
are full matches in which a chaser of a deep block still beat the league's 75th percentile from
real chances, where "territory, not threat" would mislead.

## Known gaps

- The soft-lane table above is from v1. In v2, with the own-lanes gate, the small league finds NTG's
  left flank on 8 of 8 seeds checked and HAR's right flank on 7 of 8, with no unplanted lane flagged.
