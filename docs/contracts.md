# Contracts

Two JSON Schemas define how the engine, agents and dashboard talk to each other.

- `contracts/claim.schema.json`: the **Intermediate Claim Object**
- `contracts/insight.schema.json`: one item in the **timed insight stream**

## Flow

```
events -> Analyst (deterministic metrics)
       -> claim object (no prose)
       -> Verifier: fact check, then context check
            blocked -> Analyst/Narrative revise -> re-verify (attempt + 1)
            published / published_with_context
       -> Narrative: fill template_key + params (analyst + casual tones)
       -> Translation (after verification) -> number guard
       -> Personalization: filter by user profile
       -> insight stream item (clock, type, payload, evidence, text)
       -> dashboard: insight_type -> widget
```

## Rules the schemas enforce

1. A claim has no prose, only a scope, metric, value, game state, evidence IDs, supporting values, and a `template_key` + `params`.
   - `scope` is `season` (aggregate over the dataset so far, e.g. a pre-match preview: no window),
     `match` (one whole match) or `window` (a time window in one match). `match` and `window` require
     `match_id` and `window`; a season claim has no fake 0-0 window.
   - `value` carries `amount`, `unit`, `baseline`, `baseline_source` (`season` or `league` plus its n and
     dataset label), `interval` (95%, Wilson for shares), `effect_pp` (lift vs baseline in percentage
     points) and `confidence` (`low`/`medium`/`high`, see docs/engine.md). `z_score` is optional and is an
     internal ranking signal only, never a measure of size or certainty.
   - `supporting_values` holds every other named number the claim relies on (e.g. `concede_share`,
     `mismatch_pp`, `baseline_share`). The Verifier recomputes each one.
   - **Every number in `params` must equal `value.amount` or an entry in `supporting_values`.** JSON
     Schema cannot express this, so `contracts.checks.check_param_numbers(claim)` enforces it (tests
     and the Verifier call it).
2. A claim with no evidence IDs cannot be verified (rule `missing_evidence`).
3. `causal` claims are always blocked (rule `causal_claim`). Descriptive changes are allowed.
4. Status `published_with_context` means true but misleading on its own: the insight carries a `context_chip` showing the shallow standard stat, muted, beside the honest one.
   A context rule also names the params the sentence must carry (e.g. `box_entries` beside field
   tilt). If they are missing, the claim is `blocked` and `verification.revision_hint` lists them
   (`{"field_tilt_with_lead": ["box_entries"]}`); the Analyst rebuilds the claim with them and
   re-verifies with `attempt` + 1.
5. Translation happens after verification. The number guard checks that every numeric param still appears in each translated string.
6. Coordinates are a 0-100 by 0-100 pitch from the **attacking team's point of view**.
7. Team codes are fictional.
8. A `pattern` claim (`claim_type: "pattern"`, metric `pat_*`, docs/patterns.md) lists its evidence
   as fixed anchors per instance, in order. The Verifier recomputes the numbers from those events
   with code that never calls the detector; a missing, extra, reordered or foreign event blocks it.

## Match clock

Seconds from first-half kickoff. Second half starts at 2700.

## Payload shapes by `insight_type`

| insight_type | payload uses |
|---|---|
| `matchup_mismatch` | `metrics`: attack share, league share, defender completion and league completion for the lane (+ `lane`); `focus` on the lane; `points`: season entries into the lane (evidence) |
| `perimeter_lock` | `points`: final-third passes (`kind` pass or box_entry); `metrics`: field tilt, final-third passes, box entries |
| `threat_pass` | `points`: one pass with `value` = xT added |
| `momentum_shift` | `metrics`: momentum now and at the start of the spell (subject's sign); `series`: last 15 per-minute values |
| `turning_point` | `points`: trigger event; `metrics`: momentum before and after |
| `rhythm_wave` | `series`: 15 values, one per minute |
| `volume_vs_value` | `metrics`: standard stat vs honest stat (pairs with `context_chip`) |
| `set_piece_inflation` | `metrics`: chances created total vs open play |
| `player_focus` | `player_ids` set; any metric |
| `milestone` | `metrics`: milestone name and count (within-dataset milestones only) |
| `red_card_segment` | `metrics`: per-10-minute rates per segment; `confidence` set; descriptive only |
| `pounce_sequence` | `points`: only provable events (lost duel, switch of play, shot) |
| `underperformance_stack` | `metrics`: ranked factors with weights; `confidence` always set |
| `tactical_pattern` | `family` (a `pat_*` id, or for a revised naive claim the family its rule belongs to); `claim_metric`; `window`; `points`: the claim's evidence events in order (up to 24); `metrics`: the claim's value and supporting values. The frontend draws arrows, the other side's shot blocks or a route of event nodes, and falls back to the route for a family it does not know |
| `recap_line` | any |

## Player-focus mode

Not a separate stream. The dashboard filters the same stream to insights whose `player_ids` contain the focused player.

## Personalization

Held in a user profile (not part of these schemas): mode (analyst or casual), favorite club, favorite player, single chosen metric, and language. The stream already carries both tones and every available language in `text.rendered`, so personalization is selection, not regeneration.
