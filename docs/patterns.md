# Tactical patterns

Optix finds eight tactical patterns in the event log and uses them two ways: as cards of their own
(how often a team won the ball straight back after losing it in the final third) and as evidence
that a plain statistic would mislead (a team held most of the territory, true, but most of its
shots were from distance and it conceded counters). Every pattern is event-observable: it says what was
recorded, never why, and never anything that needs player positions off the ball.

The plan and audit (fields, thresholds, base rates, Tier 2 and skipped patterns) are in
docs/patterns-plan.md. Measured numbers are generated, never typed: docs/pattern-recall.md
(claim level) and docs/pattern-diversity.md (what the stream shows).

## How a pattern becomes a card

1. **Detector** (`engine/patterns/<name>.py`): returns findings with ordered evidence event ids
   (fixed anchors per instance, e.g. the first and last pass of a touchline spell) and the numbers.
2. **Claim**: the Analyst builds a claim object with `claim_type: "pattern"` and the family as the
   metric (`pat_*`); every number is a param of the claim.
3. **Verifier**: an independent recompute (`recompute` in the same module, never calling the
   detector) re-reads every evidence event from the log, re-checks every condition and recounts the
   numbers. A missing, extra, reordered or foreign event, or a changed number, blocks the claim
   (tests/test_pattern_claims.py mutates real claims to check this). Over ten full leagues the
   detector and the recompute disagreed 0 times.
4. **Text**: three phrasings per family in English, Spanish and French, chosen by a stable hash of
   the claim id, with plural forms and zero-count variants (no "0 shots, 0 xG"). The number guard
   checks every rendered sentence; a model rewrite (when Azure OpenAI is configured) passes the same
   guard plus the banned-wording list, else the template is used.

## The naive claims and the rules that test them

Each pattern pairs with a plain statistic the Analyst would say first. A context rule in
`engine/rules/` runs the pattern's detector on the claim's own window; when it fires the claim is
blocked with a revision hint and the Analyst rewrites it with the numbers that make it honest.

| Naive claim | Rule | What the revised claim adds |
|---|---|---|
| "attacks mostly down the left" | ctx_attack_side_vs_finish_side | where the shots were actually taken |
| "N crosses" | ctx_crosses_vs_cutbacks | the cut-backs and their xG per shot |
| "N final-third passes" | ctx_volume_without_central_access | the touchline spells and the box entries |
| "N% of the territory" | ctx_tilt_without_access | the share of shots from outside the box, xG per shot |
| "N% of the territory" | ctx_dominance_with_transition_exposure | counter-attack shots conceded and their xG |
| "lost the ball N times in the final third" | ctx_losses_vs_immediate_regain | how many were won straight back |
| "N fouls" | ctx_fouls_clustered_after_losses | how many came straight after losing the ball |
| "a quiet game: N touches" | ctx_low_volume_high_quality | nothing: it is blocked and never published |

When two rules fire on one claim the Analyst uses a combined template that says both, or drops the
claim; it never publishes a sentence missing one rule's numbers. Cross-claim tests check that an
unqualified territory claim never sits in a window where the low block or the counters hold, and
that a "quiet game" claim never appears for a player the starved-finisher detector finds.

## Status

From docs/pattern-recall.md (full leagues, 20 teams, 380 matches each; tuning seeds 2026-2028,
hold-out 2029-2030; recall on planted cases, false positives on teams with nothing of that family
planted). Bar: recall >= 0.60 and false-positive rate <= 8% on both tuning and hold-out.

| Pattern | Status | Note |
|---|---|---|
| P1 Build on one side, switch | validated | planted only; natural base rate about 0 |
| P2 Cut-backs from the goal line | validated | false positives about 6%: real cut-backs by teams without the motif |
| P3 Touchline spells | validated | planted only; the stream publishes it only when >= 10% of the team's final-third passes are in the spells |
| P4 Deep block, shots from range | **experimental** | recall 0.44 tuning, 0.44 hold-out after three tuning attempts; the planted spells often fall short of the shot count or block line in any 15-minute window |
| P5 Losses won straight back | validated | |
| P6 Territory and counters conceded | **experimental** | recall 0.63 tuning, 0.48 hold-out; the misses are counters planted in matches where the team did not hold the territory, which the definition requires |
| P7 Few touches, free shots | validated | player level, full matches only |
| P8 Fouls after losing the ball | validated | small planted sample at half strength (4 cases) |

Experimental patterns are switched off by default (`enabled=False` in engine/patterns/config.py):
they publish no card of their own, in the showcase or anywhere else, and the Tech page catalogue
labels them "experimental, off in the stream". Their context rules stay on: a rule only blocks a
naive claim and asks for the numbers that make it honest, and the Verifier recomputes those numbers,
so a missed spell leaves the claim as it was before patterns existed, and a found one adds checked
context. Switched on, their claims are verified exactly like the others (tests/test_pattern_claims.py
runs the showcase that way and mutates the P4 and P6 claims). At 0.5x planted strength the detection limit is visible in the last
column of docs/pattern-recall.md: P4 drops to 0.41; the others hold.

## What the stream shows

- At most 3 cards per family per match, at most 6 pattern or naive candidates per half-time or
  full-time summary, the best of each family before the second of any.
- Within a match, a family already shown at half time returns at full time only if its number
  moved by at least 25% and by at least 2 (a count going from 1 to 2 is noise, not news).
- Across matches (novelty): a family shown for a team in either of its previous two matches is
  down-weighted, and held back unless its number moved the same way. With novelty the worst team
  repeats 35.0% of its pattern cards from the previous match (bar 40%; 53.2% without novelty). The
  most common family, the cut-back, is 26.9% of pattern cards, above the 25% bar: real cut-backs
  happen in about 6% of team-matches without any planting, and with P4 and P6 switched off there
  are fewer families to share the cards (docs/pattern-diversity.md). The price of novelty: a team's
  signature pattern is not repeated every week, so fewer planted cases reach the stream.
- The showcase match is streamed standalone, with no history, so no novelty adjustment applies.

## The showcase

AUR 4-0 NTG (seed 2026, try 6915). Besides the five original traps it holds the deep block (AUR),
the counters conceded and the touchline spells (NTG). The stream shows the touchline spells as a
card; the deep block and the counters are experimental, so they appear only through the three naive
claims their rules rewrote (territory twice, final-third volume). The search tried all 20000 seeds allowed: no seed held
the five traps, four new families and two rewritten naive claims together, so per the brief the
target was relaxed to three families (docs/PROGRESS.md, Pattern decisions).

## Limits

- Event data only. No pattern claims a 1v1, an overlap, a run, a shape or a player's position off
  the ball; "deep block" is read from where the shots were taken and from blocks and clearances.
- Synthetic data. Recall is measured on motifs we planted ourselves at realistic strengths; it shows
  the detectors find what the definition describes, not that the definitions capture real tactics.
  Real data would need the thresholds re-tuned.
- Event data cannot show formations, intent or off-ball movement, so no pattern names one.
- Thresholds were tuned on three leagues of the same generator; the hold-out leagues are new seeds
  of that generator, not new data.
- The starved finisher compares a substitute's touches with full-match lines (minutes are not in
  the engine tables).
- Tier 2 patterns (P9-P17) are not built; false nine vacuum and mid-block passivity are skipped
  because their core is not observable in event data.

## How to add a pattern

1. Write the definition in docs/patterns-plan.md: fields, thresholds, the naive claim it tests, the
   visual and icon. Measure its base rate on an unplanted league before planting anything.
2. Add its thresholds to `engine/patterns/config.py` (`enabled=True`) and a module in
   `engine/patterns/` with `detect` (findings with ordered evidence ids) and an independent
   `recompute` that re-reads the events and never calls `detect`. Register it in
   `engine/patterns/__init__.py` (MODULES, VALUE_KEYS).
3. Add the metric and, if it tests a naive claim, a `ctx_*` rule in `engine/rules/` (registered in
   PATTERN_RULES) to contracts/claim.schema.json; regenerate the TypeScript types
   (`npm run gen:types` in web/).
4. Add `pattern.<family>` with three variants in en, es and fr (agents/templates/), plural forms and
   a zero-count variant if a count can be 0, and the revised template for the naive claim.
5. Plant it in the generator with its own random stream (data_gen), so the byte-identity test still
   passes with every propensity at zero; add micro-sequence tests in tests/test_patterns.py.
6. Add its icon to the registry (web/src/icons) and its name in three languages (web/src/lib/i18n.ts).
7. Run `python -m tools.pattern_recall`. If hold-out recall is below 0.60 or the false-positive rate
   is above 8% after three tuning attempts, set `enabled=False`: it stays in the catalogue as
   experimental and publishes no card.
