# Architecture

## Agents

Plain Python classes in `agents/`, run in-process by `agents.orchestrator.Orchestrator`. No agent
computes a number: numbers come from `engine/` (metrics, claims, verifier); agents decide when to
look, what to claim, how to revise and how to word it from templates.

| Agent | Module | Role |
|---|---|---|
| Ingest | `agents/ingest.py` | deduplicate rows by event_id; drop and report rows missing the fields their type needs (never repaired) |
| Analyst | `agents/analyst.py` | triggers on the stream (kickoff preview, checkpoints, half/full time, momentum swings, threat passes, milestones); proposes plain claims via `engine.claims.build_claim`; revises blocked claims |
| Verifier | `agents/verifier_agent.py` | `engine.verifier` on the claim object, against the season (preview) or the ingested events so far |
| Narrative | `agents/narrative.py` | fills `agents/templates/<lang>.json` (analyst + casual per template_key) with the verified params; number guard |
| Personalization | `agents/personalization.py` | selects from the stream by mode, language, favorite club, player focus, single metric; never regenerates |

## Handoffs

Each handoff is a typed message (`agents/messages.py`) and a structured log record
(`agents/log.py`, one JSON object per action: agent, event, claim_id, attempt, status, rule_ids, ...).

| From -> To | Message | Content |
|---|---|---|
| stream -> Ingest | raw rows | event rows in clock order |
| Ingest -> Orchestrator | `IngestReport` + clean rows | accepted count, duplicate IDs, missing fields per dropped row |
| Orchestrator -> state | `MatchState` | ingested events, clock, score, rolling counters, cooldowns, published, dropped |
| Analyst -> Verifier | `ClaimProposal` | pending claim object, insight_type, trigger event and clock, dataset (match/season), strategy, revision_of, build spec |
| Verifier -> Orchestrator | `VerificationResult` | claim with `verification` filled (status, rule_ids, context_note, revision_hint, attempt) + the verdict details |
| Orchestrator -> Analyst | blocked `VerificationResult` | Analyst returns a revised `ClaimProposal` (attempt + 1) or drops it |
| Orchestrator -> Narrative | published claim | template_key + params |
| Narrative -> Orchestrator | `RenderedText` | language -> tone -> text, number_guard_passed |
| Orchestrator -> consumer | `Published` | final result, text, every attempt's result |

### The revision loop

1. The Analyst's first attempt is plain: the headline number only (`field_tilt.stat`: "NOR hold 76%
   field tilt in this spell").
2. The Verifier fact-checks it against the events ingested so far, then runs the context rules. A
   context rule that fires names the params the sentence must carry (`REQUIRES`); when they are
   missing the claim is `blocked` with `revision_hint`, e.g. `{"field_tilt_with_lead": ["box_entries"]}`.
3. The Analyst revises by rule: add game state and box entries (`field_tilt_with_lead`), add shot
   count and xG per shot (`shot_spam`), add the shot count (`small_sample_xg`), split open play and
   set pieces (`set_piece_inflation`), add pass quality (`wide_forward_passes`), add press intensity
   (`ppda_alone`). A fact-check failure is rebuilt from the tables once ("recompute"). Causal,
   red-card-causal and single-match-fatigue claims are dropped, never reworded.
4. The revised claim (attempt 2) is re-verified: now `published_with_context`, with its context_note.
   At most 3 attempts.

### What the Verifier can see

Match and window claims are verified against `MatchState.view()`: the match dataset restricted to
the events ingested so far. A claim can never be backed by an event the stream has not delivered.
The season preview (scope `season`) is verified against the season baseline.
