# Optix: project rules for Claude Code

Optix is a multi-agent engine that turns **synthetic** football event data into live talking points, overlays and recaps that are both **true and not misleading**, with the evidence behind every claim. It is built for the Microsoft x Premier League "Inside the Game" hackathon (challenge: Synthetic Match Insights Engine for Premier League Studio).

## Non-negotiable rules

1. **Math first, language second.** All numbers are computed deterministically in `engine/`. An LLM never computes, estimates or guesses a number. It only writes sentences from already-calculated facts.
2. **Every insight is backed by a claim object.** Claims follow `contracts/claim.schema.json`. The Verifier checks the claim object (metric, value, evidence event IDs), never free text.
3. **Verify before translating.** Fact check and context check run on the language-independent claim object. Translation happens afterwards, and a guard re-checks that every number in the translated text still matches the claim.
4. **Two-part Verifier.** Fact check (does the event log back the claim?) plus context check (is it true but misleading given game state, sample size, or metric limits?). Rules live in `engine/rules/`.
5. **No causal claims from thin data.** Block claims like "the red card caused the loss". Allow descriptive ones ("possession fell from 54% to 38% after the card"). Diagnoses are ranked factors with a confidence level, never a single label.
6. **Synthetic data only, event data only.** No real Premier League data. No tracking-derived claims (player positions, meters covered, off-ball runs). If a visual needs positions, use an event-based proxy and label it as one.
7. **Fictional teams, no real trademarks.** No real club names, badges or league logos in code, data, UI or demo. Use fictional teams and codes.
8. **Describe the present and past only.** No outcome predictions, no predicted scores, no betting or recruitment features. The pre-match preview describes style and mismatches only.
9. **All zones are from the attacker's point of view.** Never mix attacking directions, or matchup overlaps will be mirrored.
10. **Contracts decouple engine and UI.** The insight stream carries a semantic `insight_type` plus data. The frontend owns the mapping from type to widget.

## Repo layout

- `contracts/` JSON Schemas for the claim object and the timed insight stream. Change these deliberately and update docs and tests together.
- `data_gen/` synthetic data generator (fictional teams with hidden `style_seed`, planted traps).
- `engine/` deterministic metrics, style profiles, matchup, momentum, Verifier rules.
- `agents/` Ingest, Analyst, Narrative, Verifier, Personalization agents and orchestration.
- `app/` dashboard (feed cards, Focus Pitch, Perimeter Lock, momentum bar, evidence drawers).
- `docs/` architecture and design notes.
- `tests/` tests, including "the engine recovers the style seeds planted in the data".

## Build order

1. Synthetic data generator (thin slice first: 4-6 teams, about 40 matches, events/shots/passes)
2. Style profiles and matchup
3. Verifier on claim objects (fact + context check)
4. Insight stream plus dashboard with the Focus Pitch
5. Personalization (analyst/casual, favorite club, player focus, single metric, language)
6. Azure deployment pieces

## Planted traps in the synthetic data

Each must exist in the data and be caught by the engine: field tilt while leading and sitting deep, twenty 0.05 xG shots, a winger with chances created mostly from corners, a volume passer whose forward passes end wide, a team that attacks mostly down one flank against a defense weak on that side. Hand-build one showcase match containing all of them.

## Working conventions

- Keep commits small and messages plain. Do not add Claude as author or co-author on commits or PRs.
- Python for `data_gen/`, `engine/`, `agents/`. Keep functions pure where possible so metrics are testable.
- Every metric function documents its definition, inputs and known limits, since the Verifier's context rules refer to them.
- Cut list if time is short: red card analysis, underperformance diagnosis, fatigue proxy, pounce events, ingest noise cleanup are optional.
