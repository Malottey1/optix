# Information architecture: progress

Branch `ui-visuals-ia` from 6c3369d (local tag `pre-ia`). Decisions: docs/PROGRESS.md, "IA decisions".

| Item | Status | Commit | Numbers / notes |
|---|---|---|---|
| Phase 0: branch, tag, green start | done | 78d4c3f | default suite 451 passed, 2 skipped; build passes |
| Phase 0: shot_spam interval floor | done | 78d4c3f | claim-level 68/86 = 0.79 [0.69-0.86], upper 0.86 >= 0.80; slow file 3 passed (16.7 min); mutation 34/86 fails |
| Step 0: audit (docs/ia-plan.md) | done | a45f96e | words before: home 140, live 630, teams 984, players 1075, tech 2324 (1440); 15 visible lane/mismatch strings (12 on Teams) |
| Step 1: data export | done | 31f1e7f | 41 match files, 2.37 MB, largest 70.8 KB; ui.json 1.10 MB; export 23.8 s, peak RSS 392 MB; Python 464 passed / 2 skipped; Vitest 135 |
| Step 2: HeatPitch (web/src/charts) | done | fb1b22d | 384 bins, volume + change, View data table; tests: mass 1e-9, symmetry, bins = track counts, 15 zones = zoneShares exactly, tokens >= 3:1; tracer and mutation proof wired in Step 3 with the hub routes |
| Step 3: Fixtures and Match Hub | done | 1dbd3b8 | routes + redirects (10 redirect tests), nav Fixtures/Teams/Players/Tech; Vitest 160; hub at 1920x1080 shows header, turning points and the heat map (legend just below the fold, fixed in Step 7 review) |
| Step 4: Team Grid and Team Board | done | 0d3cc78 | lineup pitch (roving focus, mini-profile sheet, ledger link), style pizza, lane-lift strip, compact game-state slider (en/es/fr), signatures with intervals; board words 166-178 (budget 180), grid card <= 20; Python 465 passed / 2 skipped; Vitest 164; index gzip 179.8 KB |
| Step 5: Player Deck and Player Console | done | (this commit) | deck filters/search, console routes/pizza/bars/touch map/pattern evidence, Raw / With context from fired checks only (6 players); Python 465 passed / 2 skipped; Vitest 172 (one full run had 3 timeouts under load, passed alone and on rerun); index gzip 181.5 KB, console chunk 6.4 KB |
