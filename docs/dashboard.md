<img src="../web/public/brand/optix-logo.svg" alt="Optix" width="140" />

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
- **React Router** `HashRouter`: `#/`, `#/fixtures`, `#/match/:id` (and `/ledger`), `#/teams`, `#/teams/:code`,
  `#/players`, `#/players/:id`, `#/tech`. Each page is a lazy chunk. Old deep links redirect (`#/live` to
  the showcase hub, keeping its query; `#/match` to the fixtures), one test per old link.
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
- `data/`: `StreamSource` interface, `ReplaySource` (loads the four files), `SseSource` (live: the same
  files for the board, then verified insights pushed over server-sent events by the Optix API),
  `pickSource` (live only when the same-origin `./healthz` answers as the Optix service), and the
  match model (indexes and lookups).
- `types/`: generated contract types, hand-written types for the rest of `ui.json`, and runtime shape
  guards that fail loudly with the path of the first field that drifted.
- `state/`: replay clock and settings stores.
- `components/`: shell and navigation, settings tray, pitch, icons, and the `ui/` primitives.
- `features/<page>/`: one folder per route.
- `lib/`: formatting (numbers in each language's own form, football clock) and the interface dictionaries.

Source and indicator: served by the Optix API (`uvicorn service.app:app`, see docs/AZURE.md) the page
opens the same-origin SSE stream `./api/match/<id>/stream?speed=30` and the scoreboard chip reads
**Live stream**: the feed holds only the insights the server has pushed, and the clock cannot run
past the server's clock (`limit` in the replay store). Served as static files (Vite preview, any
static host) `./healthz` is the static file `public/healthz` (`"service": "static-replay"`), so the
page replays the files and the chip reads **Replay**. If the live stream drops or sends a malformed
frame the page falls back to the replay of the same verified files and the chip changes to Replay.
Every request goes to the origin the page came from.

Replay: `requestAnimationFrame` advances the clock store. Components subscribe with coarse selectors
(for example the scrubber on a two-second grid, the feed when a new insight arrives); the parts that
move every frame (clock text, ball marker and trail, momentum playhead) are written through refs by
`useReplayFrame`, so a tick does not re-render the tree.

## Pages

| Route | What it shows | Source |
|---|---|---|
| `#/` Home (default) | The audited line-up artwork with the headline, sub-line and two buttons (unchanged). Below it, a lazy chunk that loads the showcase match file: the showcase strip (score, goal / card / substitution marks, Live replay chip, Explore Match Hub), three key insights (one revised and two passed, chosen by a fixed rule), tiles (xG race, momentum, where the ball was), player spotlight, two validated pattern families (no recall figures), five crests, and "Why trust Optix" (three statements, link to Tech). At most 260 words below the hero, 30 per card | `ui.json`, `insights.jsonl`, `timeline.json`, `matches/m_showcase.json` |
| `#/fixtures` Fixtures | Every fixture in the data, grouped by matchweek: both badges, names (codes on phones), score, status chip and the number of verified insights; a favourite star per row and a Following filter (starred fixtures or fixtures of followed teams). The showcase AUR v NTG is pinned as the Live replay; every other match is Final. Filters by team and status; 44 px tap targets. No future fixtures (the data has none) | `matches/index.json` |
| `#/match/m_showcase` Match Hub, live | The live console (below) inside the hub frame, with a Live chip and a link back to the fixtures | as the live console |
| `#/match/:id` Match Hub, final | Two columns from 1100 px: the insights panel (tabs Insights / Patterns, family chips, pages of 5 or 10) sticky on the right; below 1100 px it sits under the header. `?t=<clock_sec>` opens the event log at that clock (the Player Console's chance links). Main column, in order: scoreline header (score, xG, shots); turning points on a timeline (goals, momentum swings, verified pattern cards, cards and subs, each with an icon, each opening the evidence drawer); heat maps (HeatPitch: volume or second-half change, per team, per half); pattern and insight cards (one headline, one visual, at most one short sentence; at most two per family or type); Matchup only when a verified lane claim exists (otherwise the section is omitted); the event log (filter by event-type icon, virtualised, arrow keys); a link to the match's claim ledger (`#/match/:id/ledger`) | `matches/<id>.json` |
| Live console (inside the hub) | Scoreboard with a momentum tug-of-war; play, pause, scrub (with goal and insight markers) and speed; SVG Focus Pitch with the selected or latest insight's evidence and a ball marker at the latest event location (an event-based proxy, labelled as such); momentum chart; Perimeter Lock; rhythm pulse; pinned-in-own-half gauges; shot blocks; the stream of verified cards (matchup cards show mismatch crosshairs, xG cards shot blocks, the rhythm card a pulse). Each card has a headline (the stream's sentence), an evidence summary, and an evidence drawer with a mini pitch, the evidence chain, the claim object, every verification attempt and the exact evidence events. A card whose first attempt was blocked shows "Rewritten after verification", a Before / After toggle and the rule's reason in one sentence | `insights.jsonl`, `claims.jsonl`, `timeline.json`, `ui.json` |
| `#/teams` Team Grid | One card per club: badge, name, matches played and the five fingerprint chips (Tempo, Press, Passing, Territory, Counters), a favourite star; a Following filter | `ui.json` teams |
| `#/teams/:code` Team Board | Visual first, at most 180 visible words. Identity header (badge, kit, five chips); the lineup pitch (most-used XI by listed position, jersey nodes with number and surname, roving focus, a mini-profile sheet with goals, assists and "VIEW DEEP TACTICAL LEDGER →" to the Player Console); style pizza against the league; where they attack (five lane bands, lift over the league; the soft-side line only when the rule passes); game-state swaps; up to three signature patterns with the share of matches and its interval, "Show all" in a drawer. Tables in closed "View data" sections | `ui.json` teams, lineups, patterns, visuals |
| `#/players` Player Deck | One card per player: initials avatar, badge, name, position and two stats by position (FW/MF goals and assists, DF tackles and interceptions, GK saves and save rate), a favourite star; a Following filter. Filter by team and position, search by name; 4 / 3 / 2 columns at 1440 / 1024 / 390 | `ui.json` players |
| `#/players/:id` Player Console | Header (avatar, name, number, position, team badge, minutes and two position stats); forwards and midfielders: chances panel and the chance evidence drawer (tiles, tabbed pitch, breakdown, table with play links to the Match Hub); defenders: defensive actions (totals, per 90, per 100 opposition entries, percentile among position peers), the defensive action map, progressive passing; goalkeepers: shots faced in the keeper's frame, shot stopping, distribution; "Not available in event data" notes linking to the Tech limits; pass routes on the Focus Pitch (top 8, then "Show all routes (N)"); Raw / With context, built only from the Verifier's existing player check (disabled with a note when the player has none); pattern chips with their evidence events; percentile pizza; the same percentiles as diverging bars around the median; the season touch map (HeatPitch) | `ui.json` players, visuals, patterns; `matches/players-heat-<code>.json` |
| `#/tech` Tech Blueprint | Pipeline (Analyst → Verifier → Narrative → number guard) with counts from the ledger; one real claim followed from its blocked first attempt to the translated sentence; the verification ledger (every claim: passed / passed with context / revised / blocked, and the deciding rule); the measured numbers, a visual guide (legend of every visual, with the lane mismatch crosshairs as its one worked example, "One example of many"), parsed from docs/realism-report.md, docs/robustness.md and docs/verifier-recall.md; "Planned Azure integration (not built yet)" | `ui.json` ledger, measured, rewrites |

Header: Search (button or Ctrl/Cmd+K: a dialog over teams, players and fixtures, grouped,
accent-blind, arrows and Enter) and Settings. Settings (slide-over): Technical details (the Tech
page), language (en / es / fr: the stream's own translated,
number-guarded sentences plus small interface dictionaries), reduce motion, show evidence by default,
high contrast and density, Favourites ("Clear favourites"; kept in this browser only) and the kits
note. They are saved in localStorage inside try/catch, so the app works when
storage is blocked. The tray says that the Tech Blueprint explanations and some longer chart captions
are English only (the Team Board, Player Deck and Player Console strings are in en / es / fr).

Brand: the header wordmark (inline SVG, `currentColor`) links to Home. Club crests come from `TeamBadge` (web/src/components/brand/TeamBadge.tsx): the crest image from 40 px up, a disc in the club accent with the club code below 40 px, or when the image fails or the code is unknown. When the name or code is shown beside it, the badge is decorative (`alt=""`). Club accents (`--team-*`) are never used to mark a verdict. Image sources, the mark audit and licences: design/ASSETS.md and docs/brand-audit.md.

View options for screenshots and tests: `#/match/m_showcase?t=2760&select=ins_0009&lang=es&play=1` (old
`#/live?...` links redirect there with the query).

## Not available in this dataset

- **Minutes played** come from lineups.csv (on / off seconds). Defensive rates are per 90 and per 100
  opposition entries above a 270-minute floor; the pizza and deck figures stay season totals.
- **Ground duels, pressure regains, save location, line-breaking passes:** not in the event data;
  the Player Console says so and links to the Tech page's Limits section.
- **Positions or tracking.** Nothing on the Player Deck uses fatigue, distance, speed or fitness.
  The ball marker on the Focus Pitch is the location of the latest event, not a tracked ball.

## Checking it

`python -m tools.check_web` (needs `pip install -r requirements-ui.txt` and a built `web/dist`) serves
`web/dist` and opens every route at 1440 px and 390 px in headless Chromium, with axe-core injected.
Routes: home, fixtures, hub_live (`#/match/m_showcase`), hub_final (`#/match/m_001`), teams, team_board
(`#/teams/AUR`), team_sheet (the same board with the lineup mini-profile open), players, player
(`#/players/NTG_07`), player_df (`#/players/CAL_05`), player_gk (`#/players/CAL_01`), chance_drawer
(`#/players/NTG_11` with the drawer open), settings (Home with the sheet open), search (Fixtures with
the search dialog open), tech. Each also runs at 1920x1080 and 1600x900.
It writes `docs/screens-v8/<route>_<desktop|mobile|1080p|900p>.png` (every route is also checked at
1920x1080 and 1600x900; plus
`badges_24_32.png`), each under 300 KB; lazy images are scrolled into view before a full-page shot.
It fails on any of:
- a console error, page error, failed request, HTTP error, or request to a host other than localhost;
- served by the Optix API: a chip other than Live stream, fewer than three cards arriving over SSE, no
  SSE request, or any request to another origin; served statically: a chip other than Replay
  (`check_live_stream`; same-origin `/healthz` and `/api/...` calls are the only API calls allowed);
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
- initial JavaScript of 250 KB gzip or more;
- a text budget exceeded (visible words, `TEXT_BUDGETS` in tools/check_web.py, one config): a card 30,
  a Team Grid card 20, the Team Board 180 in all, each Match Hub recap section 60 (the event log has
  none); the measured counts are printed per route, and `check_text_budget_proof` adds words to a
  page and shows each budget then fails;
- "lane" or "mismatch" in visible text outside its allowed places (`data-lane-ok`: the Tech worked
  example, the Matchup section, the lane-lift label, a verified claim's crosshair legend); the proof
  adds a lane sentence to the hub and shows the scan catches it;
- an image without alt text, without width and height, or decorative (`alt=""`) where no name is beside
  it; a non-hero image that is not lazy; a Home hero without `fetchpriority=high`;
- a shipped image with EXIF, XMP, ICC or text metadata, or over its size budget (300 KB; the hero
  220 KB at 1600 px and 90 KB at 800 px);
- a badge at 24 or 32 px that does not draw (mini-mark and crest, `check_badges`);
- Home hero text below 4.5:1 against the picture behind it at 1440, 1920x1080, 1600x900 or 390
  (`check_hero_contrast`: the text is hidden, the boxes it covered are captured, and the 99.5th
  percentile background luminance is compared with the text colour).

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
