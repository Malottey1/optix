# Progress log

## Azure integration (branch `ui-visuals-azure`, from main 1a5e875)

Green start: default suite 168 passed; `npm run build` ok. Each step below is its own commit.

### Azure decisions

**Step A (housekeeping, no number changes)**
- **NOR -> NTG:** a mechanical rename over every tracked text file (codes `NOR` -> `NTG`, ids
  `t_nor` -> `t_ntg`, `NOR_07` -> `NTG_07`, lowercase identifiers such as `nor_` in generator and
  tests). The team name "Northgate Town" stays. Old screenshot folders (docs/screens, screens-v2)
  are history and keep the old label; docs/screens-v3 is regenerated. One historical note that
  explains *why* NOR was a problem keeps the old code.
- **Why ordering cannot change:** no seed, hash or RNG stream depends on a team code or id (seeds
  are integers, teams are iterated in config order AUR, NTG, CAL, VES, HAR), and in the full league
  no code sorts between NOR and NTG (the next is OKP), so every sorted list keeps its order. The
  equivalence proof (below, "A1 equivalence proof") measured it.
- **Stale local season data:** `data/generated/` is gitignored. The first re-export of web data
  after the rename used a stale local copy (still `t_nor`), so the two pre-match preview insights
  could not join and the replay dropped from 35 to 33 insights. Regenerating `data/generated` with
  `python -m data_gen.generate --seed 2026` (which also rewrote `data/showcase/` byte for byte
  identical to the committed renamed files) restored all 35. The A commit carries the corrected export.
- **"0x" wording:** a template variant chosen on a value (`agents/narrative.VARIANTS`):
  `forward_passes.wide_low_threat` with `pass_quality_ratio == 0` renders
  `forward_passes.wide_low_threat.none` ("not one of them reached a central danger zone"). Every
  other multiplier reads "{ratio} times" / "veces" / "fois" instead of a glued "x".
- **"la mayoría, 19,3 %":** the parenthesis is the league average, so it now says so in all three
  languages ("league average", "media de la liga:", "moyenne de la ligue :"), not "most teams".
- Tests: `test_no_template_glues_a_multiplier_x_to_a_number`,
  `test_the_league_average_is_never_called_most_teams`, `test_a_zero_pass_quality_reads_not_one_of_them`.

**A1 equivalence proof.** Every measurement ran twice, serially, from clean git worktrees:
pre-rename main (1a5e875) and the rename commit alone (f9e3766, before any template change). The
"before" outputs were normalised (`NOR` -> `NTG`, `t_nor` -> `t_ntg`, `nor_` -> `ntg_`), and only
wall-clock fields were dropped (latency ms, `verified_at`, log timestamps, seconds taken).
- **Byte-identical after normalising (25 files):** generated season, all 8 tables plus ground
  truth; showcase match, all 8 tables plus ground truth; the showcase stream (insights, claims,
  timeline, ui.json, agent log; 35 insights, 10 blocked attempts revised, 0 dropped);
  realism.md (seed 2026); robustness.json (10 small leagues, 5 full leagues, 3 showcase searches);
  verifier recall (recall.json for 5 leagues, recall.md).
- **robustness.md** differs only in the "gen s" and "search time s" timing columns.
- Regenerating `data/showcase` from the renamed generator reproduced the committed renamed CSVs
  byte for byte.
- **The robustness tool was already broken on main:** since 09c3836, `tools/robustness.py` imports
  `tests.test_verifier_full._counts`, which no longer exists, and it fails in its full-league part.
  For the proof, a scratch wrapper (not committed) ran it in one process with that one helper
  stubbed. The verifier part of robustness is therefore empty in both runs; verifier recall is
  measured in full by `tools/verifier_recall.py`, and that is identical. I did not fix the tool;
  it is listed as an open issue.

**Dependencies.** `requirements-azure.txt`, exact pins each released at least two weeks before
2026-10-22 (checked on PyPI): agent-framework-core 1.20.0 (2026-10-02; 1.21.0 came out on the
cut-off day, so I took the previous one), openai 3.24.0, azure-identity 1.26.0, OpenTelemetry
api/sdk 1.44.0 (azure-monitor-opentelemetry-exporter 1.0.0b57 requires ~=1.44; that exporter has
only beta releases), fastapi 0.142.2, uvicorn 0.54.0, httpx 0.28.1, pydantic 2.13.5. Transitive
dependencies are resolved by pip. The deterministic engine needs none of them; CI installs them for
the tests.

**Steps B-D share one commit.** The phraser, the workflow and the spans/audit all touch the same
pipeline files (narrative, orchestrator, stream, run_match); splitting them into three commits would
have meant committing intermediate states that never ran. They are one commit, after all their tests
passed together.

**Step B (phrasing layer)**
- Current docs checked (Microsoft Learn, "Azure OpenAI ... Microsoft Entra ID"): `openai.AzureOpenAI`
  with `azure_ad_token_provider=get_bearer_token_provider(DefaultAzureCredential(),
  "https://cognitiveservices.azure.com/.default")`; the role to grant is Cognitive Services OpenAI
  User. API-key fallback only when `AZURE_OPENAI_API_KEY` is set; the key is never logged.
- **The model writes only the casual tone.** The analyst tone stays the exact template: it is the
  precise wording the dashboard's ledger and the number tracer were built around, and keeping it fixed
  halves the guarded surface. Phrasing metadata (source, rejections) goes to the agent log, the span
  and the audit record, not into the insight contract, so contracts/ did not change.
- Function-word language check: tuned until every template sentence of every key and tone reads as
  its own language (a test enforces it), so the guard never rejects what the engine itself says.
- With no Azure settings, `--phraser azure` runs offline: cache only, else template, with
  `guard_rejected: "no model client (offline)"` recorded. Its stream equals the template stream.
- Golden stream for the equality tests: the committed replay `web/public/data/insights.jsonl`
  (latency field excluded).

**Step C (Agent Framework workflow)**
- Checked the installed 1.20.0 API directly: `WorkflowBuilder(start_executor=..., max_iterations=...,
  output_from=[...])`, `add_edge(src, dst, condition=callable)`, `Executor(id)` with `@handler`
  methods typed `(msg, ctx: WorkflowContext[Out])` / `WorkflowContext[Out, WorkflowOut]`,
  `await workflow.run(msg)` -> `.get_outputs()`, `@tool` -> `FunctionTool.invoke(arguments=...,
  skip_parsing=True)`. One difference from older samples: the start executor is a keyword argument
  of the builder (no `set_start_executor`).
- One run per ingested batch, proposals released one at a time, so the order equals the direct
  pipeline; `max_iterations` 100000 (one superstep per hop; the finish batch has the most hops).
- The function tools are called by the Verifier executor itself and only logged; the verdict is
  `engine.verifier`, unchanged. No model gets tools.

**Step D (telemetry, audit)**
- `use_provider()` in agents/telemetry.py: OpenTelemetry lets the global provider be set once per
  process, and `run_match` sets it, so tests inject an in-memory provider instead.
- The Azure Monitor exporter branch is exercised with a well-formed fake connection string (the
  exporter is built, nothing is sent); export to a real Application Insights resource is "built, not
  verified live".
- Audit is opt-in (`run_match --audit FILE`), since an append-only file grows on every run.

**Step E (service and UI wiring)**
- `service/app.py` (FastAPI): `/healthz`, `/api/matches`, `/api/match/{id}/stream` (SSE replay of the
  verified `insights.jsonl` at `speed` match seconds per second, `start`, a `tick` every 30 match
  seconds, `end`), `/api/claims/{id}` (the attempt chain), web/dist mounted at `/`. No CORS
  middleware, no OpenAPI/docs routes, config from env (`OPTIX_DATA_DIR`, `OPTIX_WEB_DIST`,
  `OPTIX_MAX_SPEED`). The service replays; it never computes or phrases.
- Tests drive the app through httpx's ASGI transport. That transport buffers a streamed body, so the
  timing test runs the replay generator directly on a fake clock (every insight frame is sent when
  elapsed = start_sec / speed); the HTTP tests check content, order and limits.
- **No 404 on static hosting:** the page probes `./healthz`. On a static host that is the file
  `web/public/healthz` (`"service": "static-replay"`), so the probe never fails and the browser gate
  needed no exception; only the API answers `"service": "optix"`.
- **Honest live mode:** in Live stream mode the feed is rebuilt from the insights actually received
  (not the preloaded file), and the clock is capped at the server's clock, so the page cannot show an
  insight before the server sent it. The board, deck and evidence still come from ui.json.
- Gate: `check_live_stream` runs the real API with uvicorn on a free local port, serves the build,
  waits for three cards over SSE, and fails on any request to another origin; the static run must
  show Replay.
- E3 (Event Hubs adapter) not built: optional, and the time went to the gates.

**Step F (container and IaC; build and lint only)**
- Dockerfile: node 22.20.0 (bookworm-slim) builds web/dist; python 3.13.7-slim runs
  `uvicorn service.app:app` on 8000 as uid 10001, HEALTHCHECK on /healthz, only
  requirements-azure.txt installed. docker-compose binds 127.0.0.1:8000, read-only root, optional `.env`.
- **Not built here:** the Docker CLI exists but its daemon was not running, and starting Docker
  Desktop was outside the brief. **Not linted here:** neither `az` nor `bicep` is installed.
  `tests/test_infra.py` checks the files statically instead (multi-stage, non-root, healthcheck,
  exact base-image versions, one role assignment, no keys, nothing in CI/tools runs a deploy).
- Bicep (infra/main.bicep): Log Analytics + workspace-based Application Insights, Container Apps
  environment + app with a system-assigned identity, and one role assignment, **Cognitive Services
  OpenAI User** (5e0bd9bd-7b93-4f28-af87-19fc36ad61bd, checked on the Learn built-in roles page),
  scoped to one existing Azure OpenAI / Foundry account. API versions: containerApps and
  managedEnvironments 2026-07-01 (latest GA on Learn), workspaces 2023-09-01, components
  2020-02-02, roleAssignments 2022-04-01. The App Insights connection string is passed as a Container
  Apps secret, not a plain env value. infra/deploy.md lists the commands for you; none were run.

**Step G (live check)**
- **Not run: no Azure configuration present.** No `AZURE_OPENAI_*` variables, no `.env`, and no Azure
  CLI on this machine, so `tools/azure_live_check.py` wrote docs/azure-live-check.md saying so, with
  the steps. Zero live calls were made in this whole run.
- Live tests (`tests/test_azure_live.py`) carry the `azure_live` marker and a skip condition; they
  are the only skips in the default suite (2) and are reported separately. The live tool caps itself
  at 10 calls (the phraser's process cap is 60).

**Step H (docs and pitch)**
- One source for the status: `agents/azure_status.py` derives each component's state from facts
  (files exist; the tests that exercise it exist; the live report does not say "Not run"). It writes
  docs/AZURE.md (Mermaid diagram + table) and the README block between markers, and
  `dashboard_data` puts the same list in ui.json (`azure_status`), which the Tech Blueprint renders in
  place of the old "Planned Azure integration" panel. `tests/test_azure_status.py` fails if any of
  the three drifts. The status texts contain no digit, so the number tracer has nothing to trace.
- Components whose only tests use a fake or a static read (the Azure OpenAI client, the Application
  Insights exporter, the container, the Bicep) are "built, not verified live", not "verified by
  tests". The container row says the image was not built here.
- A status note first said "prediction words"; the dashboard's forbidden-word gate (which also
  covers the Tech page) would flag it, so it reads "talk of future results".
- PITCH.md (298 words) and DEMO_SCRIPT.md (110 s, nine shots, text names only, no logos, no music,
  ends with the repo URL).
- Secret scan: `tools/secret_scan.py` (tracked tree; `--history` every blob in git history), with a
  test that plants secrets built at run time; CI runs the tree scan. The all-zero instrumentation key
  used to build the exporter in a test is allowed explicitly.

## Visuals polish (branch `ui-visuals-polish`, from `ui-visuals` = main 32730c4)

Green start: default suite 168 passed; `npm run build` ok.

### Polish decisions

- **Wide breakpoint:** `wide` = 1600 px (`--breakpoint-wide: 100rem`). Below it nothing changes.
- **Rhythm strip under the scrubber at wide widths:** the rhythm pulse shares the match's time axis,
  so it runs full width under the transport instead of under the pitch; that is what makes the
  first screen fit at 1600x900. Grid at wide: pitch | Perimeter Lock, gauges, momentum | shot
  quality over the stream (rows `auto auto auto 1fr`, the widget wrappers use `display: contents`
  so each panel is placed directly).
- **Dropped at wide only, to fit 900 px:** the subtitles of the pitch, Perimeter Lock, rhythm,
  gauges and shot panel; the gauges' first note sentence; the second sentence of the rhythm
  caption. Captions, aria labels and the hidden tables keep the explanation. The pitch caption
  card (the drawn insight's sentence, the same as the stream's top card) is hidden at wide unless
  the screen is at least 1000 px tall, so it shows at 1920x1080. The pitch is capped to the
  viewport height (`100vh - 560px`, `- 680px` with the caption card).
- **Compacted at wide:** scoreboard padding and score size, gauge height, shot blocks (118 px max).
- **Momentum chart** is not one of the required visuals (the tug-of-war bar in the scoreboard is);
  at wide it sits under the gauges and starts on the first screen at 1080p.
- **V4 default view:** the 8 busiest routes; "Show all routes (N)" restores the previous full set
  (forward routes with at least 2 passes; every chance route). Bend 5% of the route length (was
  12%) plus a 1.1-unit offset to the right of travel. Ties are broken by start zone, end zone,
  then kind, in the page and in the Python check, so the top 8 are the same set in both.
- **Arrowheads** are larger and drawn past the line end with a dark outline, so direction reads on
  thick routes.

### Test changes

- `check_web.check_consistency`: the pass-route check runs on the default view (8 busiest routes)
  and again after clicking "Show all routes"; each view must match the data in count, pass counts
  and width order. Not weakened: the full set is still checked, and the default view is new.
- `check_web.MUTATIONS`: new "routes default view" mutation (the busiest route +3 passes per player)
  that must fail the default view; the "routes" mutation must now fail the full view. Mutation
  copies are refreshed from the current build each run (a reused copy could serve a stale build).
- New `check_web.check_first_screen`: at 1920x1080 and 1600x900 the Focus Pitch, Perimeter Lock,
  tug-of-war bar, gauges, rhythm pulse, shot panel and the stream's header are wholly inside the
  first viewport; no overlapping text; SVG text at least 11 px.
- Enforced budgets (were only reported): replay p95 at most 20 ms, now measured at 1440x900 and at
  1920x1080; initial JS under 250 KB gzip.
- `tests/test_dashboard.py`: asserts the first-screen report, both route views and both frame runs.
- Vitest: top-8 cut, tie order, and the lane offset of a route and its reverse.

## Visuals (branch `ui-visuals`, from `ui-v2`)

Started 2026-10-22 18:23. Football-native visuals in web/, each drawing a metric or claim the
engine already produces. The audit is docs/visuals-plan.md; each visual is described in
docs/visuals.md.

### Visuals decisions

- **Branch base:** main does not contain web/, so ui-visuals was branched from ui-v2. Green start:
  default suite 166 passed, `npm run build` ok. The preview server from the previous session was
  stopped first so builds and tests run alone.
- **Export (agents/dashboard_data.py, allowed as a plain export):** a `visuals` section with the
  showcase match's shots (location, xG, result), `engine.flow.territorial_stress` spells per team,
  `engine.flow.rhythm` per minute (run per period, because minutes 45-49 exist in both halves),
  leading and trailing field tilt and press intensity from `engine.profiles.team_style_profile`,
  and per player the forward passes and key passes grouped by start and end zone with xT added
  (`threat.value_at`) and xA. Plus `head_to_head[].claim.lane` (the lane the claim object names).
  No new metric, no engine change. Tests: tests/test_dashboard_data.py (two new tests).
- **ui.json size:** with the export it was 1.17 MB; run_match now writes it with compact
  separators (1.02 MB). It is still just over 1 MB; committed as is (already minified).
- **V3 axes:** field tilt (territory) and press intensity (pressure events per opponent pass).
  Ball-won height was the first choice for "sitting deep", but its sample is under the minimum in
  several leading states (AUR leading: 49 ball-winning events); press intensity has hundreds of
  observations per state and the engine documents that a team that leads and sits deep presses
  less. Minimum sample per state: n >= 50 on both metrics, the engine's medium-confidence sample
  size (metrics.CONF_MEDIUM_N).
- **V5 is ADAPT:** the engine's territorial stress is "a team keeping the ball in the opponent's
  half" (x >= 50, no on-ball event by the other side). The gauge shows, per team, the cumulative
  seconds of the opponent's spells: time pinned in its own half, not its own third.
- **V9 and V11 are SKIP:** no per-match player values exist; the showcase has no red card (two
  yellows).
- **V8 percentiles:** computed in the page from the engine's per-player values (documented formula,
  unit-tested, recomputed independently in Python by the consistency gate). Comparison group:
  outfield players with at least 100 passes.

- **V4 colour changed during the build:** the plan coloured forward routes by xT added per pass, but
  the volume passer's xT per pass (0.009) equals the league's, so he did not read grey. The export
  gained a per-route count of passes ending in a high-threat cell (`hot`) and the league share
  (`league_hot_share`); routes are coloured by route pass quality, the engine's own
  `pass_quality_ratio` definition. A test rebuilds each player's ratio from the routes. Forward
  routes with one pass are hidden (caption gives shown / total). Chances keep xA per chance.
- **V7 pin:** clicking a node in the evidence chain pins that event on the drawer's pitch (the
  table below stays the text version).
- **V10 built (Tier 3):** from `track` (the showcase's on-ball event locations, attacker frame),
  share per zone per half and the shift in points; on the Team Board for the two showcase teams.
  No export change.
- **Tug-of-war:** the label says who is pulling, with no number (the brief forbids a raw
  percentage).
- **V3 tick numbers removed:** axis ticks would be numbers not in the data; exact values are in the
  value cards and the hidden table.
- **Placement:** the matchup and xG cards on Live carry compact crosshairs and shot blocks; the
  Player Deck context cards carry compact pass routes; Tech has a visual guide.
- **Lazy loading:** the pages were already lazy chunks; each visual lives in its route's chunk
  (initial JS unchanged at 149 KB gzip).

### Test changes (and why)

- `tools/check_web.py`: the number tracer accepts the visuals' documented formulas (recomputed in
  Python, not read from the page); new `check_consistency` (V1, V2, V5, V4, V8 against the engine
  output) and `mutation_proof`; screenshots go to docs/screens-v3/; `--ref` and
  `--mutation-proof` flags.
- `tools/check_dashboard.py`: "60,000" and "60000" join the forbidden words.
- `tests/test_dashboard.py`: runs check_web with `ref_dir` = the fresh engine output and asserts the
  consistency report.
- `tests/test_visuals_consistency.py` (new, slow): every consistency check fails on a throwaway
  copy with that visual's data changed.
- `tests/test_dashboard_data.py`: two tests tie the `visuals` export to the engine functions and
  show the planted volume passer and corner specialist read differently.
- Vitest: `lib/viz.test.ts` and `components/viz/helpers.test.ts` cover every geometry and scale
  function. No convex hull exists (V11 is skipped), so none is tested.
- The crosshair table had two "League" headers (React duplicate key warning); renamed.

## UI v2 (branch `ui-v2`, from `ui-restructure`)

Started 2026-10-22 16:17. The front end is rebuilt in web/ (Vite + React + TypeScript). The data
generator, engine, Verifier, Translator and contracts are unchanged. web/ is now the current UI;
app/ and legacy/ are deprecated and kept for reference (docs/dashboard.md has the stack and how to run).

Pages: Live Center, Team Board, Player Deck, Tech Blueprint and the settings tray, all built.

Gate results (Node 23.4.0, npm 10.9.2; each run alone):
- `npm run lint`, `npm run typecheck`, `npm test` (18 Vitest tests), `npm run build`: pass.
- `python -m tools.check_web`, every route at 1440 and 390 px: no console errors, failed or
  non-localhost requests; no horizontal scroll; 0 overlapping text; 0 untraced numbers; Tab reaches
  every control; Tailwind applied; axe: 0 serious or critical (and 0 moderate or minor); data
  attributes present. Evidence drawer: exact event ids for 5 cards incl. rewrites. In-app
  navigation through every route at both widths: no errors. Language switch: 35 cards, no number
  changed, number guard passes in en/es/fr, every route's numbers equal in en and fr. Storage
  blocked and reduced motion: pass.
- Replay at fast speed: p50 16.7 ms, p95 16.7 ms, max 16.8 ms, 0 long tasks.
- Initial JS: 149.0 KB gzip (budget 250 KB); pages are lazy chunks.
- Default Python suite: 166 passed. Slow `tests/test_dashboard.py` (web) 4 passed,
  `tests/test_dashboard_legacy.py` (app/) 3 passed.
- Screenshots: docs/screens-v2/ (8 route shots plus live_1080p.png, each under 300 KB).

Dependencies (exact):
- dependencies: @fontsource-variable/inter 5.3.0, @fontsource/barlow-condensed 5.3.0,
  @radix-ui/react-dialog 1.2.0, @radix-ui/react-slider 1.5.0, @radix-ui/react-switch 1.3.8,
  @radix-ui/react-tabs 1.1.22, @radix-ui/react-toggle 1.1.19, @radix-ui/react-toggle-group 1.1.20,
  @radix-ui/react-tooltip 1.3.0, d3-scale 4.0.2, d3-shape 3.2.0, motion 12.43.0, react 19.3.0,
  react-dom 19.3.0, react-router 7.18.4, zustand 5.0.15.
- devDependencies: @eslint/js 9.39.5, @tailwindcss/vite 4.3.3, @testing-library/dom 10.4.2,
  @testing-library/react 16.3.3, @types/d3-scale 4.0.9, @types/d3-shape 3.2.0, @types/node 22.20.5,
  @types/react 19.3.0, @types/react-dom 19.3.0, @vitejs/plugin-react 5.2.0, axe-core 4.14.0,
  eslint 9.39.5, eslint-plugin-react-hooks 7.1.1, globals 17.13.0, jsdom 26.1.0,
  json-schema-to-typescript 16.0.0, prettier 3.9.9, tailwindcss 4.3.3, typescript 5.9.3,
  typescript-eslint 8.71.1, vite 7.3.7, vitest 3.2.7.

### UI v2 decisions

- **Branch base:** main does not contain ui-restructure (main is at 189e9f9), so ui-v2 was branched
  from ui-restructure, as instructed. Default suite before starting: 158 passed.
- **Data files:** out/ui.json does not hold the stream (the brief assumed it did). The stream is
  out/insights.jsonl, every verification attempt is out/claims.jsonl, and teams, goals, periods and
  momentum are out/timeline.json. `npm run data` copies all four, byte for byte, into
  web/public/data/ (committed). Sizes: ui.json 965 KB (under 1 MB, so copied as is, not minified),
  insights.jsonl 72 KB, claims.jsonl 50 KB, timeline.json 5.5 KB. No Python code changed.
- **Versions:** every direct dependency is pinned exactly, and the install used
  `npm install --before=2026-10-08`, so transitive dependencies are also at least two weeks old.
  Where a brand-new major had appeared in the last weeks (react-router 8, motion 14, TypeScript 7,
  Vite 8, ESLint 10, Vitest 5), I pinned the newest release of the previous major, whose APIs I
  could rely on unattended. npm prints a deprecation notice on eslint 9.39.5 ("no longer
  supported"); it works and is the newest 9.x.
- **Dependencies beyond the named stack, and why:** @vitejs/plugin-react and @tailwindcss/vite (the
  Vite plugins); @radix-ui/react-toggle-group (the segmented controls: speed, density, language,
  Before / After; a sibling of the Toggle primitive); jsdom (Vitest's DOM environment);
  @testing-library/dom (peer of React Testing Library); @eslint/js, typescript-eslint,
  eslint-plugin-react-hooks and globals (the ESLint config); @types/react, @types/react-dom,
  @types/d3-scale, @types/d3-shape and @types/node (types). TanStack Query was skipped: the data
  is four static files loaded once. clsx, tailwind-merge and class-variance-authority were skipped
  too; a one-line `cx` helper is enough.
- **Fonts:** Inter (variable, UI) and Barlow Condensed 600/700 (scores and big numerals), both OFL,
  self-hosted through Fontsource and emitted as files by Vite (`assetsInlineLimit: 0`).
- **Honest labels:** the match header says "Replay", not "Live": it is a synthetic match replayed
  from the stream. The Perimeter Lock map legend says the grey dots are "other final-third passes
  in the evidence" (the claim's evidence is a sample of up to 15 events, not every pass).
- **Phone layout:** the team names are hidden under 640 px (the codes stay, and the names are in the
  header's accessible label) so neither truncates.
- **Tab gate:** a Radix roving-focus group (toggle group, tab list) is one Tab stop: Tab lands on
  the root or on its active item, and arrow keys move inside. The web checker therefore counts focus
  on the nearest checked ancestor (tools/check_web.py, WEB_ACTIVE_JS), so the group counts as
  reached. tools/check_dashboard._tab_order gained an optional argument for this; the legacy
  behaviour is unchanged.
- **Navigation bug found by the language gate:** navigating inside the app crashed ("destroy_ is
  not a function"): the scroll-to-top effect returned `window.scrollTo(...)`, which returns a
  promise in this Chromium, and React called it as the cleanup. Fixed with a block body, and a new
  navigation gate (tools/check_web.check_navigation) clicks the nav links through every route at
  both widths; it was run against the old build and reports the crash.
- **Tech Blueprint:** the walkthrough follows the earliest rewritten claim in the stream from its
  blocked attempt to the published sentences in three languages; the report intros keep their
  markdown code spans as `<code>`. Every number on the page comes from ui.json (ledger, rewrites,
  measured) or claims.jsonl.
- **CI:** .github/workflows/ci.yml runs the default Python suite, then web `npm ci --ignore-scripts`,
  lint, typecheck, test and build on Node LTS. No secrets. The slow browser tests stay local
  (CI has no Chromium set up by this repo).
- **Number trace:** one documented formula was added for web/: the per-type counts of an insight's
  evidence events (the card's evidence summary, "15 events (pass 12, shot 3)").
- **Settings key:** `optix.settings.v2` (the legacy app keeps `optix.settings.v1`).

### Test changes

- **tests/test_ui_stack.py:** the "no package.json, lockfile, bundler config or node_modules" rule
  now applies to app/ and legacy/ (the deprecated no-build UIs), plus a new check that no such file
  exists anywhere outside web/. Reason: web/ is the new Vite build and needs package.json, a
  lockfile and a bundler config; the rule belonged to the no-build UI. Every app/ check (remote
  URLs, CDN names, import map, VENDOR.md checksums, plain CSS background) is unchanged.
- **tests/test_web_stack.py (new, default suite):** exact versions and a committed lockfile that
  matches package.json; node_modules and dist never tracked; no remote URL in web/src, index.html
  or a built web/dist; no CDN names and self-hosted fonts only; plain CSS body background and the
  colour tokens; web/public/data holds the four engine files, identical to out/ when out/ exists.
- **tests/test_dashboard.py (slow):** now runs every tools/check_web gate on a copy of the built
  web/dist with a freshly streamed match. Reason: web/ passes every gate and replaces app/. The
  previous app/ test moved unchanged to **tests/test_dashboard_legacy.py** (slow); nothing was
  deleted or weakened. It skips (slow suite only) when web/dist or web/node_modules is missing.
- **tests/test_number_trace.py:** one new test proves the tracer on the committed web data: a real
  headline traces, and the same headline with an invented number is caught.

## UI restructure (branch `ui-restructure`)

The dashboard is rebuilt as a no-build React app: React 18.3.1, htm 3.1.1 and the Tailwind 4.1.11
browser build, all as native ES modules vendored in app/vendor/ (VENDOR.md has checksums and
licences). It has hash routes #/live, #/teams, #/players and #/tech, a settings slide-over, and
native SVG for every chart and pitch. Details are in docs/dashboard.md. The Preact fallback was not
needed: esm.sh produced self-contained React and ReactDOM builds whose only import is the bare
"react".

Gate results (`python -m tools.check_dashboard`, every route at 1440 and 390 px):
- no console errors, failed requests or non-localhost requests;
- no horizontal scroll and no overlapping text;
- Tab reaches every control (19-36 per view);
- Tailwind applied;
- the evidence drawer lists exactly the claim's event ids;
- 0 untraced numbers;
- the language switch changes no number on 35 cards, and the number guard is clean;
- no forbidden words;
- storage blocked and reduced motion both work.

Replay at fast speed: 240 frames in 4 s, mean 16.7 ms, p95 16.8 ms, max 16.8 ms, 0 long tasks.

Test changes:
- **tests/test_dashboard.py** (slow) was rewritten for the new UI. It runs every gate above on a
  freshly streamed match. The old test checked views of the old page (#feed .card, ?select=...).
  Those no longer exist.
- **New, default suite:**
  - tests/test_ui_stack.py: no package.json, lockfile, bundler config or node_modules; no remote
    URL in an import, script src, link href, CSS url(), @import or fetch; import map targets and
    relative imports exist; VENDOR.md covers every file with a matching SHA-256;
  - tests/test_dashboard_data.py: the ui.json ledger and rewrites; the number guard on original
    wordings; rule reasons; planted styles on the Team Board; planted players on the Player Deck;
    evidence rows; parsed reports;
  - tests/test_number_trace.py: the number tracer catches invented numbers and ids.

## Unattended decisions

- **Phase 0, per-league sanity bound:** a league fails only when the Wilson 95% upper bound of its
  recall is below the bound (e.g. 0.30 for field-tilt full-match claims). That way a small n
  cannot flake, while a collapse (0/25) still fails.
- **Phase 0, pooled floors:** asserted only when the test pool holds at least 3 leagues. A run
  with a single league (OPTIX_VERIFIER_SEEDS=2029) prints the pooled figure and checks only the
  per-league bounds.
- **Phase 0 results** (`.venv/bin/python -m pytest`): default 141 passed, 0 skipped; slow 20
  passed, 0 skipped (the dashboard test ran). Pooled recall on true cases:
  - claim level: shot_spam 85/96 = 0.89 [0.81-0.93], field_tilt 56/105 = 0.53 [0.44-0.63];
  - pipeline level: shot_spam 86/96 = 0.90 [0.82-0.94], field_tilt 91/105 = 0.87 [0.79-0.92].

- **Phase A, docs honesty:** the README said language models write sentences; it now says templates
  do, and adds a "Not built yet (planned)" section (Azure, Event Hubs, Application Insights, Agent
  Framework, LLM phrasing). Measured full-league figures were corrected to 800,670 events, 121 MB and
  about 15 s (the docs had about 750,000 events, 110 MB and 20 s). The ARCHITECTURE example "76%" is
  now 76.3%, the value the stream writes. engine.md's unplanted fire rates now match
  docs/verifier-recall.md (16.0% pipeline, 3.2% claim level). The NTG->NTG rename and the "0x"
  template wording were left for the Azure step, as instructed.
- **Phase A, pyproject.toml** is pytest configuration, not a bundler or build config. It stays, and
  the no-build test does not flag it.
- **Phase A, .gitignore** now also covers .claude/settings.local.json, .cache/, *.log and archives.
- **Phase B, the old dashboard** (app/app.js, style.css, index.html and its screenshots) was moved
  with `git mv` to legacy/dashboard-v1/, not deleted. It is not served or tested.
- **Phase B, data for the new pages** comes from one new file, out/ui.json, written by
  agents/dashboard_data.py inside agents.run_match, so the quickstart is unchanged. Two new engine
  pieces document their definitions and limits: `metrics.involvement` and `metrics.pass_completion`
  for the Player Deck, and `engine/style_labels.py` for the Team Board label rules.
- **Phase B, label rule:** a style label shows only when the 95% interval excludes the league average
  AND the gap is at least 3 pp (shares) or 5% (means). Otherwise the label reads "typical".
- **Phase B, "original wording" of a rewritten card** is the blocked attempt's own claim
  (template_key and params), rendered by the same templates and checked by the number guard. The
  "why" sentence is a new `_rules` block in agents/templates/{en,es,fr}.json: one plain sentence per
  rule, no numbers.
- **Phase B, language:** the switch changes the insight sentences (the stream's translated,
  number-guarded outputs) and the main interface strings. Team Board, Player Deck and Tech page
  explanations stay in English.
- **Phase B, ball marker** on the Focus Pitch is the location of the latest on-ball event, flipped
  into the frame of the team shown. It is labelled an event-based proxy, not tracking (rule 6).
- **Phase B, speed control** uses words (Slow / Normal / Fast = 10 / 30 / 90 match seconds per
  second) so no un-sourced number appears on screen.
- **Phase B, number trace:** a number on screen passes when it is in the data: any number in
  out/*.json*, any number inside a string there, or the length of a list or object there, which
  covers "15 events". Football clock times (mm:ss, 45+m) derived from clock seconds also pass.
  Id-like words (event ids, player ids) must be strings in the data.
- **Phase B, the Tailwind browser build prints a console warning** ("should not be used in
  production"). It is a warning, not an error, and the gate counts errors only. The no-build stack
  requires this build.
- **Phase B, Pillow** was added to requirements-ui.txt to keep screenshots under 300 KB
  (palette-quantised PNG).
- **Phase B, a stray empty directory /tmp/x** was created by mistake during a check. It holds
  nothing and was left in place (no rm).

## Verifier recall: diagnosis and fixes for the match-level rules

Tool: `python -m tools.verifier_recall --json F --out docs/verifier-recall.md`. It runs one full
league at a time in a fresh child process (about 2 minutes and 1.9 GB each) and writes F after
every league. Full tables, miss classes and examples are in docs/verifier-recall.md. Case
definitions are in tests/verifier_cases.py. Seeds 2026-2028 were used to choose the changes;
2029-2030 are the hold-out.

**Changes**
1. **shot_spam** counts non-penalty shots only. A penalty's xG of 0.78 was lifting the mean of a
   dozen speculative shots over the 0.08 cap.
2. **field_tilt_with_lead** takes the box-entry share over the trailing part of the scope. On a
   full-match claim, box entries from level spells diluted the pattern; this was category (b) for
   the claims.
3. **The Analyst** proposes a full-time field-tilt window when the last one ended at least 15
   minutes before the whistle. The 30-minute cooldown was skipping the closing push in stoppage
   time, which was category (b) for the pipeline.
4. **field_tilt_with_lead** stays quiet when the chaser clearly out-created an average chaser
   from real chances. "Real chances" means non-penalty shots above 0.08 xG. "Clearly" means above
   the league's 75th percentile for scopes of that length, against the same time in each game
   state. This uses the new `metrics.chaser_threat` and `metrics.chaser_threat_line`. It removes
   the real false positives (see docs/engine.md, "Reading the field tilt caveat").

**Before (v2) and after (current code), pooled over five leagues.** Recall is on true cases with
Wilson 95% intervals and the number of true cases. "FP" is the share of all unplanted cases whose
fires are real false positives by the total-xG outcome label.

| Rule | Level | Seeds | Recall before | Recall after | Unplanted fire rate before → after | FP before → after |
|---|---|---|---|---|---|---|
| shot_spam | claim | tune | 0.81 [0.69-0.90] (44/54) | 0.87 [0.76-0.94] (47/54) | 0.051 → 0.053 | – |
| shot_spam | claim | hold-out | 0.88 [0.75-0.95] (37/42) | 0.90 [0.78-0.96] (38/42) | 0.045 → 0.051 | – |
| shot_spam | pipeline | tune | 0.85 [0.73-0.92] (46/54) | 0.89 [0.78-0.95] (48/54) | 0.052 → 0.054 | – |
| shot_spam | pipeline | hold-out | 0.88 [0.75-0.95] (37/42) | 0.90 [0.78-0.96] (38/42) | 0.049 → 0.054 | – |
| field_tilt | claim | tune | 0.75 [0.63-0.84] (45/60) | 0.62 [0.49-0.73] (37/60) | 0.042 → 0.035 | 0.013 → 0.004 |
| field_tilt | claim | hold-out | 0.64 [0.50-0.77] (29/45) | 0.42 [0.29-0.57] (19/45) | 0.035 → 0.027 | 0.010 → 0.001 |
| field_tilt | pipeline | tune | 0.95 [0.86-0.98] (57/60) | 0.90 [0.80-0.95] (54/60) | 0.180 → 0.158 | 0.041 → 0.005 |
| field_tilt | pipeline | hold-out | 0.89 [0.77-0.95] (40/45) | 0.82 [0.69-0.91] (37/45) | 0.176 → 0.163 | 0.038 → 0.006 |

- **Recall over all planted cases**, including those below detection, after the changes:
  - shot_spam: 0.68 (claim) and 0.68 (pipeline) of 149;
  - field_tilt: 0.52 (claim) and 0.87 (pipeline) of 107.
- **The 17.8% Analyst-pipeline rate before the changes**, as shares of all 3230 unplanted cases:
  - 11.0% justified: the chaser made no more xG than an average chaser;
  - 2.8% unclear;
  - 4.0% real false positives.
  - After the changes the rate is 16.0%, with 0.5% real false positives.
- **Changes 1-3 alone** (v3 in docs/verifier-recall.md):
  - field_tilt claim-level recall rose 0.70 → 0.80;
  - pipeline recall rose 0.92 → 0.94;
  - unplanted rates stayed under 6% on claims;
  - but real false positives rose to 5.0% in the pipeline.
- **Change 4** trades recall for honesty:
  - The dropped planted cases are chasers of a deep block that still beat the league's 75th
    percentile from real chances. For those, "territory, not threat" would mislead.
  - Claim-level field-tilt recall falls below where it was before all of these changes.
- **Rejected** (offline estimates on the tuning seeds):
  - a trailing-spell alternative for shot_spam, which pushed unplanted fires to 6.1-6.4%;
  - judging tilt on the trailing part only, at 6.0-7.1%;
  - gating on the league average instead of the 75th percentile: pipeline recall 0.75, claim recall 0.41.
- **The old-code numbers** are not a fresh run of the old code. A /tmp cleanup wiped the stored
  diagnosis, so the old rules were re-applied to the scopes recorded by the new run. This works
  because the Analyst's windows do not depend on the rules; the old full-time cooldown is
  reproduced by dropping the extra window. The rebuilt numbers match the earlier measurements
  exactly, e.g. seed 2026 shot_spam 21/31, field_tilt 15/16, unplanted 32/646 and 24/646.

**Miss classes after the changes, pipeline level, all five leagues**
- shot_spam:
  - (a) 0;
  - (b) 3: the full-match claim dilutes the trailing spell, and the fix was rejected for its false fires;
  - (c) 7: mean xG over 0.08 from a few good chances;
  - (d) 37: 32 with fewer than 12 non-penalty shots while trailing.
- field_tilt:
  - (a) 1;
  - (b) 0;
  - (c) 13, of which 8 were held back by the threat condition;
  - (d) 0.

**Decision (human): keep change 4.** The pipeline is what users see, and it improved: real false
positives fell 4.0% → 0.5%, and recall is 0.90 on the tuning seeds and 0.82 on the hold-out.

**Hold-out vs tuning.** Change 4's 75th-percentile line was chosen on seeds 2026-2028. Field-tilt
recall on one full-match claim per team is 0.62 [0.49-0.73] (n=60) on those seeds but
0.42 [0.29-0.57] (n=45) on the hold-out 2029-2030. Quote the hold-out figure. The full explanation
is in docs/engine.md and docs/verifier-recall.md.

**Dashboard test.** The project venv (`.venv`, Python 3.13) already has playwright, and the dashboard
test runs and passes with `.venv/bin/python`. The earlier skip came from running the suites with
the Anaconda `python` on PATH, which has no playwright. Nothing was reinstalled. Run the suites
with `.venv/bin/python -m pytest`.

## 3C. Multi-seed robustness

Tool: `python -m tools.robustness` (about 20 minutes on 6 processes; `--json F --reuse` skips seeds
already measured). Full tables: docs/robustness.md.

- **Small league, 10 seeds (2026-2035):** 9 of 10 seeds have all 38 applicable targets in range.
  The one miss is goals_dispersion on seed 2035 (1.63). No target fails on more than 2 seeds.
  Caveat: with 40 matches the sampling allowance is wide, so values such as a 0.125 draw share
  still pass. The small league is a weak test of realism; the full league is the real one.
- **Full league, seeds 2026 / 2027 / 2028:**
  - 47/47 targets in range on every seed.
  - Champion points 84 / 86 / 93; bottom 21 / 25 / 24. With 2029 and 2030 added, the champion
    range is 84-93.
  - Every planted volume passer (4), corner specialist (4), shot-spam team (3) and
    deep-when-leading team (3) is recovered on every seed.
  - Soft lanes: 6/6 with a true effect of at least 7 pp are found on every seed, with 0/12 false
    positives. The two weak plants, IRK (0.3, about 2.6 pp) and RVD (0.6, about 5.2 pp), are never
    found. That is expected, because they are below the stated recoverable size.
- **Showcase search from offset 0:**
  - 2026 finds 4-1 at try 1384, with a minimum margin of 14%. This matches SHOWCASE_SEARCH_START.
  - 2027 finds 2-0 at try 2724, with a minimum margin of 11%.
  - 2028 finds 1-1 at try 1090, with a minimum margin of 10%.
  - The tightest thresholds are shot_spam.low_xg_share and chaser_field_tilt. A 1-1 showcase would
    have no lead for the field-tilt story to sit on for long, so only 2026 and 2027 give a natural
    demo.
- **Verifier, pooled (Wilson 95% intervals):**
  - With 3 seeds:
    - shot_spam recall 0.64 (0.53-0.73), 88 true cases, false-fire rate 0.051;
    - field_tilt_with_lead recall 0.73 (0.60-0.82), 62 cases, false-fire rate 0.042.
  - With 5 seeds (2029 and 2030 added only for pooling):
    - shot_spam 0.64 (0.56-0.71), 149 cases;
    - field_tilt_with_lead 0.69 (0.60-0.77), 107 cases.
  - set_piece_inflation and wide_forward_passes: recall 1.00 on all 20 plants. False-fire rates are
    0.041 and 0.001; precision is 0.22 and 0.91.
  - The player rules cannot reach 75 true cases: each league plants only 4 of each, so 75 would need
    about 19 leagues.
- **Needs human review:**
  - The comment in `tests/test_verifier_full.py` gives recall as 13/25 and 22/28. That is stale: the
    test itself now prints 21/31 and 15/16 on seed 2026.
  - The field_tilt recall floor of 0.65 holds on seed 2026 only by luck (0.94). Seeds 2027, 2029 and
    2030 measure 0.57, 0.56 and 0.75.
  - Recommendation: pin the floors to the pooled lower bounds (shot_spam about 0.55, field_tilt
    about 0.60) and run that test on more than one seed. Not changed here.

## Realism v2: summary (read this first)

Branch `realism-v2` (tag `pre-realism-v2` marks the start). Commits: Stage 0 (fc34094),
Stages 1-6 (2d3b6fa), Stages 7-8 (767cc7b and the final docs commit). Nothing pushed or merged.
Default suite: 141 passed. Slow suite: 18 passed (full league, Verifier precision/recall,
pooled seeds, showcase search from zero, dashboard).

**What changed**
- Fixtures: circle-method calendar with dates, kick-off slots, international breaks and two
  midweek rounds; at most 2 home or 2 away in a row.
- Squads of 24 with formations by style, `lineups.csv`, 2-5 substitutions, minutes played, bans
  after a red card or a fifth yellow, light rotation, injuries.
- The ball: failed passes end as interceptions, blocks, tackles, out of play or loose balls; duels,
  carries, dribbles, clearances, saves, claims; throw-ins, goal kicks, corners, free kicks and
  penalties; players and ball never teleport.
- Chances: headers, inside-box share, on-target share, distance, penalties and set-piece goals in
  range; xG calibrated by bin.
- Dead balls and time: fouls, cards, offsides, stoppage time, ball in play, late goals.
- League: bounded, correlated dials; champion and bottom points, correlations in range.
- Tests: `tests/test_realism.py`; report: `python -m tools.realism_report` ->
  `docs/realism-report.md`.
- Engine and agents: PPDA counts fouls; ball-won height counts won tackles only; soft-lane gate
  compares lifts against each lane's own league rate; shot_spam and field_tilt_with_lead retuned;
  half-time summaries at the half-time whistle; momentum series cut at the claim window.
- Dashboard: football time (45+x, 90+x), plays to the final whistle, the evidence drawer shows the
  fouled or incoming player; screenshots in `docs/screens/` refreshed.

**Before / after (full league, seed 2026; v1 = the v1 generator measured with today's definitions)**

| Target | Range | v1 | v2 |
|---|---|---|---|
| goals_per_match | 2.6-3.3 | 2.805 | 2.937 ok |
| draw_share | 0.2-0.28 | 0.261 | 0.263 ok |
| goals_dispersion | 0.95-1.3 | 0.982 | 1.266 ok |
| shots_per_team | 11.0-14.0 | 12.2 | 12.7 ok |
| on_target_share | 0.32-0.37 | 0.410 | 0.350 ok |
| inside_box_share | 0.6-0.72 | 0.773 | 0.691 ok |
| header_share | 0.11-0.19 | 0.399 | 0.152 ok |
| mean_shot_distance_m | 15.5-18.5 | 15.7 | 17.8 ok |
| penalties_per_match | 0.2-0.32 | 0.000 | 0.279 ok |
| set_piece_goal_share | 0.2-0.33 | 0.073 | 0.225 ok |
| passes_per_team | 400.0-520.0 | 554.1 | 445.8 ok |
| pass_accuracy | 0.79-0.85 | 0.786 | 0.790 ok |
| back_pass_share | 0.1-0.2 | 0.054 | 0.163 ok |
| final_third_pass_share | 0.18-0.3 | 0.409 | 0.293 ok |
| interceptions_per_team | 7.0-12.0 | 96.6 | 10.5 ok |
| clearances_per_team | 14.0-26.0 | 0.000 | 17.5 ok |
| fouls_per_team | 9.5-12.5 | 0.000 | 9.815 ok |
| yellows_per_match | 3.3-4.6 | 0.000 | 4.053 ok |
| reds_per_match | 0.04-0.15 | 0.000 | 0.124 ok |
| offsides_per_team | 1.4-2.6 | 0.000 | 1.949 ok |
| added_time_first_half_min | 1.0-4.0 | 0.000 | 3.703 ok |
| added_time_second_half_min | 4.0-10.0 | 0.000 | 7.930 ok |
| ball_in_play_min | 54.0-60.0 | 90.0 | 59.3 ok |
| subs_per_team | 3.0-5.0 | 0.000 | 4.392 ok |
| ppda_league | 8.0-16.0 | 6.264 | 14.4 ok |
| possession_sd_pp | 5.0-8.5 | 3.854 | 5.602 ok |
| players_used_per_team | 20.0-30.0 | 11.0 | 22.4 ok |
| corr_possession_shots | 0.3-1.0 | -0.392 | 0.644 ok |
| corr_ppda_possession | -1.0--0.2 | 0.113 | -0.439 ok |

Every one of the 47 targets is in range on the small and the full league (`docs/realism-report.md`
has all of them, the xG bins, goal timing and correlations). **Targets still outside range: none.**

**Traps and rules that changed behaviour**
- All five traps still fire in the showcase with margin >= 10% (seed 20261383, AUR 4-1 NTG) and
  are rediscovered from events alone. The engine reads no ground truth.
- Field-tilt trap: volume gate 100 -> 60 final-third passes (realistic final-third volume). The
  flank trap is checked against the season's completion rate for that lane.
- NTG's weak lane is planted at strength 1.5; opponents aim at a known soft side.
- CAL (the dominant negative control) and VES (both wings) dials were sharpened so their styles stay
  recognisable under the new ball model.
- shot_spam: >= 12 shots, >= 65% low xG, mean <= 0.08; field_tilt_with_lead: entry cap 18%. Recall
  on the v2 full league 0.52 and 0.79, non-trap fire rates under 5%.
- Soft lanes: 4 pp minimum lift plus a lift-based own-lanes z >= 2.33.

**Decisions**: see "Decisions (realism v2)" below. **Test changes**: see "Test changes (realism v2)"
below; none weakened a requirement, several raised one.

**Needs human review**
- Season luck is large in a 5-team, 40-match league. Several tests run on the one seed (2026).
  During tuning, single-seed checks (CAL control, soft lanes, the season field-tilt firing,
  dispersion) flipped with unrelated changes. All pass now, but they could flip again on a
  simulator change. Consider running those checks over several seeds.
- Champion points on the full league range from 77 to 95 across seeds (target 78-95; the brief said
  80-92). Seed 2026 has 88.
- Verifier recall moved by up to 0.15 between simulator builds (25-30 positives per rule). The
  floors sit about one sampling SD below the current measurement.
- The showcase is now a 4-1 (previously 2-1). The traps and story still hold. A future seed search
  could prefer closer scores if the demo needs one.
- The showcase's NTG match PPDA is high (31.4): AUR sit deep and NTG press little in this match.
  It is published with press intensity alongside (ppda_alone), but worth a look on screen.
- Stated as approximate: most v2 ranges are wide football-knowledge ranges (see
  `data_gen/calibration.py` SOURCES); only goals, results, fouls, cards, penalties, set pieces,
  added time, ball in play and late goals cite public pages.
- Not modelled (optional per the brief): injuries are simple (fixed absence), rotation is light,
  goalkeeper distribution is basic.

## Realism v2 (branch `realism-v2`, from `overnight`; tag `pre-realism-v2`)

Started 2026-10-21 18:24.

### Stage 0. Housekeeping
- (a) docs/realism-audit.md rewritten: only our own measurements, public-source ranges (with URLs)
  and ranges marked "approximate". No third-party event data, numbers derived from it, or scripts
  that fetch it remain in the repo or the working tree.
- (b) data_gen/calibration.py: 47 range targets for the recent era (2022/23-2024/25), each with a
  source note and a per-observation SD for a sampling allowance (2 sd / sqrt(n)). The 38/30/32
  outcome point target is replaced by ranges (home 40-49%, draw 20-28%, away 28-36%).
  `NOT_YET_MODELLED` lists the 27 targets the v1 generator misses on the full league (plus goal
  dispersion, missed on the pooled small seasons); later stages remove entries.
- Tests: 122 passed by default.

### Stages 1-6. Fixtures, squads, the ball, chances, dead balls, league structure
Committed as one stage (see Decisions). Summary:
- Stage 1, fixtures: `data_gen/schedule.py`. Circle method, Berger home/away alternation, the second
  half of the season mirrored, at most 2 home or 2 away in a row, weekend slots from 15 Aug 2026 to
  22 May 2027, international breaks and two midweek rounds. The small league plays the 5-team double
  round robin twice (40 matches). tests/test_schedule.py.
- Stage 2, squads: `data_gen/squads.py`. 24-player squads (formation XI + 2 GK, 4 DF, 4 MF, 3 FW),
  formations by style (4-3-3, 4-2-3-1, 4-4-2, 3-5-2, 4-1-4-1), a unique name pool per league,
  `lineups.csv`, 2-5 substitutions per team (mostly 55-85', earlier when trailing or after a red),
  minutes played, a one-match ban after a red or a fifth yellow, light rotation after short rest,
  injuries with forced subs. Trap players and goalkeepers are never rested or subbed off for tactics.
- Stage 3, the ball: failed passes end as interceptions, out of play, blocks, tackles on reception,
  clearances or loose balls; duels, carries, dribbles, clearances and blocks; goal kicks, throw-ins,
  build-up from the goalkeeper and centre-backs; back passes and pass lengths in range; position
  continuity with a teleport guard (reach 6 + 8 m/s); style drives volume; PPDA in range.
- Stage 4, chances: headers, shots in the box, on target, distance, penalties, set-piece goals and
  cross completion in range; goalkeeper saves and claims; xG refitted per bin.
- Stage 5, dead balls and time: fouls, cards (a booked player is more careful), offsides, red cards
  change behaviour (the side down a player defends deeper), stoppage time from stoppages, ball in
  play, goal timing rising late in each half. Contracts unchanged (the new event types already fit).
- Stage 6, league: bounded, correlated dials from a quality score; PLQ and LMF defy their strength;
  champion and bottom points in range; correlation signs as targets.
- Calibration: every target passes on the small league (seed 2026 and seeds 1-5 pooled) and on the
  full league (seeds 2026 and 7). `NOT_YET_MODELLED` is empty.
- Verifier retune on the v2 full league (seed 2026, 1345 cases): shot_spam >= 12 shots, >= 65% low xG,
  mean <= 0.08 (recall 0.40 -> 0.52, non-trap rate 3.3% -> 4.8%); field_tilt_with_lead entry cap
  15% -> 18% (recall 0.64 -> 0.79, non-trap rate 1.1% -> 3.6%). Recall moved by up to 0.15 between
  simulator builds during tuning (25-30 positives per rule), so the test floors sit about one SD below.
- Showcase: seed 20260957 (958 tries), AUR 2-1 NTG (goals 18', 47', 78'); every trap fires with
  margin >= 10%.

### Stage 7-8 (partial). Realism tests, report, downstream repair
- tests/test_realism.py: 14 default tests on the small league (every range, fixtures, lineups,
  players on the pitch, 11 v 10 after a red, subs match lineups, minutes add up, bans, no player
  teleports, ball continuity, restart spots, referential integrity, unique names, determinism) and
  6 slow ones on the full league (the same checks plus xG by bin, goals variance/mean, late goals,
  correlation signs including press vs PPDA). tools/realism_report.py writes docs/realism-report.md
  (with a v1 column from docs/realism-v1-measured.json). Every target is in range on both leagues.
- Generator bugs found by these tests and fixed: a player substituted at a dead ball could take the
  free kick; kick-offs could start with a dribble; keepers' last position was dropped after a pass
  (no reach check); keeper saves and claims at a fixed spot could be out of reach (now pulled
  within reach, using no random numbers); injuries were logged at the centre spot; dribble, tackle
  and carry events lost the sequence's play pattern.
- goals_dispersion sampling SD 1.0 -> 1.41 (the variance/mean ratio of n Poisson counts has SD about
  sqrt(2/n)); the slow test still requires 0.95-1.3 on the full league with no allowance.
- Soft-lane own-lanes gate now compares lifts over each lane's league rate (lanes have different
  baselines); NTG found on 8/8 seeds, HAR 7/8, no false positives.
- Engine: PPDA counts fouls (standard definition); ball-won height counts won tackles only.
- Showcase now seed 20261383 (1384 tries), AUR 4-1 NTG, all margins >= 10%.
- Test changes: test_data_gen attacking-output clone test 30 -> 100 matches a side (30 was
  underpowered; true ratio about 1.8); test_dashboard reads the final score from ground truth
  instead of a literal "2 – 1".
- Docs: data-dictionary.md, engine.md and ARCHITECTURE.md updated for v2.
- Screenshots refreshed (python -m tools.check_dashboard): every view loads with no console error,
  failed request or horizontal scroll.

### Decisions (realism v2)
- Era for "realistic": recent seasons 2022/23-2024/25 as instructed; where those seasons differ a lot
  (goals 2.85-3.28, yellows 3.4-5.1) the range spans them.
- Sampling allowance instead of separate small/full tolerances: one range per target, widened by
  2 sd / sqrt(n) for the sample size actually measured.
- Season-shape targets (correlations across teams, points of champion and bottom team, possession SD,
  pass-volume spread, players used) apply only to the 20-team league (`min_teams`).

- Stage 1 committed together with Stages 2-6: the v1 small-league recovery tests pass only on the
  old fixture draw, so the new calendar and the rewritten simulator had to land together for the
  suite to be green at each commit.
- Field tilt spell length: `traps.FIELD_TILT_MIN_F3` 100 -> 60 final-third passes. With realistic
  final-third volume (about a quarter of passes), 100 passes in a leading spell is rare even for a
  dominant chaser; 60 keeps the trap clear of noise.
- NTG's weak lane is planted at strength 1.5 (`weak_strength`) and opponents aim at a known soft side
  (near side only); after a completed entry into the weak lane, box passes and shot appetite rise
  slightly (`via_weak`). The soft-lane truth helper formula (0.09 x strength) is unchanged.
- The flank trap's completion check compares against the season reference completion for that lane,
  not only the other end of the same match (one match is too small a sample).
- CAL dials raised (att 1.08, dfn 1.06, press 0.90, directness 0.58, attacking output 1.25) so the
  negative control "dominant, not a tilt trap" is neither vacuous nor failing: at output 1.10 CAL's
  box-entry share in its level-or-ahead high-tilt spells ranged 0.09-0.27 over 8 seeds (half the
  seeds had a spell under the 15% gate); now 0.15-0.36 on all 8.
- Result shape: CHASE_URGENCY 0.8 -> 0.5 and SHOT_RATE_BOX 0.135 -> 0.14. A strong trailing-side
  urgency fed equalisers, so draws ran at 31-33% on the full league. Raising shot volume alone
  pushed small-league shots per team over range. Checked on full seeds 2026 and 7 and the small
  league (seed 2026 and seeds 1-5 pooled).
- Soft-lane own-lanes gate z 1.64 -> 2.33 (one-sided 5%, Bonferroni for 5 lanes): AUR's
  left_half_space was flagged on seeds 2 and 2026 (z 1.69, 2.23); every planted lane that 1.64
  found has z >= 2.75 across 8 seeds.
- Half-time summaries fire on the first-half `half_end` event (after stoppage time), not at 2700 s.
- The dashboard shows football time from the timeline's new `periods` (45+3, 90+6); the scrub runs
  to the last event. The evidence drawer shows `related_player_id` (fouled player, player on).
- Momentum payload series is cut at the claim's window end (a long stoppage could put the
  triggering event a minute later, so the series' last point disagreed with the claim).
- Volume passer usage 1.4 (was higher): at the old usage the passer led the league by an implausible
  margin.
- Showcase realism envelope: the search also requires <= 30 shots per team, <= 6 goals and >= 250
  passes per team; NTG's left winger gets delivery 1.4 in the showcase only.
- Soft-lane rule: the lane must also beat the team's own other lanes (two-proportion z >= 1.64), and
  the minimum gap fell 6 -> 4 pp. Without the own-lanes gate, a deep block made every lane look soft
  against AUR.
- New play patterns `throw_in` and `goal_kick`, new shot types `penalty` and `free_kick`; the
  `related_player_id` column carries the player fouled, the player coming on and the duel opponent.
- New template `matchup.weak_lane` (en/es/fr): the top matchup can now be a half-space, not a flank.
- Verifier thresholds retuned on the full league (numbers in the stage note). Lower precision is
  accepted: non-trap fires are real low-quality volume or real trailing territory, still true context.

### Test changes (realism v2)
- **Verifier recall work, tests/test_verifier_full.py**, rewritten on tests/verifier_cases.py:
  - **Seed:** the league seed is selectable (OPTIX_VERIFIER_SEED, default 2026).
  - **True cases:** recall is asserted on true cases, meaning planted cases minus those below
    detection (fewer than 12 non-penalty shots, or no extra low-xG shots, while trailing; fewer
    than 30 final-third passes, or under 60% tilt, while trailing). Recall on all planted cases
    is printed.
  - **Pipeline level:** recall and fire rate are now also checked on the claims the Analyst
    proposes while streaming each match.
  - **Floors:** set just under the pooled Wilson lower bounds over seeds 2026-2030:
    - claim level: shot_spam 0.80 (was 0.42 on all planted cases), field_tilt 0.43 (was 0.65);
    - pipeline level: shot_spam 0.81, field_tilt 0.78.
  - **Why the field-tilt claim floor went down:** the requirement changed. The rule now
    deliberately stays quiet on chasers that made clearly more than an average chaser from real
    chances.
  - **Pipeline caps:** the field-tilt pipeline unplanted rate is capped at 20%, since the Analyst
    proposes several windows per match. Real false positives (total-xG label) are capped at 2% of
    unplanted cases.
  - **Player rules:** they now require every plant caught (4 per league), as before (recall 1.0).
  - **Stale comment:** the comment that gave 13/25 and 22/28 is gone; it now gives the pooled
    numbers.
  - **Runs:** the slow test was run on seeds 2026 (pass) and 2029. On 2029, claim-level field-tilt
    recall is 0.40 against the 0.43 pooled floor, so it failed. Superseded by the next entry.
- **tests/test_verifier_full.py: pooled floors on pooled data, sanity bounds per league.**
  - **The error:** the floors are pooled bounds, so asserting them on a single league was wrong.
    A league has only 14-25 true cases per rule, so one case moves recall by about 0.04. Seed
    2029's 10/25 = 0.40 sits under 0.43 by one case, with a Wilson interval of 0.23-0.59 that
    easily contains the pooled 0.53.
  - **Pooled floors:** the test now generates every league in OPTIX_VERIFIER_SEEDS, by default
    2026-2030, the leagues the floors came from. Each runs in a fresh process, one at a time. The
    floors are asserted on recall pooled across those leagues, and only when the pool holds at
    least 3 leagues. The floors are unchanged: claim shot_spam 0.80, field_tilt 0.43; pipeline
    0.81 and 0.78.
  - **Per-league sanity bounds:** each league gets a wide bound, failed only when its whole Wilson
    95% interval lies below it, so small n cannot flake. Claim-level field_tilt has 0.30; the
    others 0.60.
  - **Unchanged per league:** the non-trap caps, the real-false-positive cap and the player-rule
    checks.
  - **No floor was lowered.**
- **test_verifier.py `test_field_tilt_rule_silent_on_high_territory_with_box_entries`:** unchanged
  and still passing. It selects full-match claims by the whole-match box-entry share, while the
  rule now looks at the trailing part only. A claim with many box entries overall but few while
  trailing could now fire, but none of those in the small league does.
- test_data_gen.py `test_season_meets_calibration_targets`, test_full_league.py
  `test_full_league_meets_calibration`: targets are now ranges with an allowance; the tests allow
  failures only from `calibration.NOT_YET_MODELLED` (a ratchet; tests/test_realism.py will require
  it empty). Reason: the targets changed (Stage 0b), and v1 cannot meet the new ones until later
  stages.
- `test_ground_truth_records_expected_targets`: expected targets have no point value any more
  (ranges only, never a point), so the "target inside tolerance" check became "lo < hi, source
  recorded".
- `test_calibration_is_not_a_lucky_seed` (slow): pools five other seeds' seasons (200 matches) and
  checks the same targets, instead of "mean within a band around the point target" (no point targets
  any more). It now builds the seasons without the showcase search, which made it take 6 minutes.

- test_data_gen.py `test_shape`: 120 players, 24 per team, unique names (squads are now 24, Stage 2).
- test_data_gen.py `test_events_are_clean`: the last clock is between 5400 and 5400 + 1200 s and the
  half_end periods are 1 and 2 (stoppage time now runs past 90:00).
- test_data_gen.py `test_field_tilt_does_not_fire_on_cal_dominance`: CAL only, with a 40-pass spell
  floor stated in the test (the trap default fell to 60, see Decisions).
- test_data_gen.py season firings test uses `traps.FIELD_TILT_MIN_F3` instead of a literal 100.
- test_engine.py: the second-half partition window is (2700, end of match) instead of (2700, 5400)
  (stoppage time); matchup confidence is recomputed as the minimum of the share and completion
  confidences and must be medium or high.
- test_full_league.py: `RECOVERABLE_EFFECT_PP` 7.0 (power reasoning in the comment, realistic
  final-third volume halves the sample); total events between 650k and 1M (richer event types).
- test_stream.py: insights start no later than the last event (stoppage time), not 5400.
- test_verifier.py `test_honest_claim_passes_and_verified_claim_validates`: AUR has six shots in the
  v2 showcase, so `small_sample_xg` rightly fires on its match xG; the honest claim is now AUR's
  season xG on the season data.
- test_verifier.py `test_field_tilt_rule_silent_on_high_territory_with_box_entries`: the "above the
  entry cap" filter uses the rule constant instead of a literal 15 (cap retuned to 18%).
- test_verifier_full.py `MIN_MATCH_RECALL`: shot_spam 0.40 -> 0.42, field_tilt_with_lead 0.45 -> 0.65,
  about one sampling SD below the retuned measurement (0.52, 0.79). A raise, not a weakening.
- test_agents.py `test_raw_field_tilt_claim_blocked_then_republished_with_context`: picks NTG's first
  tilt claim after AUR's first goal instead of NTG's first tilt claim. In the v2 showcase NTG's first
  claim covers 0-15' at 0-0, which is honest and published as is; the test now also asserts that.
- Calibration tests: `NOT_YET_MODELLED` is now empty, so they require every target.

## Overnight run (steps 0-10)

Branch: `overnight`. Started 2026-10-21 07:08 local, finished about 08:30. Steps 0-10 all done.
Nothing was cut from the priority list.

## Summary

**Built**
- Data: a 10%-margin showcase (smallest margin +12.1%), LF CSVs and a slow marker (step 0); a 20-team,
  380-match full league (682k events, about 17 s) with extra planted traps and their expected
  evidence. The small league stays byte-identical (step 2).
- Contracts: claim `scope`, `supporting_values`, interval / effect_pp / confidence / baseline_source,
  `check_param_numbers` (step 1), and `verification.revision_hint` (step 6).
- Engine: effect sizes with Wilson intervals and confidence labels (z only for ranking), soft lanes
  from conceded completion rate, season baselines for single matches, and a HAR diagnosis (true
  effect 7.3-9.0 pp, recovered on the full league; the stated recoverable size is 5 pp, with 7/7
  recovered and 0/12 false positives) (step 3). Also xT (12x8), pass quality, xA split,
  territorial stress, shot clusters, rhythm, momentum and milestones (step 4).
- Verifier (step 5): fact check that recomputes value and supporting values from the claim object
  and checks each evidence event; 9 context rules. On the full league every rule fires on 5% or
  fewer of non-trap cases. Corner specialist and volume passer recall is 4/4 each. Match-level
  recall is 0.46 for shot spam and 0.54 for field tilt, counting only matches where the trap's
  game state occurred.
- Agents (step 6): Ingest, Analyst, Verifier, Narrative, Personalization, an orchestrator, typed
  messages, a per-match state store and structured logs. Blocked claims are revised by rule and
  re-verified with attempt numbers.
- Insight stream (step 7): `python -m agents.run_match`. The showcase gives 34 insights, 12 blocked
  attempts revised, 0 dropped. Latency: median 4 ms, max 25 ms.
- Translation and personalization (step 8): hand-written es/fr for all 16 templates; a number
  guard per language (decimal comma); analyst/casual, favorite club, player focus, single metric.
- Dashboard (step 9): a static app/ with feed, evidence drawer, Focus Pitch, momentum tug-of-war,
  Perimeter Lock, standard vs honest stat, the blocked-then-rewritten strip, 3 languages,
  light/dark and reduced motion. Headless Chromium checks show 0 console errors on 8 views;
  screenshots are in docs/screens/.
- Docs and hardening (step 10): ARCHITECTURE.md (Mermaid diagram, roles, data flow, handoffs,
  requirement->code table), README with a 5-command quick start, dashboard.md. A clean clone in a
  fresh venv ran the 5 commands, the tests passed (122 passed, 1 module skipped without
  Playwright) and the dashboard checks were clean.
- Tests: 122 by default plus 12 slow, all passing (slow suite 3.5 minutes).

**Incomplete / not built**
- Cut-list items were not built as features: red card segment analysis, underperformance
  diagnosis, fatigue proxy, pounce events, ingest noise cleanup beyond dedup and missing fields.
  Their Verifier rules exist (causal_red_card, single_match_fatigue block such claims). The
  insight types red_card_segment, pounce_sequence, underperformance_stack and turning_point are
  never emitted.
- Shot clusters and territorial stress can be claimed and verified, but the Analyst has no trigger
  for them yet.
- npxG equals xG: the generator has no penalties.
- Azure deployment (build order 6) was outside this run.

**Decisions**: see "Decisions" below (every one is listed there, grouped by step).
**Needs human review**: see the section at the end (4 items).

## Steps

### Step 0. Housekeeping
- (a) CSVs are now written with `lineterminator="\n"`; regenerated; `git add` shows no CRLF warnings.
- (b) Showcase trap margins are computed by `data_gen.traps.trap_margins` and stored in
  `ground_truth.json` (`showcase.trap_margins`). Before: two thresholds were within 10%
  (spam low-xG share 0.769 vs 0.75, +2.6%; volume-passer wide share 0.86 vs 0.80, +7.5%).
  The seed search now requires every threshold cleared by >= 10% (`SHOWCASE_MIN_MARGIN`).
  New showcase: seed 20264547, AUR 2-1 NTG. Numbers: chaser tilt 0.762 (>=0.68, +12%), box
  entries 14 of 147 final-third passes (share 0.095 <= 0.15), 16 of 19 NTG shots low-xG (share
  0.842, mean xG 0.058), volume passer rank 1 with wide share 0.925, corner specialist 6 corner
  chances vs 0 open play, AUR left share 0.613 of 31 entries. Smallest margin +12.1%.
- (c) `@pytest.mark.slow` registered in pyproject.toml, deselected by default (`addopts = -m 'not slow'`).
  Run them with `pytest -m slow`, or everything with `pytest -m ""`.
- Tests: 41 passed, 2 slow deselected (both slow pass).

### Step 1. Contracts
- claim.schema.json: `scope` (season/match/window, required); `window` and a string `match_id` are
  required only for match/window (if/then); `supporting_values`; `value.interval`, `value.effect_pp`,
  `value.confidence`, `value.baseline_source`; `z_score` optional and documented as ranking-only.
- `contracts/checks.py: check_param_numbers()` enforces "every number in params equals value.amount or a
  supporting_values entry". Tests: a param number found nowhere is rejected; strings/bools ignored.
- Examples updated. The insight example's casual text dropped the number 1 (it said "once"), which the
  number guard would reject; rewritten so every numeric param appears in every rendering (new test).
- engine/matchup emits the new shape: scope season, no window, Wilson interval, effect_pp, confidence,
  supporting_values. Matchup ranking switched from summed z to summed percentage-point lift (z only
  breaks ties). Report shows shares with 95% CIs, pp lifts and confidence.
- Tests: 51 passed, 2 slow deselected.

### Step 2. 20-team league
- `--league small|full`. small is byte-identical to before (checked by sha1 on all 7 season files and
  all 7 showcase files). full: 20 teams, 380 matches, 682,215 events, 102 MB (events.csv 77 MB,
  passes.csv 30 MB), generated in 16-18 s.
- New `TeamSpec` fields with defaults (`weak_strength=1.0`, `archetype=""`) so the 5 teams are unchanged.
- Calibration on the full league, first run without tuning: home/draw/away 41.3/26.1/32.6%, 2.81 goals,
  65.5% one-goal-or-less, 24.3 shots, 10.4 corners. All inside tolerance.
- Engine: `tables.team_events()` indexes events by the matches a team played; profiles use it. A full-
  league profile bracket takes ~11 s (it was ~130 s before the index).
- Slow test `tests/test_full_league.py` (6 tests, ~60 s): totals and schedule, calibration, originals
  unchanged, fictional names, every archetype signal, every player trap, every team trap.
- Tests: 51 passed by default; slow: 8 (all pass).

### Step 3. Engine statistics
- Every profile comparison now has effect (pp for shares, units for means), 95% interval (Wilson /
  normal), confidence and n; z kept as an internal ranking signal only. Rationale in docs/engine.md.
- New metric `entry_completion_by_lane` (conceded entry completion rate by lane). `profiles.soft_lane()`
  uses it: largest lift >= 6 pp with the Wilson lower bound above the league rate.
- Matchup = attacker share lift + defender completion lift (pp). Claim supporting_values gain
  concede_completion, league_completion, completion_effect_pp, completion_attempts.
- HAR diagnosis: true effect of its plant (from the generator's logged success probabilities) is
  7.3-9.0 pp, the same as NTG's. Share missed it (opponents' lane habits swamp it); completion rate
  finds it on the full league (+7.2 pp, n=505) but not on the 40-match season (n=186, interval about
  +-6 pp). Stated recoverable size 5 pp: 7/7 recovered on the full league, 0/12 false positives.
- `load(dir, baseline="season", season_dir=...)`: single-match analyses use season baselines; a
  single match with a season baseline yields a scope "match" claim with baseline_source = season n.
  `engine.report --season-baseline DIR`.
- docs/engine.md explains why ball-won height and PPDA mislead for CAL; the ppda_alone rule refers to it.
- Tests: 54 passed by default; slow 10.

### Step 4. Remaining metrics
- engine/threat.py: xT grid (12x8, value = xG that possessions from a cell go on to produce, fitted on
  the baseline season, sparse cells borrow their column mean), xt_added per completed pass,
  pass_quality_ratio, threat_passes.
- engine/flow.py: xa_split, territorial_stress, shot_clusters, rhythm (15-value series), momentum,
  milestones (first goal in the dataset, 25/50/75/100 completed passes in a match).
- tests/test_engine_fixtures.py: every metric (old and new) on hand-built events with hand-worked
  answers, plus trap checks: NTG_07 pass_quality_ratio 0.19 (< 0.35), NTG_11 open-play xA per chance
  < 0.6 x league median.
- Bug found by a fixture and fixed: high_threat_cells counted every cell tied at the 75th-percentile
  cut, so a mostly-zero grid made every central cell "high threat".
- Tests: 70 passed by default; slow 10.

### Step 5. Verifier
- engine/claims.py: per-metric recompute registry (`compute`) and `build_claim` (pending claim objects
  with value, supporting_values, evidence, scope, game state). The Verifier and the Analyst share it.
- engine/verifier.py: fact check (evidence exists, each ID satisfies the metric definition and lies in
  scope, value and every supporting value recomputed within half a rounding step, params numbers
  backed) then context check (engine/rules/, 9 modules). Status published / published_with_context /
  blocked, rule_ids, context_note key, attempt number.
- matchup_claim now carries `defender_id` so the Verifier can recompute it.
- tests/test_verifier.py (20 tests): honest, tampered amount, tampered supporting value, unbacked param
  number, unknown, wrong-team and out-of-window evidence; every rule fires where the showcase plants
  it; nothing fires on CAL level/ahead windows with tilt >= 60%, on high tilt with box entries > 15%,
  or on CAL's top passer and CAL's shots.
- tests/test_verifier_full.py (slow) on the full league:

  | rule | TP | FN | FP | TN | recall | precision | non-trap fire rate |
  |---|---|---|---|---|---|---|---|
  | shot_spam (match, trap team trailing >= 45 min) | 11 | 13 | 32 | 614 | 0.46 | 0.26 | 5.0% |
  | field_tilt_with_lead (match, vs sit-deep, trailing >= 45 min) | 20 | 17 | 12 | 634 | 0.54 | 0.62 | 1.9% |
  | set_piece_inflation (season, players >= 4 chances) | 4 | 0 | 0 | 195 | 1.00 | 1.00 | 0% |
  | wide_forward_passes (season, players >= 15 fwd passes) | 4 | 0 | 0 | 216 | 1.00 | 1.00 | 0% |

  Every rule is under the 10% non-trap limit, so none was retuned.
- Speed: season player claims went from 0.45 s to 0.1 s (cached league share for pass_quality_ratio,
  evidence scanned from the team's matches only, no in-scope set for season claims).
- Tests: 90 passed by default; slow 11.

### Step 6. Agents
- agents/: messages.py (typed handoffs), state.py (per-match MatchState with rolling counters and a
  view of ingested events), log.py (structured JSON logs), ingest.py, analyst.py, verifier_agent.py,
  narrative.py + templates/en.json (analyst and casual per template_key), personalization.py,
  orchestrator.py. Handoffs documented in docs/ARCHITECTURE.md.
- Context rules now declare REQUIRES; a fired context rule whose params are missing blocks the claim
  with `verification.revision_hint` (contract change: schema, docs/contracts.md, test). The Analyst
  revises by rule and re-verifies with attempt + 1.
- Showcase stream: 36 published claims in 0.6 s, none dropped. NTG's raw field tilt claim is blocked
  by field_tilt_with_lead (attempt 1) and republished with context at attempt 2: "NTG hold 65.4% field
  tilt while chasing the game, but only 8 of 70 final-third passes reached the box."
- engine: `metrics.chances_by_player`; rhythm claims carry `minutes`; territorial_stress claims carry
  box_entries.
- tests/test_agents.py (13): ingest dedup/missing fields, stream with duplicates publishes the same,
  blocked -> revised -> published_with_context with the log sequence, every trap's strategy used,
  every published claim schema-valid and backed only by past events, causal dropped, tampered claim
  recomputed, Verifier sees only ingested events, templates contain no hard-coded numbers, number
  guard, personalization modes.
- Tests: 104 passed by default; slow 11.

### Step 7. Insight stream
- agents/insights.py: Published claim -> insight (schema-valid); final insight_type follows what the
  Verifier found (field_tilt_with_lead -> perimeter_lock, shot_spam / wide_forward_passes ->
  volume_vs_value, set_piece_inflation -> set_piece_inflation); context_chip when published_with_context;
  payload numbers only from the claim, points only from evidence events, series from engine.flow.
- agents/stream.py: InsightStream feeds one event at a time and measures latency from receiving the
  triggering event to the built insight. Pre-match work (season preview, baselines) runs in prepare().
- `python -m agents.run_match --match m_showcase --out out/insights.jsonl` writes insights.jsonl,
  claims.jsonl (every attempt, for the blocked-then-rewritten view) and agent_log.jsonl. out/ is
  git-ignored.
- Showcase: 34 insights, 12 blocked attempts revised, 0 dropped; latency median 4 ms, max 25 ms;
  slowest single event 16 ms.
- tests/test_stream.py (7): schema, order, chip iff with-context, numbers and points traced to the
  claim, planted traps reach the stream, latency < 1 s, runner outputs.
- Tests: 111 passed by default; slow 11.

### Step 8. Translation and personalization
- Hand-written Spanish and French for all 16 template keys (both tones), agents/templates/es.json and
  fr.json, plus translated lane labels (`_labels`). Rendering happens in the Narrative agent, only for
  verified claims, for every configured language.
- Number guard per language: numbers are written in the language's own form (decimal comma in es/fr)
  and every numeric param must appear in every rendered string, with no other number allowed.
- Personalization modes: analyst/casual, language (falls back to en), favorite club (marked and first
  at the same clock), player focus, single metric. CLI: `python -m agents.personalize --mode casual
  --lang es --player NTG_07`.
- Same moment, two tones (45:00, NTG trailing):
  - analyst: "NTG hold 65.4% field tilt while chasing the game, but only 8 of 70 final-third passes
    reached the box."
  - casual: "NTG have the ball up the pitch (65.4% of final-third passes) but just 8 of 70 got into
    the box."
  - casual, fr: "NTG a le ballon haut (65,4 % des passes dans le dernier tiers), mais seulement 8 sur
    70 sont entrées dans la surface."
- tests/test_translation.py (11): same keys and placeholders in all languages, every rendered string in
  the showcase stream passes the guard in its language, decimal comma and labels, the guard catches a
  changed number, no translation before verification, each personalization mode, CLI.
- Tests: 122 passed by default; slow 11.

### Step 9. Dashboard
- app/index.html, style.css, app.js: static, no build tooling. Plays the match on a clock; feed cards
  with badges, evidence drawer with every verification attempt, Focus Pitch SVG, momentum tug-of-war
  with hover, Perimeter Lock, standard vs honest stat, analyst/casual toggle, language selector,
  player focus filter, the blocked-then-rewritten strip on revised cards, light/dark, reduced motion.
- agents.run_match also writes out/timeline.json (teams, players, goals, engine momentum per minute)
  so the page computes nothing.
- engine/claims.py: field tilt evidence lists box entries first (the 15 cited events carry the point;
  before, a 75th-minute perimeter lock cited 15 passes and none of its 6 box entries).
- tools/check_dashboard.py + requirements-ui.txt (Playwright 1.64, cached Chromium build): 8 views, 0
  console errors, no horizontal scroll; screenshots in docs/screens/. Slow test tests/test_dashboard.py.
- docs/dashboard.md.
- Tests: 122 passed by default; slow 12.

### Step 10. Hardening and docs
- docs/ARCHITECTURE.md: Mermaid diagram, agent roles, data flow, handoffs, revision loop,
  requirement->code table. README: 5-command quick start plus optional commands.
- End-to-end from a clean clone (`git clone --branch overnight`, fresh venv, Python 3.13): generate,
  run_match and http.server all worked (every app and data file returned 200); 122 tests passed, and
  the dashboard check passed against the clone. Regenerating left the committed showcase unchanged.
- Full slow suite: 12 passed in 3.5 minutes.

## Decisions
- Showcase seed search starts from a recorded offset (`SHOWCASE_SEARCH_START = {2026: 4547}`) because
  a search from 0 with the 10% margin takes ~2 minutes and every test fixture regenerates the data.
  A slow test re-runs the search from 0 and checks it finds the same seed, so the hint only skips work.
- Slow tests chosen: multi-seed calibration and the search-from-zero check. The determinism test stays
  in the default run because it is the cheapest guard against non-determinism.

- `baseline_source` lives inside `value` (next to `baseline`), not at the claim top level: it
  describes the baseline.
- `match_id` became optional/nullable: a season claim (pre-match preview) is not about one match, but
  may name the match it previews. It stays required for scope match/window.
- Verifier "recompute from the evidence": a season claim's value is an aggregate over hundreds of
  events while evidence_event_ids is a sample (12). So the fact check recomputes value and
  supporting_values from scope + subject + metric over the tables, and checks that every evidence ID
  exists and individually satisfies the claim's definition (e.g. is an AUR final-third entry into the
  claimed lane). Applies to Step 5.
- Confidence labels for a share vs a baseline: high = n >= 200, 95% half-width <= 5 pp and the
  interval excludes the baseline; medium = n >= 50 and the interval excludes the baseline; else low.
  A matchup's confidence is the lower of its two sides.

- Full-league team identities are fixed by `FULL_LEAGUE_TEAM_SEED` (not by --seed), so the same 20 teams
  appear whatever match seed is used.
- `teams.csv` for the full league has 2 extra columns (`weak_strength`, `archetype`); the small league keeps
  its original columns so `small` stays byte-identical.
- Expected evidence written to match what the simulator really does: shot spam is conditioned on trailing
  (it only fires against a deep block); "sits deep when leading" is checked on field tilt only (JPH's press
  drop equals the league's); volume passers are "team's top forward passer, league top 10%".
- HAR (shot_spam 0.5, "shoots early and often") is not listed as a shot-spam trap: its trailing low-xG share
  is at the league's. The shot-spam trap threshold is shot_spam >= 0.6.

- Test change, not weakened: my Step 1 test asserted the AUR-NTG matchup confidence == "high". After
  the defender side switched to completion rate (as Step 3 asks), the correct label is "medium" because
  NTG's left-flank completion sample is 190 attempts (< 200). The assertion now pins "medium" exactly
  and also asserts why (completion attempts < 200 <= attacker n).
- Soft-lane threshold 6 pp (observed lift) with the stated recoverable true effect 5 pp: at 5 pp
  observed, ESF (center, +5.5) and JPH (left_flank, +4.9) would have been false positives on the
  full league.

- xT is a possession-value model (xG produced by the rest of the possession), not the iterative
  Markov xT; it is simpler, needs no transition matrix, and matches the step's description.
- Failed passes get 0 xT added (not minus the start value): losing the ball is reported separately.
- Momentum = 100 x (home - away) / (home + away) of exponentially decayed (half-life 5 min) positive
  xT added plus shot xG.

- Verifier: the fact check recomputes from the claim object's scope, subject and params, never from
  text. A claim may fire several rules; the context_note is the first blocking rule's (else the first
  context rule's). Rule order: blocking rules first.
- Precision/recall cases for match-level rules only count a trap team's match as positive when the
  game state the trap needs happened (trailing >= 45 minutes); other trap-team matches are excluded
  from both counts.
- shot_spam precision is 0.26 at match level, kept: the 32 "false positives" are unplanted teams that
  really did take 10+ shots with >= 75% at xG <= 0.08 in that match, which is exactly what the chip
  says. The non-trap rate (5%) is within the limit.

- Context rules block when the sentence lacks the context (REQUIRES missing) rather than only
  attaching a chip. Reason: the step 6 example ("raw NTG 71% field tilt claim blocked by
  field_tilt_with_lead and republished with a context note") needs a block, and a sentence that
  states the shallow number alone is the misleading thing. A chip alone would leave the headline
  misleading. The step 5 tests now assert both halves (raw -> blocked with hint; with context ->
  published_with_context).
- ppda_alone checks press_intensity in params (what the sentence shows), not supporting_values.
- The Analyst's first attempts are plain on purpose so the revision loop is visible and tested; in
  production it could ask for the context up front, with the same result.
- In-match verification uses the match dataset restricted to ingested events (a new Dataset view
  when events arrived), so caches keyed on the dataset are rebuilt per view; xT grid and league
  pass-quality share are cached on the season baseline, which views share.
- The Analyst's trigger thresholds (tilt >= 60%, xT added >= 0.025, momentum swing >= 40, pass
  milestones 50/75, cooldowns) are editorial choices for a readable feed, documented in analyst.py.

- The season preview (matchup) is computed before kickoff and emitted on the first event; its first
  run at kickoff cost 385 ms, which is pre-match work, not live latency.
- The preview insight's points are season events (its evidence), so the dashboard can draw them
  without loading the season.

- Spanish and French write decimals with a comma ("65,4 %"); the number guard compares numbers in
  each language's written form, so "1.1" in a French sentence counts as a wrong number.
- Translations avoid gendered wording for players (no pronouns), so they hold for any player.

- Dashboard data is read from out/ (git-ignored, regenerated by run_match) rather than committed, so it
  can never drift from the engine; screenshots in docs/screens/ are committed.
- No /opt/pw-browsers here; Playwright 1.64 from requirements-ui.txt used its cached Chromium. The
  checker falls back to /opt/pw-browsers or the local cache if the bundled revision is missing.
- Blocked claims are shown in the UI as structured data (template, rule, needed params), never as a
  rendered sentence: only verified claims are narrated.

## Surprises

- ESF (possession, shot_spam 0.8) shows LOWER low-xG share than the league over all minutes; the spam only
  shows when trailing. Expected evidence was stated conditionally rather than strengthening the plant.

- In the showcase match on its own, AUR's top lane mismatch against NTG is left_half_space (41.9% of
  AUR's entries, interval 26-59%), not left_flank: a single match is a small sample. The season
  preview claim is left_flank.

## Needs human review
- The Spanish and French templates are my own translations; a native speaker should review the
  football register (e.g. "field tilt" is kept as a loan term in es/fr analyst mode).
- When a volume passer has no forward pass into a central danger zone, the sentence reads "pass
  quality 0x the league rate". True, but a "none of them" phrasing would read better; it needs a
  template variant chosen on a value, which I did not add. (Resolved later: a value-chosen variant,
  see "Azure decisions".)
- tests/test_dashboard.py skips at import when Playwright is missing, so a default run without
  requirements-ui.txt reports "1 skipped". Harmless, but it could move to a conftest hook if a clean
  "0 skipped" matters.
- The original code `NOR` is also a common abbreviation of a real club's name. CLAUDE.md forbids real
  trademarks; a 3-letter code is probably fine, but I did not rename an existing team (that would change
  the small league and the showcase). Worth a human decision. (Resolved later: renamed to `NTG`, see
  "Azure decisions".)
