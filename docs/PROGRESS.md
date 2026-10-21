# Progress log (overnight run)

Branch: `overnight`. Started 2026-10-21 07:08 local.

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
- The original code `NOR` is also a common abbreviation of a real club's name. CLAUDE.md forbids real
  trademarks; a 3-letter code is probably fine, but I did not rename an existing team (that would change
  the small league and the showcase). Worth a human decision.
