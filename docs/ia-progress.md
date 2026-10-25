# Information architecture: progress

Branch `ui-visuals-ia` from 6c3369d (local tag `pre-ia`). Decisions: docs/PROGRESS.md, "IA decisions".

| Item | Status | Commit | Numbers / notes |
|---|---|---|---|
| Phase 0: branch, tag, green start | done | 78d4c3f | default suite 451 passed, 2 skipped; build passes |
| Phase 0: shot_spam interval floor | done | 78d4c3f | claim-level 68/86 = 0.79 [0.69-0.86], upper 0.86 >= 0.80; slow file 3 passed (16.7 min); mutation 34/86 fails |
| Step 0: audit (docs/ia-plan.md) | done | a45f96e | words before: home 140, live 630, teams 984, players 1075, tech 2324 (1440); 15 visible lane/mismatch strings (12 on Teams) |
| Step 1: data export | done | (this commit) | 41 match files, 2.37 MB, largest 70.8 KB; ui.json 1.10 MB; export 23.8 s, peak RSS 392 MB; Python 464 passed / 2 skipped; Vitest 135 |
