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

1. A claim has no prose, only a metric, value, window, game state, evidence IDs, and a `template_key` + `params`.
2. A claim with no evidence IDs cannot be verified (rule `missing_evidence`).
3. `causal` claims are always blocked (rule `causal_claim`). Descriptive changes are allowed.
4. Status `published_with_context` means true but misleading on its own: the insight carries a `context_chip` showing the shallow standard stat, muted, beside the honest one.
5. Translation happens after verification. The number guard checks that every numeric param still appears in each translated string.
6. Coordinates are a 0-100 by 0-100 pitch from the **attacking team's point of view**.
7. Team codes are fictional.

## Match clock

Seconds from first-half kickoff. Second half starts at 2700.

## Payload shapes by `insight_type`

| insight_type | payload uses |
|---|---|
| `matchup_mismatch` | `metrics`: attack share and defense concession share for the zone; `focus` on the zone |
| `perimeter_lock` | `points`: passes outside the box; `metrics`: passes outside vs entries into the box |
| `threat_pass` | `points`: one pass with `value` = xT added |
| `momentum_shift` | `metrics`: momentum value per team, score and game state shown beside it |
| `turning_point` | `points`: trigger event; `metrics`: momentum before and after |
| `rhythm_wave` | `series`: 15 values, one per minute |
| `volume_vs_value` | `metrics`: standard stat vs honest stat (pairs with `context_chip`) |
| `set_piece_inflation` | `metrics`: chances created total vs open play |
| `player_focus` | `player_ids` set; any metric |
| `milestone` | `metrics`: milestone name and count (within-dataset milestones only) |
| `red_card_segment` | `metrics`: per-10-minute rates per segment; `confidence` set; descriptive only |
| `pounce_sequence` | `points`: only provable events (lost duel, switch of play, shot) |
| `underperformance_stack` | `metrics`: ranked factors with weights; `confidence` always set |
| `recap_line` | any |

## Player-focus mode

Not a separate stream. The dashboard filters the same stream to insights whose `player_ids` contain the focused player.

## Personalization

Held in a user profile (not part of these schemas): mode (analyst or casual), favorite club, favorite player, single chosen metric, and language. The stream already carries both tones and every available language in `text.rendered`, so personalization is selection, not regeneration.
