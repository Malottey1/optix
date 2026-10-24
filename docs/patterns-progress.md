# Patterns progress

Resume file for the tactical pattern library (branch `ui-visuals-patterns`). Decisions are in
docs/PROGRESS.md under "Pattern decisions"; the plan and audit in docs/patterns-plan.md.

## Steps

| Item | Status | Commit | Numbers / notes |
|---|---|---|---|
| Setup (tag, branch, green start) | done | | tag pre-patterns on 144ba45 |
| Banned wording (config, linter, guard, UI scan) | done | | 82 tests |
| Step 1 audit (docs/patterns-plan.md) | done | | Tier 1 built; Tier 2 not built; 2 skipped with reasons |
| Step 2 planting + byte-identity proof | done | 4e67d84 | proof passed; showcase 20000-try scan: relaxed to 3 families (offset 6914) |
| Step 3 engine, Verifier, Analyst | done | b9f6012 | 8 rules, revise loop, combined revision, mutation and cross-claim tests |
| Step 4 templates, guards, i18n | done | b9f6012 | 3 variants x 3 languages, plurals, zero variants, edge-value test |
| Step 5 UI and exports | done | 575be40 | cards, Team Board signatures, Player Deck chip, Tech catalogue, fallback |
| Step 6 measurement | done | this commit | 6 validated, 2 experimental (off by default); repetition bar met (35.0%), most-common-family bar missed (cut-back 26.9%) |
| Step 7 end-to-end checks | done | this commit | workflow == direct (byte-identical); audit chain intact (47 records, new families and rules); OTel, SSE and /api/claims tests; exports byte-identical twice |
| Gates, push, report | done | this commit | suite 433 passed / 2 skipped; slow tests run; Vitest 124; check_web 0 problems at 4 sizes; p95 16.7 ms; JS 168.0 KB |

## Definition of Done per pattern

Columns: 1 detector, 2 independent recompute + mutation tests, 3 contract + TS types, 4 naive claim
+ trap rule, 5 templates (3 variants x 3 languages), 6 micro-sequence tests, 7 planting + recovery,
8 UI card + icon, 9 docs/patterns.md, 10 committed.

| Pattern | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P1 Bait and Switch | x | x | x | x | x | x | x | x | x | x | validated |
| P2 Cutback | x | x | x | x | x | x | x | x | x | x | validated |
| P3 Flank Isolation | x | x | x | x | x | x | x | x | x | x | validated |
| P4 Elastic Low Block | x | x | x | x | x | x | x | x | x | x | experimental, off by default |
| P5 Counter-Press | x | x | x | x | x | x | x | x | x | x | validated |
| P6 Rest Defence | x | x | x | x | x | x | x | x | x | x | experimental, off by default |
| P7 Starved Finisher | x | x | x | x | x | x | x | x | x | x | validated |
| P8 Tactical Fouling | x | x | x | x | x | x | x | x | x | x | validated |
| P15 Set-Piece Dependence | x | x | x | x | x | x | x | x | x | x | experimental, off by default (Tier 2) |
| P17 Direct Transition Spike | x | x | x | x | x | x | x | x | x | x | validated (Tier 2) |
| P16 Press-Resistant Passer | x | x | x | x | x | x | x | x | x | x | validated (Tier 2) |
| P11 Pressed Presser | x | x | x | x | x | x | x | x | x | x | validated (Tier 2) |

## Follow-up: Tier 2 (P15, P17, P16, P11)

| Item | Status | Numbers / notes |
|---|---|---|
| Base rates and plants | done | unplanted base rates P15 6.6%, P17 3.9%, P16 4.6%, P11 2.6%; all four planted (no hidden trait marks a natural case) |
| Detectors, recomputes, rules, templates, UI | done | 0 detector/recompute mismatches over 10 leagues |
| Recall | done | P17, P16, P11 validated; P15 experimental after three tuning attempts (docs/pattern-recall.md) |
| Measurement | done | diversity bars met with novelty (cut-back 19.7%, VES 31.2%); 12 of 12 families in >= 5% of matches; verifier recall (peak 2.10 GB), robustness (peak 1.72 GB), realism (none out of range) re-run on the final leagues |
| Showcase | done | offset 6914 kept, AUR 4-0 NTG: 3 validated pattern cards (P17 twice, P3), 2 Tier 2 rewrites |
| Gates | one open | default suite 451 passed, 2 skipped; slow suite 29 passed, 1 failed: claim-level shot_spam recall 68/86 = 0.79 against its 0.80 floor (floor not changed; docs/PROGRESS.md); contract and TS types, lint, typecheck, Vitest 124, build; check_web --ref out --mutation-proof at 1440, 390, 1920x1080, 1600x900: 0 problems, p95 16.7 ms, initial JS 168.2 KB gzip; banned wording and real names (in the default suite), secret scan 0 findings, byte-identity proof (both seeds), two identical exports; screenshots docs/screens-v7 |
