# Progress log

## Realism v2 (branch `realism-v2`, from `overnight`; tag `pre-realism-v2`)

Started 2026-10-21 18:24.

### Stage 0. Housekeeping
- (a) docs/realism-audit.md rewritten: only our own measurements, public-source ranges (with URLs)
  and ranges marked "approximate". No third-party event data, numbers derived from it, or scripts
  that fetch it remain in the repo or the working tree.
- (b) data_gen/calibration.py: 47 range targets for the recent era (2022/23-2024/25), each with a
  source note and a per-observation SD for a sampling allowance (2 sd / sqrt(n)). The 38/30/32
  outcome point target is replaced by ranges (home 40-49%, draw 20-28%, away 28-36%).
  `NOT_YET_MODELLED` lists the 27 targets the v1 generator misses on the full league (plus goal
  dispersion, missed on the pooled small seasons); later stages remove entries.
- Tests: 122 passed by default.

### Stages 1-6. Fixtures, squads, the ball, chances, dead balls, league structure
Committed as one stage (see Decisions). Summary:
- Stage 1, fixtures: `data_gen/schedule.py`. Circle method, Berger home/away alternation, the second
  half of the season mirrored, at most 2 home or 2 away in a row, weekend slots from 15 Aug 2026 to
  22 May 2027, international breaks and two midweek rounds. The small league plays the 5-team double
  round robin twice (40 matches). tests/test_schedule.py.
- Stage 2, squads: `data_gen/squads.py`. 24-player squads (formation XI + 2 GK, 4 DF, 4 MF, 3 FW),
  formations by style (4-3-3, 4-2-3-1, 4-4-2, 3-5-2, 4-1-4-1), a unique name pool per league,
  `lineups.csv`, 2-5 substitutions per team (mostly 55-85', earlier when trailing or after a red),
  minutes played, a one-match ban after a red or a fifth yellow, light rotation after short rest,
  injuries with forced subs. Trap players and goalkeepers are never rested or subbed off for tactics.
- Stage 3, the ball: failed passes end as interceptions, out of play, blocks, tackles on reception,
  clearances or loose balls; duels, carries, dribbles, clearances and blocks; goal kicks, throw-ins,
  build-up from the goalkeeper and centre-backs; back passes and pass lengths in range; position
  continuity with a teleport guard (reach 6 + 8 m/s); style drives volume; PPDA in range.
- Stage 4, chances: headers, shots in the box, on target, distance, penalties, set-piece goals and
  cross completion in range; goalkeeper saves and claims; xG refitted per bin.
- Stage 5, dead balls and time: fouls, cards (a booked player is more careful), offsides, red cards
  change behaviour (the side down a player defends deeper), stoppage time from stoppages, ball in
  play, goal timing rising late in each half. Contracts unchanged (the new event types already fit).
- Stage 6, league: bounded, correlated dials from a quality score; PLQ and LMF defy their strength;
  champion and bottom points in range; correlation signs as targets.
- Calibration: every target passes on the small league (seed 2026 and seeds 1-5 pooled) and on the
  full league (seeds 2026 and 7). `NOT_YET_MODELLED` is empty.
- Verifier retune on the v2 full league (seed 2026, 1345 cases): shot_spam >= 12 shots, >= 65% low xG,
  mean <= 0.08 (recall 0.40 -> 0.52, non-trap rate 3.3% -> 4.8%); field_tilt_with_lead entry cap
  15% -> 18% (recall 0.64 -> 0.79, non-trap rate 1.1% -> 3.6%). Recall moved by up to 0.15 between
  simulator builds during tuning (25-30 positives per rule), so the test floors sit about one SD below.
- Showcase: seed 20260957 (958 tries), AUR 2-1 NOR (goals 18', 47', 78'); every trap fires with
  margin >= 10%.

### Stage 7-8 (partial). Realism tests, report, downstream repair
- tests/test_realism.py: 14 default tests on the small league (every range, fixtures, lineups,
  players on the pitch, 11 v 10 after a red, subs match lineups, minutes add up, bans, no player
  teleports, ball continuity, restart spots, referential integrity, unique names, determinism) and
  6 slow ones on the full league (the same checks plus xG by bin, goals variance/mean, late goals,
  correlation signs including press vs PPDA). tools/realism_report.py writes docs/realism-report.md
  (with a v1 column from docs/realism-v1-measured.json). Every target is in range on both leagues.
- Generator bugs found by these tests and fixed: a player substituted at a dead ball could take the
  free kick; kick-offs could start with a dribble; keepers' last position was dropped after a pass
  (no reach check); keeper saves and claims at a fixed spot could be out of reach (now pulled
  within reach, using no random numbers); injuries were logged at the centre spot; dribble, tackle
  and carry events lost the sequence's play pattern.
- goals_dispersion sampling SD 1.0 -> 1.41 (the variance/mean ratio of n Poisson counts has SD about
  sqrt(2/n)); the slow test still requires 0.95-1.3 on the full league with no allowance.
- Soft-lane own-lanes gate now compares lifts over each lane's league rate (lanes have different
  baselines); NOR found on 8/8 seeds, HAR 7/8, no false positives.
- Engine: PPDA counts fouls (standard definition); ball-won height counts won tackles only.
- Showcase now seed 20261383 (1384 tries), AUR 4-1 NOR, all margins >= 10%.
- Test changes: test_data_gen attacking-output clone test 30 -> 100 matches a side (30 was
  underpowered; true ratio about 1.8); test_dashboard reads the final score from ground truth
  instead of a literal "2 – 1".
- Docs: data-dictionary.md, engine.md and ARCHITECTURE.md updated for v2.
- NOT DONE yet: refresh docs/screens/ (python -m tools.check_dashboard after agents.run_match;
  the slow dashboard test passes), the final summary at the top of this file with the before/after
  table (docs/realism-report.md has it), and the "Needs human review" list: the champion's points
  vary 77-95 across seeds; the small-league CAL control's minimum entry share is close to its 15%
  gate on some seeds; the Verifier's recall moved by up to 0.15 between builds.

### Decisions (realism v2)
- Era for "realistic": recent seasons 2022/23-2024/25 as instructed; where those seasons differ a lot
  (goals 2.85-3.28, yellows 3.4-5.1) the range spans them.
- Sampling allowance instead of separate small/full tolerances: one range per target, widened by
  2 sd / sqrt(n) for the sample size actually measured.
- Season-shape targets (correlations across teams, points of champion and bottom team, possession SD,
  pass-volume spread, players used) apply only to the 20-team league (`min_teams`).

- Stage 1 committed together with Stages 2-6: the v1 small-league recovery tests pass only on the
  old fixture draw, so the new calendar and the rewritten simulator had to land together for the
  suite to be green at each commit.
- Field tilt spell length: `traps.FIELD_TILT_MIN_F3` 100 -> 60 final-third passes. With realistic
  final-third volume (about a quarter of passes), 100 passes in a leading spell is rare even for a
  dominant chaser; 60 keeps the trap clear of noise.
- NOR's weak lane is planted at strength 1.5 (`weak_strength`) and opponents aim at a known soft side
  (near side only); after a completed entry into the weak lane, box passes and shot appetite rise
  slightly (`via_weak`). The soft-lane truth helper formula (0.09 x strength) is unchanged.
- The flank trap's completion check compares against the season reference completion for that lane,
  not only the other end of the same match (one match is too small a sample).
- CAL dials raised (att 1.08, dfn 1.06, press 0.90, directness 0.58, attacking output 1.25) so the
  negative control "dominant, not a tilt trap" is neither vacuous nor failing: at output 1.10 CAL's
  box-entry share in its level-or-ahead high-tilt spells ranged 0.09-0.27 over 8 seeds (half the
  seeds had a spell under the 15% gate); now 0.15-0.36 on all 8.
- Result shape: CHASE_URGENCY 0.8 -> 0.5 and SHOT_RATE_BOX 0.135 -> 0.14. A strong trailing-side
  urgency fed equalisers, so draws ran at 31-33% on the full league. Raising shot volume alone
  pushed small-league shots per team over range. Checked on full seeds 2026 and 7 and the small
  league (seed 2026 and seeds 1-5 pooled).
- Soft-lane own-lanes gate z 1.64 -> 2.33 (one-sided 5%, Bonferroni for 5 lanes): AUR's
  left_half_space was flagged on seeds 2 and 2026 (z 1.69, 2.23); every planted lane that 1.64
  found has z >= 2.75 across 8 seeds.
- Half-time summaries fire on the first-half `half_end` event (after stoppage time), not at 2700 s.
- The dashboard shows football time from the timeline's new `periods` (45+3, 90+6); the scrub runs
  to the last event. The evidence drawer shows `related_player_id` (fouled player, player on).
- Momentum payload series is cut at the claim's window end (a long stoppage could put the
  triggering event a minute later, so the series' last point disagreed with the claim).
- Volume passer usage 1.4 (was higher): at the old usage the passer led the league by an implausible
  margin.
- Showcase realism envelope: the search also requires <= 30 shots per team, <= 6 goals and >= 250
  passes per team; NOR's left winger gets delivery 1.4 in the showcase only.
- Soft-lane rule: the lane must also beat the team's own other lanes (two-proportion z >= 1.64), and
  the minimum gap fell 6 -> 4 pp. Without the own-lanes gate, a deep block made every lane look soft
  against AUR.
- New play patterns `throw_in` and `goal_kick`, new shot types `penalty` and `free_kick`; the
  `related_player_id` column carries the player fouled, the player coming on and the duel opponent.
- New template `matchup.weak_lane` (en/es/fr): the top matchup can now be a half-space, not a flank.
- Verifier thresholds retuned on the full league (numbers in the stage note). Lower precision is
  accepted: non-trap fires are real low-quality volume or real trailing territory, still true context.

### Test changes (realism v2)
- test_data_gen.py `test_season_meets_calibration_targets`, test_full_league.py
  `test_full_league_meets_calibration`: targets are now ranges with an allowance; the tests allow
  failures only from `calibration.NOT_YET_MODELLED` (a ratchet; tests/test_realism.py will require
  it empty). Reason: the targets changed (Stage 0b), and v1 cannot meet the new ones until later
  stages.
- `test_ground_truth_records_expected_targets`: expected targets have no point value any more
  (ranges only, never a point), so the "target inside tolerance" check became "lo < hi, source
  recorded".
- `test_calibration_is_not_a_lucky_seed` (slow): pools five other seeds' seasons (200 matches) and
  checks the same targets, instead of "mean within a band around the point target" (no point targets
  any more). It now builds the seasons without the showcase search, which made it take 6 minutes.

- test_data_gen.py `test_shape`: 120 players, 24 per team, unique names (squads are now 24, Stage 2).
- test_data_gen.py `test_events_are_clean`: the last clock is between 5400 and 5400 + 1200 s and the
  half_end periods are 1 and 2 (stoppage time now runs past 90:00).
- test_data_gen.py `test_field_tilt_does_not_fire_on_cal_dominance`: CAL only, with a 40-pass spell
  floor stated in the test (the trap default fell to 60, see Decisions).
- test_data_gen.py season firings test uses `traps.FIELD_TILT_MIN_F3` instead of a literal 100.
- test_engine.py: the second-half partition window is (2700, end of match) instead of (2700, 5400)
  (stoppage time); matchup confidence is recomputed as the minimum of the share and completion
  confidences and must be medium or high.
- test_full_league.py: `RECOVERABLE_EFFECT_PP` 7.0 (power reasoning in the comment, realistic
  final-third volume halves the sample); total events between 650k and 1M (richer event types).
- test_stream.py: insights start no later than the last event (stoppage time), not 5400.
- test_verifier.py `test_honest_claim_passes_and_verified_claim_validates`: AUR has six shots in the
  v2 showcase, so `small_sample_xg` rightly fires on its match xG; the honest claim is now AUR's
  season xG on the season data.
- test_verifier.py `test_field_tilt_rule_silent_on_high_territory_with_box_entries`: the "above the
  entry cap" filter uses the rule constant instead of a literal 15 (cap retuned to 18%).
- test_verifier_full.py `MIN_MATCH_RECALL`: shot_spam 0.40 -> 0.42, field_tilt_with_lead 0.45 -> 0.65,
  about one sampling SD below the retuned measurement (0.52, 0.79). A raise, not a weakening.
- test_agents.py `test_raw_field_tilt_claim_blocked_then_republished_with_context`: picks NOR's first
  tilt claim after AUR's first goal instead of NOR's first tilt claim. In the v2 showcase NOR's first
  claim covers 0-15' at 0-0, which is honest and published as is; the test now also asserts that.
- Calibration tests: `NOT_YET_MODELLED` is now empty, so they require every target.

## Overnight run (steps 0-10)

Branch: `overnight`. Started 2026-10-21 07:08 local, finished about 08:30. Steps 0-10 all done.
Nothing was cut from the priority list.

## Summary

**Built**
- Data: a 10%-margin showcase (smallest margin +12.1%), LF CSVs and a slow marker (step 0); a 20-team,
  380-match full league (682k events, about 17 s) with extra planted traps and their expected
  evidence. The small league stays byte-identical (step 2).
- Contracts: claim `scope`, `supporting_values`, interval / effect_pp / confidence / baseline_source,
  `check_param_numbers` (step 1), and `verification.revision_hint` (step 6).
- Engine: effect sizes with Wilson intervals and confidence labels (z only for ranking), soft lanes
  from conceded completion rate, season baselines for single matches, and a HAR diagnosis (true
  effect 7.3-9.0 pp, recovered on the full league; the stated recoverable size is 5 pp, with 7/7
  recovered and 0/12 false positives) (step 3). Also xT (12x8), pass quality, xA split,
  territorial stress, shot clusters, rhythm, momentum and milestones (step 4).
- Verifier (step 5): fact check that recomputes value and supporting values from the claim object
  and checks each evidence event; 9 context rules. On the full league every rule fires on 5% or
  fewer of non-trap cases. Corner specialist and volume passer recall is 4/4 each. Match-level
  recall is 0.46 for shot spam and 0.54 for field tilt, counting only matches where the trap's
  game state occurred.
- Agents (step 6): Ingest, Analyst, Verifier, Narrative, Personalization, an orchestrator, typed
  messages, a per-match state store and structured logs. Blocked claims are revised by rule and
  re-verified with attempt numbers.
- Insight stream (step 7): `python -m agents.run_match`. The showcase gives 34 insights, 12 blocked
  attempts revised, 0 dropped. Latency: median 4 ms, max 25 ms.
- Translation and personalization (step 8): hand-written es/fr for all 16 templates; a number
  guard per language (decimal comma); analyst/casual, favorite club, player focus, single metric.
- Dashboard (step 9): a static app/ with feed, evidence drawer, Focus Pitch, momentum tug-of-war,
  Perimeter Lock, standard vs honest stat, the blocked-then-rewritten strip, 3 languages,
  light/dark and reduced motion. Headless Chromium checks show 0 console errors on 8 views;
  screenshots are in docs/screens/.
- Docs and hardening (step 10): ARCHITECTURE.md (Mermaid diagram, roles, data flow, handoffs,
  requirement->code table), README with a 5-command quick start, dashboard.md. A clean clone in a
  fresh venv ran the 5 commands, the tests passed (122 passed, 1 module skipped without
  Playwright) and the dashboard checks were clean.
- Tests: 122 by default plus 12 slow, all passing (slow suite 3.5 minutes).

**Incomplete / not built**
- Cut-list items were not built as features: red card segment analysis, underperformance
  diagnosis, fatigue proxy, pounce events, ingest noise cleanup beyond dedup and missing fields.
  Their Verifier rules exist (causal_red_card, single_match_fatigue block such claims). The
  insight types red_card_segment, pounce_sequence, underperformance_stack and turning_point are
  never emitted.
- Shot clusters and territorial stress can be claimed and verified, but the Analyst has no trigger
  for them yet.
- npxG equals xG: the generator has no penalties.
- Azure deployment (build order 6) was outside this run.

**Decisions**: see "Decisions" below (every one is listed there, grouped by step).
**Needs human review**: see the section at the end (4 items).

## Steps

### Step 0. Housekeeping
- (a) CSVs are now written with `lineterminator="\n"`; regenerated; `git add` shows no CRLF warnings.
- (b) Showcase trap margins are computed by `data_gen.traps.trap_margins` and stored in
  `ground_truth.json` (`showcase.trap_margins`). Before: two thresholds were within 10%
  (spam low-xG share 0.769 vs 0.75, +2.6%; volume-passer wide share 0.86 vs 0.80, +7.5%).
  The seed search now requires every threshold cleared by >= 10% (`SHOWCASE_MIN_MARGIN`).
  New showcase: seed 20264547, AUR 2-1 NOR. Numbers: chaser tilt 0.762 (>=0.68, +12%), box
  entries 14 of 147 final-third passes (share 0.095 <= 0.15), 16 of 19 NOR shots low-xG (share
  0.842, mean xG 0.058), volume passer rank 1 with wide share 0.925, corner specialist 6 corner
  chances vs 0 open play, AUR left share 0.613 of 31 entries. Smallest margin +12.1%.
- (c) `@pytest.mark.slow` registered in pyproject.toml, deselected by default (`addopts = -m 'not slow'`).
  Run them with `pytest -m slow`, or everything with `pytest -m ""`.
- Tests: 41 passed, 2 slow deselected (both slow pass).

### Step 1. Contracts
- claim.schema.json: `scope` (season/match/window, required); `window` and a string `match_id` are
  required only for match/window (if/then); `supporting_values`; `value.interval`, `value.effect_pp`,
  `value.confidence`, `value.baseline_source`; `z_score` optional and documented as ranking-only.
- `contracts/checks.py: check_param_numbers()` enforces "every number in params equals value.amount or a
  supporting_values entry". Tests: a param number found nowhere is rejected; strings/bools ignored.
- Examples updated. The insight example's casual text dropped the number 1 (it said "once"), which the
  number guard would reject; rewritten so every numeric param appears in every rendering (new test).
- engine/matchup emits the new shape: scope season, no window, Wilson interval, effect_pp, confidence,
  supporting_values. Matchup ranking switched from summed z to summed percentage-point lift (z only
  breaks ties). Report shows shares with 95% CIs, pp lifts and confidence.
- Tests: 51 passed, 2 slow deselected.

### Step 2. 20-team league
- `--league small|full`. small is byte-identical to before (checked by sha1 on all 7 season files and
  all 7 showcase files). full: 20 teams, 380 matches, 682,215 events, 102 MB (events.csv 77 MB,
  passes.csv 30 MB), generated in 16-18 s.
- New `TeamSpec` fields with defaults (`weak_strength=1.0`, `archetype=""`) so the 5 teams are unchanged.
- Calibration on the full league, first run without tuning: home/draw/away 41.3/26.1/32.6%, 2.81 goals,
  65.5% one-goal-or-less, 24.3 shots, 10.4 corners. All inside tolerance.
- Engine: `tables.team_events()` indexes events by the matches a team played; profiles use it. A full-
  league profile bracket takes ~11 s (it was ~130 s before the index).
- Slow test `tests/test_full_league.py` (6 tests, ~60 s): totals and schedule, calibration, originals
  unchanged, fictional names, every archetype signal, every player trap, every team trap.
- Tests: 51 passed by default; slow: 8 (all pass).

### Step 3. Engine statistics
- Every profile comparison now has effect (pp for shares, units for means), 95% interval (Wilson /
  normal), confidence and n; z kept as an internal ranking signal only. Rationale in docs/engine.md.
- New metric `entry_completion_by_lane` (conceded entry completion rate by lane). `profiles.soft_lane()`
  uses it: largest lift >= 6 pp with the Wilson lower bound above the league rate.
- Matchup = attacker share lift + defender completion lift (pp). Claim supporting_values gain
  concede_completion, league_completion, completion_effect_pp, completion_attempts.
- HAR diagnosis: true effect of its plant (from the generator's logged success probabilities) is
  7.3-9.0 pp, the same as NOR's. Share missed it (opponents' lane habits swamp it); completion rate
  finds it on the full league (+7.2 pp, n=505) but not on the 40-match season (n=186, interval about
  +-6 pp). Stated recoverable size 5 pp: 7/7 recovered on the full league, 0/12 false positives.
- `load(dir, baseline="season", season_dir=...)`: single-match analyses use season baselines; a
  single match with a season baseline yields a scope "match" claim with baseline_source = season n.
  `engine.report --season-baseline DIR`.
- docs/engine.md explains why ball-won height and PPDA mislead for CAL; the ppda_alone rule refers to it.
- Tests: 54 passed by default; slow 10.

### Step 4. Remaining metrics
- engine/threat.py: xT grid (12x8, value = xG that possessions from a cell go on to produce, fitted on
  the baseline season, sparse cells borrow their column mean), xt_added per completed pass,
  pass_quality_ratio, threat_passes.
- engine/flow.py: xa_split, territorial_stress, shot_clusters, rhythm (15-value series), momentum,
  milestones (first goal in the dataset, 25/50/75/100 completed passes in a match).
- tests/test_engine_fixtures.py: every metric (old and new) on hand-built events with hand-worked
  answers, plus trap checks: NOR_07 pass_quality_ratio 0.19 (< 0.35), NOR_11 open-play xA per chance
  < 0.6 x league median.
- Bug found by a fixture and fixed: high_threat_cells counted every cell tied at the 75th-percentile
  cut, so a mostly-zero grid made every central cell "high threat".
- Tests: 70 passed by default; slow 10.

### Step 5. Verifier
- engine/claims.py: per-metric recompute registry (`compute`) and `build_claim` (pending claim objects
  with value, supporting_values, evidence, scope, game state). The Verifier and the Analyst share it.
- engine/verifier.py: fact check (evidence exists, each ID satisfies the metric definition and lies in
  scope, value and every supporting value recomputed within half a rounding step, params numbers
  backed) then context check (engine/rules/, 9 modules). Status published / published_with_context /
  blocked, rule_ids, context_note key, attempt number.
- matchup_claim now carries `defender_id` so the Verifier can recompute it.
- tests/test_verifier.py (20 tests): honest, tampered amount, tampered supporting value, unbacked param
  number, unknown, wrong-team and out-of-window evidence; every rule fires where the showcase plants
  it; nothing fires on CAL level/ahead windows with tilt >= 60%, on high tilt with box entries > 15%,
  or on CAL's top passer and CAL's shots.
- tests/test_verifier_full.py (slow) on the full league:

  | rule | TP | FN | FP | TN | recall | precision | non-trap fire rate |
  |---|---|---|---|---|---|---|---|
  | shot_spam (match, trap team trailing >= 45 min) | 11 | 13 | 32 | 614 | 0.46 | 0.26 | 5.0% |
  | field_tilt_with_lead (match, vs sit-deep, trailing >= 45 min) | 20 | 17 | 12 | 634 | 0.54 | 0.62 | 1.9% |
  | set_piece_inflation (season, players >= 4 chances) | 4 | 0 | 0 | 195 | 1.00 | 1.00 | 0% |
  | wide_forward_passes (season, players >= 15 fwd passes) | 4 | 0 | 0 | 216 | 1.00 | 1.00 | 0% |

  Every rule is under the 10% non-trap limit, so none was retuned.
- Speed: season player claims went from 0.45 s to 0.1 s (cached league share for pass_quality_ratio,
  evidence scanned from the team's matches only, no in-scope set for season claims).
- Tests: 90 passed by default; slow 11.

### Step 6. Agents
- agents/: messages.py (typed handoffs), state.py (per-match MatchState with rolling counters and a
  view of ingested events), log.py (structured JSON logs), ingest.py, analyst.py, verifier_agent.py,
  narrative.py + templates/en.json (analyst and casual per template_key), personalization.py,
  orchestrator.py. Handoffs documented in docs/ARCHITECTURE.md.
- Context rules now declare REQUIRES; a fired context rule whose params are missing blocks the claim
  with `verification.revision_hint` (contract change: schema, docs/contracts.md, test). The Analyst
  revises by rule and re-verifies with attempt + 1.
- Showcase stream: 36 published claims in 0.6 s, none dropped. NOR's raw field tilt claim is blocked
  by field_tilt_with_lead (attempt 1) and republished with context at attempt 2: "NOR hold 65.4% field
  tilt while chasing the game, but only 8 of 70 final-third passes reached the box."
- engine: `metrics.chances_by_player`; rhythm claims carry `minutes`; territorial_stress claims carry
  box_entries.
- tests/test_agents.py (13): ingest dedup/missing fields, stream with duplicates publishes the same,
  blocked -> revised -> published_with_context with the log sequence, every trap's strategy used,
  every published claim schema-valid and backed only by past events, causal dropped, tampered claim
  recomputed, Verifier sees only ingested events, templates contain no hard-coded numbers, number
  guard, personalization modes.
- Tests: 104 passed by default; slow 11.

### Step 7. Insight stream
- agents/insights.py: Published claim -> insight (schema-valid); final insight_type follows what the
  Verifier found (field_tilt_with_lead -> perimeter_lock, shot_spam / wide_forward_passes ->
  volume_vs_value, set_piece_inflation -> set_piece_inflation); context_chip when published_with_context;
  payload numbers only from the claim, points only from evidence events, series from engine.flow.
- agents/stream.py: InsightStream feeds one event at a time and measures latency from receiving the
  triggering event to the built insight. Pre-match work (season preview, baselines) runs in prepare().
- `python -m agents.run_match --match m_showcase --out out/insights.jsonl` writes insights.jsonl,
  claims.jsonl (every attempt, for the blocked-then-rewritten view) and agent_log.jsonl. out/ is
  git-ignored.
- Showcase: 34 insights, 12 blocked attempts revised, 0 dropped; latency median 4 ms, max 25 ms;
  slowest single event 16 ms.
- tests/test_stream.py (7): schema, order, chip iff with-context, numbers and points traced to the
  claim, planted traps reach the stream, latency < 1 s, runner outputs.
- Tests: 111 passed by default; slow 11.

### Step 8. Translation and personalization
- Hand-written Spanish and French for all 16 template keys (both tones), agents/templates/es.json and
  fr.json, plus translated lane labels (`_labels`). Rendering happens in the Narrative agent, only for
  verified claims, for every configured language.
- Number guard per language: numbers are written in the language's own form (decimal comma in es/fr)
  and every numeric param must appear in every rendered string, with no other number allowed.
- Personalization modes: analyst/casual, language (falls back to en), favorite club (marked and first
  at the same clock), player focus, single metric. CLI: `python -m agents.personalize --mode casual
  --lang es --player NOR_07`.
- Same moment, two tones (45:00, NOR trailing):
  - analyst: "NOR hold 65.4% field tilt while chasing the game, but only 8 of 70 final-third passes
    reached the box."
  - casual: "NOR have the ball up the pitch (65.4% of final-third passes) but just 8 of 70 got into
    the box."
  - casual, fr: "NOR a le ballon haut (65,4 % des passes dans le dernier tiers), mais seulement 8 sur
    70 sont entrées dans la surface."
- tests/test_translation.py (11): same keys and placeholders in all languages, every rendered string in
  the showcase stream passes the guard in its language, decimal comma and labels, the guard catches a
  changed number, no translation before verification, each personalization mode, CLI.
- Tests: 122 passed by default; slow 11.

### Step 9. Dashboard
- app/index.html, style.css, app.js: static, no build tooling. Plays the match on a clock; feed cards
  with badges, evidence drawer with every verification attempt, Focus Pitch SVG, momentum tug-of-war
  with hover, Perimeter Lock, standard vs honest stat, analyst/casual toggle, language selector,
  player focus filter, the blocked-then-rewritten strip on revised cards, light/dark, reduced motion.
- agents.run_match also writes out/timeline.json (teams, players, goals, engine momentum per minute)
  so the page computes nothing.
- engine/claims.py: field tilt evidence lists box entries first (the 15 cited events carry the point;
  before, a 75th-minute perimeter lock cited 15 passes and none of its 6 box entries).
- tools/check_dashboard.py + requirements-ui.txt (Playwright 1.64, cached Chromium build): 8 views, 0
  console errors, no horizontal scroll; screenshots in docs/screens/. Slow test tests/test_dashboard.py.
- docs/dashboard.md.
- Tests: 122 passed by default; slow 12.

### Step 10. Hardening and docs
- docs/ARCHITECTURE.md: Mermaid diagram, agent roles, data flow, handoffs, revision loop,
  requirement->code table. README: 5-command quick start plus optional commands.
- End-to-end from a clean clone (`git clone --branch overnight`, fresh venv, Python 3.13): generate,
  run_match and http.server all worked (every app and data file returned 200); 122 tests passed, and
  the dashboard check passed against the clone. Regenerating left the committed showcase unchanged.
- Full slow suite: 12 passed in 3.5 minutes.

## Decisions
- Showcase seed search starts from a recorded offset (`SHOWCASE_SEARCH_START = {2026: 4547}`) because
  a search from 0 with the 10% margin takes ~2 minutes and every test fixture regenerates the data.
  A slow test re-runs the search from 0 and checks it finds the same seed, so the hint only skips work.
- Slow tests chosen: multi-seed calibration and the search-from-zero check. The determinism test stays
  in the default run because it is the cheapest guard against non-determinism.

- `baseline_source` lives inside `value` (next to `baseline`), not at the claim top level: it
  describes the baseline.
- `match_id` became optional/nullable: a season claim (pre-match preview) is not about one match, but
  may name the match it previews. It stays required for scope match/window.
- Verifier "recompute from the evidence": a season claim's value is an aggregate over hundreds of
  events while evidence_event_ids is a sample (12). So the fact check recomputes value and
  supporting_values from scope + subject + metric over the tables, and checks that every evidence ID
  exists and individually satisfies the claim's definition (e.g. is an AUR final-third entry into the
  claimed lane). Applies to Step 5.
- Confidence labels for a share vs a baseline: high = n >= 200, 95% half-width <= 5 pp and the
  interval excludes the baseline; medium = n >= 50 and the interval excludes the baseline; else low.
  A matchup's confidence is the lower of its two sides.

- Full-league team identities are fixed by `FULL_LEAGUE_TEAM_SEED` (not by --seed), so the same 20 teams
  appear whatever match seed is used.
- `teams.csv` for the full league has 2 extra columns (`weak_strength`, `archetype`); the small league keeps
  its original columns so `small` stays byte-identical.
- Expected evidence written to match what the simulator really does: shot spam is conditioned on trailing
  (it only fires against a deep block); "sits deep when leading" is checked on field tilt only (JPH's press
  drop equals the league's); volume passers are "team's top forward passer, league top 10%".
- HAR (shot_spam 0.5, "shoots early and often") is not listed as a shot-spam trap: its trailing low-xG share
  is at the league's. The shot-spam trap threshold is shot_spam >= 0.6.

- Test change, not weakened: my Step 1 test asserted the AUR-NOR matchup confidence == "high". After
  the defender side switched to completion rate (as Step 3 asks), the correct label is "medium" because
  NOR's left-flank completion sample is 190 attempts (< 200). The assertion now pins "medium" exactly
  and also asserts why (completion attempts < 200 <= attacker n).
- Soft-lane threshold 6 pp (observed lift) with the stated recoverable true effect 5 pp: at 5 pp
  observed, ESF (center, +5.5) and JPH (left_flank, +4.9) would have been false positives on the
  full league.

- xT is a possession-value model (xG produced by the rest of the possession), not the iterative
  Markov xT; it is simpler, needs no transition matrix, and matches the step's description.
- Failed passes get 0 xT added (not minus the start value): losing the ball is reported separately.
- Momentum = 100 x (home - away) / (home + away) of exponentially decayed (half-life 5 min) positive
  xT added plus shot xG.

- Verifier: the fact check recomputes from the claim object's scope, subject and params, never from
  text. A claim may fire several rules; the context_note is the first blocking rule's (else the first
  context rule's). Rule order: blocking rules first.
- Precision/recall cases for match-level rules only count a trap team's match as positive when the
  game state the trap needs happened (trailing >= 45 minutes); other trap-team matches are excluded
  from both counts.
- shot_spam precision is 0.26 at match level, kept: the 32 "false positives" are unplanted teams that
  really did take 10+ shots with >= 75% at xG <= 0.08 in that match, which is exactly what the chip
  says. The non-trap rate (5%) is within the limit.

- Context rules block when the sentence lacks the context (REQUIRES missing) rather than only
  attaching a chip. Reason: the step 6 example ("raw NOR 71% field tilt claim blocked by
  field_tilt_with_lead and republished with a context note") needs a block, and a sentence that
  states the shallow number alone is the misleading thing. A chip alone would leave the headline
  misleading. The step 5 tests now assert both halves (raw -> blocked with hint; with context ->
  published_with_context).
- ppda_alone checks press_intensity in params (what the sentence shows), not supporting_values.
- The Analyst's first attempts are plain on purpose so the revision loop is visible and tested; in
  production it could ask for the context up front, with the same result.
- In-match verification uses the match dataset restricted to ingested events (a new Dataset view
  when events arrived), so caches keyed on the dataset are rebuilt per view; xT grid and league
  pass-quality share are cached on the season baseline, which views share.
- The Analyst's trigger thresholds (tilt >= 60%, xT added >= 0.025, momentum swing >= 40, pass
  milestones 50/75, cooldowns) are editorial choices for a readable feed, documented in analyst.py.

- The season preview (matchup) is computed before kickoff and emitted on the first event; its first
  run at kickoff cost 385 ms, which is pre-match work, not live latency.
- The preview insight's points are season events (its evidence), so the dashboard can draw them
  without loading the season.

- Spanish and French write decimals with a comma ("65,4 %"); the number guard compares numbers in
  each language's written form, so "1.1" in a French sentence counts as a wrong number.
- Translations avoid gendered wording for players (no pronouns), so they hold for any player.

- Dashboard data is read from out/ (git-ignored, regenerated by run_match) rather than committed, so it
  can never drift from the engine; screenshots in docs/screens/ are committed.
- No /opt/pw-browsers here; Playwright 1.64 from requirements-ui.txt used its cached Chromium. The
  checker falls back to /opt/pw-browsers or the local cache if the bundled revision is missing.
- Blocked claims are shown in the UI as structured data (template, rule, needed params), never as a
  rendered sentence: only verified claims are narrated.

## Surprises

- ESF (possession, shot_spam 0.8) shows LOWER low-xG share than the league over all minutes; the spam only
  shows when trailing. Expected evidence was stated conditionally rather than strengthening the plant.

- In the showcase match on its own, AUR's top lane mismatch against NOR is left_half_space (41.9% of
  AUR's entries, interval 26-59%), not left_flank: a single match is a small sample. The season
  preview claim is left_flank.

## Needs human review
- The Spanish and French templates are my own translations; a native speaker should review the
  football register (e.g. "field tilt" is kept as a loan term in es/fr analyst mode).
- When a volume passer has no forward pass into a central danger zone, the sentence reads "pass
  quality 0x the league rate". True, but a "none of them" phrasing would read better; it needs a
  template variant chosen on a value, which I did not add.
- tests/test_dashboard.py skips at import when Playwright is missing, so a default run without
  requirements-ui.txt reports "1 skipped". Harmless, but it could move to a conftest hook if a clean
  "0 skipped" matters.
- The original code `NOR` is also a common abbreviation of a real club's name. CLAUDE.md forbids real
  trademarks; a 3-letter code is probably fine, but I did not rename an existing team (that would change
  the small league and the showcase). Worth a human decision.
