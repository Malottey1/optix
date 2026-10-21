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

## Surprises

## Needs human review
