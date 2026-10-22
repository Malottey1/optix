# Dashboard

The current dashboard is `web/`: Vite, React and TypeScript. It replays the showcase match on a clock
and shows the verified insight stream, team style fingerprints, player context and how the pipeline
checks itself. The page computes no statistic. Every number comes from the four files
`agents.run_match` writes, copied byte for byte into `web/public/data/`:
- `insights.jsonl` (the timed insight stream, `contracts/insight.schema.json`)
- `claims.jsonl` (every verification attempt, including blocked ones)
- `timeline.json` (teams, goals, momentum, periods)
- `ui.json` (built by `agents/dashboard_data.py` from engine/ outputs and the generated reports in docs/)

`app/` (React with no build step) and `legacy/dashboard-v1/` are **deprecated** and kept for reference;
their checks still run as `tests/test_dashboard_legacy.py`.

## Run it

Needs Node 20.19 or later and the Python environment from the README quick start.

```bash
python -m agents.run_match --match m_showcase --out out/insights.jsonl   # engine output in out/
cd web
npm ci --ignore-scripts      # exact versions from package-lock.json
npm run data                 # copy out/ into public/data/ (only after the engine output changed)
npm run dev                  # http://127.0.0.1:5173/
npm run build                # static site in web/dist/
npm run preview              # serve web/dist/ on http://127.0.0.1:4173/
```

`web/public/data/` is committed, so `npm run dev` and `npm run build` work without running Python.
The data files are never edited by hand; `npm run data` refreshes them. Other scripts: `npm run lint`,
`npm run typecheck`, `npm test` (Vitest), `npm run format`, `npm run gen:types` (TypeScript types from
`contracts/*.schema.json`, output committed in `web/src/types/generated/`).

## Stack

All versions are exact and every package was at least two weeks old when installed
(`npm install --save-exact --ignore-scripts --before=<date>`). The full list is in `docs/PROGRESS.md`.

- **Vite 7, React 19, TypeScript 5.9** in strict mode (`noUncheckedIndexedAccess`; no `any`).
- **React Router** `HashRouter`: `#/live`, `#/teams`, `#/players`, `#/tech`. Each page is a lazy chunk.
- **Tailwind CSS 4** through its Vite plugin. Design tokens are CSS variables in
  `web/src/styles/tokens.css`, mapped to Tailwind colours with `@theme inline`. The body background is
  set in plain CSS in `index.html`, so there is no flash before the styles load.
- **Radix UI primitives** (dialog for the drawer and settings tray, tooltip, tabs, toggle group,
  slider, switch), wrapped as small components in `web/src/components/ui/`.
- **Motion** for transitions, through `MotionConfig` so reduced motion (system or setting) turns them off.
- **Zustand** stores for the replay clock and the settings.
- **d3-scale and d3-shape** for maths only. The pitch, lanes, momentum chart, Perimeter Lock, scatter,
  bars and the visuals in `components/viz/` (docs/visuals.md) are hand-written SVG; there is no canvas and no chart library. Marks carry
  `data-event-id`, `data-lane`, `data-team`, `data-claim-id` and similar attributes for the tests.
- **Fontsource** self-hosted fonts (Inter variable for the interface, Barlow Condensed for numerals and
  display; both OFL) with tabular numerals. Nothing is loaded from a CDN; at runtime the page requests
  nothing except the server it is loaded from.
- Dev tooling: ESLint, Prettier, Vitest with Testing Library and jsdom, axe-core (used by the browser
  gate), json-schema-to-typescript.

Code layout (`web/src/`):
- `data/`: `StreamSource` interface, `ReplaySource` (loads the four files), `SseSource` (interface and
  contract test only, **not wired yet**: no server sends events), and the match model (indexes and lookups).
- `types/`: generated contract types, hand-written types for the rest of `ui.json`, and runtime shape
  guards that fail loudly with the path of the first field that drifted.
- `state/`: replay clock and settings stores.
- `components/`: shell and navigation, settings tray, pitch, icons, and the `ui/` primitives.
- `features/<page>/`: one folder per route.
- `lib/`: formatting (numbers in each language's own form, football clock) and the interface dictionaries.

Replay: `requestAnimationFrame` advances the clock store. Components subscribe with coarse selectors
(for example the scrubber on a two-second grid, the feed when a new insight arrives); the parts that
move every frame (clock text, ball marker and trail, momentum playhead) are written through refs by
`useReplayFrame`, so a tick does not re-render the tree.

## Pages

| Route | What it shows | Source |
|---|---|---|
| `#/live` Live Center | Scoreboard with a momentum tug-of-war; play, pause, scrub (with goal and insight markers) and speed; SVG Focus Pitch with the selected or latest insight's evidence and a ball marker at the latest event location (an event-based proxy, labelled as such); momentum chart; Perimeter Lock; rhythm pulse; pinned-in-own-half gauges; shot blocks; the stream of verified cards (matchup cards show mismatch crosshairs, xG cards shot blocks, the rhythm card a pulse). Each card has a headline (the stream's sentence), an evidence summary, and an evidence drawer with a mini pitch, the evidence chain (nodes by event type, click to pin on the pitch), the claim object, every verification attempt and the exact evidence events. A card whose first attempt was blocked shows "Rewritten after verification", a Before / After toggle and the rule's reason in one sentence | `insights.jsonl`, `claims.jsonl`, `timeline.json`, `ui.json` (rewrites, reasons, evidence, track) |
| `#/teams` Team Board | Head to head first: any attacker and defender, mismatch crosshairs (entries up, conceded down, crosshair on the verified claim's lane, attacker's frame with the mirror handled), the verified matchup sentence and the per-lane table behind a disclosure. Game-state swaps (field tilt and press intensity, trailing to leading). Zone shift of the showcase match, half by half. Per team: style labels with their rule and numbers in a tooltip (`engine/style_labels.py`); entry lanes made and conceded against the league; soft lane in both frames | `ui.json` teams |
| `#/players` Player Deck | Only involvement, pass quality and chances created. The Verifier's context cards for the volume passer and the set-piece creators (Before / After, reason, chance split, pass routes, evidence); a player profile with pass routes (forward passes or chances) and a percentile pizza; volume against quality; where the chances come from; the full sortable, filterable table | `ui.json` players |
| `#/tech` Tech Blueprint | Pipeline (Analyst → Verifier → Narrative → number guard) with counts from the ledger; one real claim followed from its blocked first attempt to the translated sentence; the verification ledger (every claim: passed / passed with context / revised / blocked, and the deciding rule); the measured numbers, a visual guide (legend of every visual), parsed from docs/realism-report.md, docs/robustness.md and docs/verifier-recall.md; "Planned Azure integration (not built yet)" | `ui.json` ledger, measured, rewrites |

Settings (slide-over from the header): language (en / es / fr: the stream's own translated,
number-guarded sentences plus small interface dictionaries), reduce motion, show evidence by default,
high contrast and density. They are saved in localStorage inside try/catch, so the app works when
storage is blocked. The tray says that the Team Board, Player Deck and Tech Blueprint explanations are
English only.

View options for screenshots and tests: `#/live?t=2760&select=ins_0009&lang=es&play=1`.

## Not available in this dataset

- **Minutes played.** Player figures are season totals, not per 90.
- **Positions or tracking.** Nothing on the Player Deck uses fatigue, distance, speed or fitness.
  The ball marker on the Focus Pitch is the location of the latest event, not a tracked ball.

## Checking it

`python -m tools.check_web` (needs `pip install -r requirements-ui.txt` and a built `web/dist`) serves
`web/dist` and opens every route at 1440 px and 390 px in headless Chromium, with axe-core injected.
It writes `docs/screens-v3/<route>_<desktop|mobile>.png` plus `live_1080p.png`, each under 300 KB.
It fails on any of:
- a console error, page error, failed request, HTTP error, or request to a host other than localhost;
- horizontal scroll; overlapping text;
- a control that Tab never reaches; Tailwind not applied; a serious or critical axe finding;
- missing data attributes on the marks;
- an evidence drawer whose events differ from the stream's evidence ids;
- a number on screen that does not trace to the data (football clock times, counts of listed items,
  per-type counts of evidence events and the visuals' formulas in docs/visuals.md are the only
  derived numbers);
- a visual that disagrees with the engine output (`check_consistency`; `--ref out --mutation-proof`
  also shows each of those checks fails on a copy with that visual's data changed);
- a crash or missing page when navigating between routes in the app;
- a language switch that changes a number, or a sentence that fails the number guard;
- a forbidden word (real club names, prediction or betting language, invented statistics such as "60,000");
- an error with storage blocked or with reduced motion;
- initial JavaScript of 250 KB gzip or more.

It also records replay frame times (p50 / p95) while the match plays at fast speed.

Tests:
- `tests/test_dashboard.py` (slow): every gate above on a freshly streamed match.
- `tests/test_web_stack.py`: exact versions and a tracked lockfile, no node_modules or dist in git,
  no remote URL or CDN in `web/src`, `web/index.html` or `web/dist`, plain-CSS body background,
  committed data equal to `out/`.
- `tests/test_number_trace.py`: the number tracer, including on the committed web data.
- `tests/test_dashboard_data.py`: ui.json content.
- `tests/test_ui_stack.py` and `tests/test_dashboard_legacy.py` (slow): the deprecated `app/`.
- `web/src/**/*.test.ts(x)` (Vitest): formatting, dictionaries, shape guards, data sources, settings
  with storage blocked, and the rewritten card's Before / After.
