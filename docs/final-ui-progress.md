# Final UI progress

Branch `ui-visuals-final-ui` from a8ab229 (local tag `pre-final-ui`, not pushed). Green start: default
suite exit 0, `npm run build` pass.

| Item | Status | Commit | Numbers | Open questions |
|---|---|---|---|---|
| Step 0 audit (docs/final-ui-plan.md, data dictionary "What the data can and cannot show") | done | (this commit) | lane claim on 37/41 fixtures, 61 directions, 40 low confidence; hub gap under Heat Maps 2,248 px at 1440 | – |
| Step 1 nav and Settings | done | 903f0ef | nav Home/Fixtures/Teams/Players; Technical details + kits note in Settings; search button hidden until Step 8 | – |
| Step 2 data export | done | b0cd777 | ui.json 1,225,980 B; matches dir 2,685,162 B (largest 71,409 B); 9 new profile tests pass | pressure regains not exported (no field) |
| Step 3 Match Hub layout | done | d13fa2d + (this commit) | gap under Heat Maps 2,248 px -> 16 px at 1440; panel sticky, viewport-high, paged 5/10 | check_hub_layout + old-layout proof caught; 4 new Vitest; entry JS 182.85 KB gzip (was 177.0) |
