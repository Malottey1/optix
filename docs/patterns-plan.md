# Tactical patterns: plan and audit

Step 1 of the pattern library. For each pattern: BUILD (new detector), ADAPT (built on an existing
engine metric) or SKIP; the event fields it reads; its thresholds (engine/patterns/config.py, the
values after tuning); the natural base rate measured on one league before any planting; the naive
claim it tests and the Verifier rule that does it; the card visual and icon; and whether planting
was needed. Measured recovery is in docs/pattern-recall.md; the user-facing summary in
docs/patterns.md.

All zones are from the attacker's point of view (x 0-100 toward the opponent goal, y 0-100 from
the attacker's left). Sides: left y < 40, right y >= 60; outer strip y < 15 or > 85; central lane
40 <= y < 60; apex x 82-92, y 38-62; goal-line wide x >= 94 and y <= 25 or >= 75; middle third
x 33-67. A loss is the opponent's possession_change; its x in the loser's frame is 100 - x.

Base rates: share of the 760 team-matches of the seed 2026 full league (20 teams, 380 matches,
nothing planted) with a finding, with the thresholds as first written (before tuning).

## Tier 1

| Pattern | Decision | Fields | Thresholds (config) | Base rate | Naive claim -> rule | Visual, icon | Planted |
|---|---|---|---|---|---|---|---|
| P1 Bait and switch (`pat_bait_switch`) | BUILD | pass x/y start and end, pass_distance_m, outcome, possession_id, shots | >= 15 short passes (<= 20 m), >= 70% on one side; switch within 2 actions, >= 25 m and >= 40 across; shot or box entry within 3 actions | 0% | "attacks mostly down the left" (attack_side_share) -> `ctx_attack_side_vs_finish_side` (context) | switch arrows; pattern-bait-switch | yes (AUR) |
| P2 Cut-back (`pat_cutback`) | BUILD | pass ends, pass_type, shots, xG | delivery to the goal-line wide zone, pass back >= 5 x units into the apex within 2 actions, shot within 2 | 6.4% | "N crosses" (crosses) -> `ctx_crosses_vs_cutbacks` (context) | pass arrows; pattern-cutback | yes (VES) |
| P3 Flank isolation (`pat_flank_isolation`) | BUILD | completed passes, y start and end, possession_id, shots | 10 consecutive completed passes in one possession, >= 75% both ends in one outer strip, none ending central; overlaps merged | 0% | "N final-third passes" (final_third_passes) -> `ctx_volume_without_central_access` (context) | pass-route arrows; pattern-flank-isolation | yes (NTG, VES left) |
| P4 Elastic low block (`pat_elastic_low_block`) | ADAPT (field tilt, momentum) | passes in the final third, shots and xG, blocks and clearances, engine momentum | 15-minute windows every 5: opponent tilt >= 65%, >= 2 opponent shots, >= 70% from outside the box, xG per shot below the league median, blocks + clearances above the league 75th percentile, momentum <= 50; spell >= 15 minutes | 2.8% | "N% field tilt" (field_tilt) -> `ctx_tilt_without_access` (context; stands down when `field_tilt_with_lead` fires) | the other side's shot blocks in the window; pattern-elastic-low-block | yes (AUR) |
| P5 Counter-press (`pat_counter_press`) | BUILD | possession_change x, pressure events, clock | loss at x >= 66.7, regain within 4 s with >= 2 pressures in the opponent's third; >= 2 regains and >= 1.5x the league rate | 0% | "lost the ball N times in the final third" (final_third_losses) -> `ctx_losses_vs_immediate_regain` (context) | route nodes; pattern-counter-press | yes (CAL) |
| P6 Rest defence (`pat_rest_defence`) | ADAPT (field tilt) | possession_change x, shots, xG, final-third passes | team tilt >= 60% (match or a 30-minute window), opponent shot within 10 s of winning the ball in its own half, >= 2 such shots | 2.0% | "N% field tilt" (field_tilt) -> `ctx_dominance_with_transition_exposure` (context; stands down when `field_tilt_with_lead` fires) | route nodes; pattern-rest-defence | yes (NTG) |
| P7 Starved finisher (`pat_starved_finisher`, player) | BUILD | touches (pass, carry, dribble, shot, duel), under_pressure, xG, position | forward; touches at or below the position's 25th percentile or <= 15; >= 2 unpressured shots; xG per touch >= 5x the position median; xG >= 0.25; full match only | 9.2% | "quiet game: N touches" (player_touches) -> `ctx_low_volume_high_quality` (block, never revised) | route nodes, Player Deck chip; pattern-starved-finisher | yes (VES striker) |
| P8 Fouls after losses (`pat_tactical_fouling`) | BUILD | fouls, possession_change x, clock | foul within 5 s of a loss in the middle third; >= 3 such fouls and >= 2.5x the league rate per middle-third loss | 25.1% | "N fouls" (fouls) -> `ctx_fouls_clustered_after_losses` (context) | route nodes; pattern-tactical-fouling | yes (CAL) |

The family id `pat_tactical_fouling` is kept; every user-facing word is observational ("fouls after
losing the ball").

## Tier 2

Not built in this pass (time went to Tier 1 measurement and the Verifier loop). Each would follow
the same Definition of Done. Icons to reuse when built: P9 metric-territorial-stress, P10
style-wing-play, P11 style-high-press, P12 pass, P13 pressure, P14 players, P15 corner, P16
pressure, P17 style-direct-play.

| Pattern | Decision |
|---|---|
| P9 Sustained box pinning | not built |
| P10 Controlled funneling | not built |
| P11 Pressed presser | not built |
| P12 Third-man wall pass | not built |
| P13 Press trap (turnovers after short passes into a wide zone) | not built |
| P14 Restless rotation (player) | not built |
| P15 Set-piece dependence | not built |
| P16 Press-resistant passer (player) | not built |
| P17 Direct transition spike | not built |

## Skipped

| Pattern | Why |
|---|---|
| False nine vacuum | its core, a centre-back drawn out of line, needs player positions off the ball; event data has none |
| Mid-block passivity | claims about a block's shape are not observable in event data; the observable part overlaps P4 |

## Planting

The detectors were first run on unplanted leagues; P1, P3 and P5 had a base rate of about 0 (the
simulator rarely produces 15 short passes in a row, long touchline circulation or two pressures
within 4 s), so their recall can only be tested on planted motifs. The others are planted at
signature strength on the assigned teams. Each motif has its own random stream per match and team;
with every propensity at zero the generator output is byte-identical to the pre-patterns generator
(tests/test_motifs.py). Planted teams and strengths are in each ground_truth.json (`planted_motifs`).
