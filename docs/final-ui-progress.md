# Final UI progress

Branch `ui-visuals-final-ui` from a8ab229 (local tag `pre-final-ui`, not pushed). Green start: default
suite exit 0, `npm run build` pass.

| Item | Status | Commit | Numbers | Open questions |
|---|---|---|---|---|
| Step 0 audit (docs/final-ui-plan.md, data dictionary "What the data can and cannot show") | done | (this commit) | lane claim on 37/41 fixtures, 61 directions, 40 low confidence; hub gap under Heat Maps 2,248 px at 1440 | – |
| Step 1 nav and Settings | done | 903f0ef | nav Home/Fixtures/Teams/Players; Technical details + kits note in Settings; search button hidden until Step 8 | – |
| Step 2 data export | done | b0cd777 | ui.json 1,225,980 B; matches dir 2,685,162 B (largest 71,409 B); 9 new profile tests pass | pressure regains not exported (no field) |
| Step 3 Match Hub layout | done | d13fa2d + (this commit) | gap under Heat Maps 2,248 px -> 16 px at 1440; panel sticky, viewport-high, paged 5/10 | check_hub_layout + old-layout proof caught; 4 new Vitest; entry JS 182.85 KB gzip (was 177.0) |
| Step 4 Matchup redesign | done | (this commit) | shown on 17/41 fixtures (41%) with the confidence display rule; 2 new Vitest; checker compares outlines + rule thresholds | – |
| Step 5 Style against the league | done | (this commit) | 5 rows, one scale per measure, chips from numbers; style-row consistency check + mutation; boards 167-178 words | – |
| Step 6 Players: deck, console, evidence drawer | done | (this commit) | DF/GK/FW panels; drawer with play links (?t=); 5 new Vitest + 1 hub; checker: 4 routes, 3 mutations caught; entry JS 182.3 KB gzip | routes caption and legend deviate (zone routes, no per-pass rows); see PROGRESS |
| Step 7 Home | done | (this commit) | 211 words below the hero (budget 260), cards <= 29; HomeSections lazy chunk 4.6 KB gzip; 4 Home mutations caught | nav pill over hero not done; hero faces conflict flagged |
| Step 8 search | done | (this commit) | overlay chunk 2.35 KB gzip; entry 189.2 KB gzip; 6 new Vitest (ranking, keyboard, focus return, language); checker route clean at 4 sizes | – |
| Step 9 favourites | done | (this commit) | stars on 3 surfaces, Following chip, Clear in Settings; 5 new Vitest; checker clean on teams/players/fixtures/settings | – |
| Step 10 docs | done | (this commit) | dashboard.md, visuals.md (V16-V23), i18n-review.md (181 keys), final-ui-plan.md summary, Tech Limits, README to screens-v9 | – |
| Gates | passed | (this commit) | Python 474 passed / 2 skipped; Vitest 199; check_web all routes x 4 sizes 0 failures, 17/17 mutations; p95 16.8 ms; entry 185.3 KB gzip (+8.3); ui.json 1,226,114 B; matches 2,692,489 B; two identical exports; byte-identity 2026 + 2027; secret scan 0 | 10 curated screenshots committed (repo-size gate), all 62 local |
