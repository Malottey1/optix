# Progress log

## Azure live (branch `ui-visuals-azure-live`, from 83bb967)

### Azure live decisions

- Telemetry export row: "verified live" now needs the live report's machine-read export line
  (`- application insights export: exported N spans, connection string set, result success`, N > 0).
  The live check writes that line from a recording wrapper around the Azure Monitor exporter. Spans
  captured in memory never count. The existing report has no such line, so the row is "built, not verified live".
- The committed ui.json was stale: it still showed the status from before the live check, and
  test_committed_ui_json_carries_the_same_status was failing on the tip. It was regenerated with
  run_match plus npm run data; only `azure_status` changed (phraser verified live, telemetry built).

- Per-100 rates: the output guard allows the literal "100" only when the claim has a numeric param
  whose name ends in _100 (`output_guard.allowed_literals`). The template number guard is unchanged.
  No claim parameter was renamed and no export changed.
- Prompt p3 added the "<value> per 100" wording. The single live-check re-run (3 calls) was still all
  rejected, because the model wrote the game state and window seconds as digits ("by 2 or more goals",
  "3120 seconds"). A 3-call diagnostic batch, counted in the 60-call cache budget, showed this. Prompt p4
  says context fields are described in words. Only prompt text changed; the guard did not.
- Phrasing cache: 49 published showcase claims, so all fit under the 60-call cap and none were skipped.
  Priority order: Fan top cards, revised, pattern, then stream order. `tools/phrase_cache.py` writes
  only data/phrasing-cache and a report outside the repo. web/public/data stays template-based.
- data/phrasing-cache is tracked (180 KB, under 300 KB). It holds guard-accepted sentences only and the
  deployment name, with no endpoint or secret. p2 and p3 entries from earlier runs stay (also guard-accepted).
- The shell accidentally ran a backticked command inside an unquoted heredoc
  (`python -m agents.run_match --phraser azure`). It failed at import before doing any work; git status
  and out/ == web/public/data confirmed nothing changed.

### Test changes (Azure live)

- tests/test_azure_status.py `test_ci_state_only_after_a_recorded_successful_run`: it now monkeypatches
  `live_check_ran` to False. The test is about CI alone, and its "phraser stays built" assertion
  assumed no live report existed; that assertion is unchanged. New tests: in-memory spans never verify
  the telemetry export, only a successful recorded export does, and the live check writes the record.

## Personalization (branch `ui-visuals-personalize`, from 7a60c6a; local tag `pre-personalize`)

### Personalization decisions

- Untracked files in git status at the start (docs/screens-v9 extras, web/tsconfig.tsbuildinfo) were
  generated output from earlier runs, not hand changes, so there was no "outside" commit; they stay untracked.
- Modes are `fan` / `analyst` in the new config. The older agents/personalization.py (casual /
  analyst, CLI agents.personalize) is left as it was; the service and web use engine/personalize.py.
- Fan ranking: `fan_priority` (turning-point types first), then clock, then id. Followed clubs go
  first. The live feed still lists the chosen cards newest first.
- Player involvement = the insight's `player_ids` or the player / related player of an evidence
  event. Only the first followed player is used. A followed player not in the match is ignored there.
- Metric families: momentum → momentum_shift; xG → set_piece_inflation, player_focus; rhythm →
  rhythm_wave; territorial stress → perimeter_lock. Field tilt, xT and PPDA have no time series, so
  they are not offered (`not_offered` in the config). Played matches carry only momentum.
- No league-typical reference exists for these series; the readout states that, not invented.
- The showcase event file is named `events-m_showcase.json` (not `m_showcase.events.json`), so the
  match-file globs `m_*.json` in tests/test_match_export.py and their schema checks stay unchanged.
  It is written by agents/showcase_events.py and by match_export; 65 KB, so matches/ is 2.85 MB of 3 MB.
  The full season export was not re-run (no other data file changed; data_gen untouched).
- check_web presets Analyst view for every existing check, because they were written for the full hub.
  New `hub_live_fan` / `hub_final_fan` routes run every route gate in Fan view. `--lean` keeps 1920x1080
  for Home and the hubs only, as this run's brief asks.
- Live wide layout: the view switch, following chip and metric picker sit in the hub's top strip.
- Entry JS grew about 4 KB gzip, mostly the new en/es/fr strings (Settings shows the view switch).
  The panels live in the hub, live and Home chunks.

### Test changes (personalize)

- web/src/App.test.tsx and web/src/features/hub/hub.test.tsx: a `beforeEach(() => setMode("analyst"))`.
  These suites test Analyst content (pager, chips, matchup, event log, Before / After), and Fan is now the
  default. No assertion changed. Fan view is tested in features/personal/personal.test.tsx.
- tests/test_personalize.py and tools/personalize_golden.py read the committed stream
  (web/public/data/insights.jsonl, byte-identical to out/ and the file the TypeScript twin reads)
  instead of the ignored out/ folder, which CI does not have. Goldens unchanged, no assertion changed.
  The Dockerfile's web stage also copies contracts/personalization.json, which the web build imports.

## Final UI (branch `ui-visuals-final-ui`, from a8ab229 = main = ui-visuals-ia; local tag `pre-final-ui`)

Item status is in docs/final-ui-progress.md; the audit and design notes in docs/final-ui-plan.md.

### Final UI decisions

- Start: main and ui-visuals-ia are the same commit (a8ab229). Green start: default suite exit 0,
  `npm run build` pass.
- Audit data source: the dashboard season data/generated (40 matches) and data/showcase; facts in
  docs/final-ui-plan.md section 1 and docs/data-dictionary.md "What the data can and cannot show".

- Nav: Home joins the primary nav (Home, Fixtures, Teams, Players); the logo still links home. Tech
  is reached from Settings ("Technical details", above the language switch) and from Home. The search
  button stays hidden until search ships (Step 8). The kits note now lives once, in Settings.
- Player profiles: exported pre-rounded (as shown) in ui.json `players[].profile`, so the number
  tracer matches them exactly; percentiles against position peers are computed in the export. Lists
  (defensive points, key passes, shots faced) go to lazy per-team `matches/players-<code>.json`.
- Rates and peer percentiles need at least 270 minutes (`MIN_MINUTES`); below that they are absent,
  not zero. Keepers get no outfield defensive block (`defence` absent), outfield players no `keeper`.
- Keeper attribution: saved shots by the save event's keeper; every shot faced (goals included) by
  the keeper on the pitch at the shot's clock (lineups on_sec/off_sec), which is the starting keeper
  except in the 3 matches with a keeper substitution. Long pass = at least 32 m (`LONG_PASS_M`).
- xA per chance is rounded half up on exact integer ten-thousandths (xa has four decimals), so a mean
  landing on a half rounds the same in the export and the tests.
- Pressure regains: no field; a sequence rule would be a new metric, so it is not exported.
- Match Hub (final): two columns from 1100 px (62/38). Left: scoreline, turning points, lineups,
  heat maps, matchup, event log. Right: one sticky "Insights and patterns" panel, height 100vh - 96 px,
  scrolling inside (focusable named region), tabs Insights / Patterns (family chips with icons under
  Patterns), 5 or 10 cards per page with Previous / Next and "Page k of n"; tab, family and page size
  remembered in module memory only. Below 1100 px the same panel is a section under the scoreline.
  Gap under Heat Maps at 1440: 2,248 px before, 16 px after (all section gaps 16 px at every size).
- Lineups facing each other: from 640 px one landscape pitch (home left attacking right, away
  mirrored); below 640 px two stacked pitches (labels never collide at 390). Markers: goal, yellow,
  red, substituted off, from the turning points.
- Matchup (Step 4): the claim is season level (the whole season, the same lane and numbers for every
  fixture of a pair), so the strips are season figures too, labelled "Season figures", and the
  sentence states the claim's own values. The right strip shows the defender's conceded entry-pass
  completion minus the league's, the measure the rule tests (not the share of entries conceded, which
  the old crosshair showed and which can show no gap on the claim lane). The thresholds are named
  constants in engine/matchup.py (MIN_ATTACK_PP, MIN_COMPLETION_PP, both 0, behaviour unchanged) and
  exported as ui teams.matchup_rule; the page and tests read them from there.
- Matchup display rule: the claim fires on 37 of 41 fixtures (90%). The brief's "three strongest
  insights by magnitude" has no common magnitude (most claims are counts, xG or shares with no
  baseline), so the display-only rule uses the claim's own confidence label: shown at medium or high
  only (MATCHUP_DISPLAY_CONFIDENCE). Result: 17 of 41 fixtures (41%), one direction each; the toggle
  appears only when two directions qualify. The Verifier and the stream are unchanged.
- Style against the league (Step 5): five rows (Tempo, Press, Passing, Territory, Counters) from
  the existing style labels; each row's two bars on one scale per measure, lowest to highest team
  in the league; chips from the numbers only: "Highest / Lowest of N" for a unique extreme, else
  "About average" within 3% of the league value (STYLE_TOLERANCE_REL, exported as ui teams.style_rule),
  else above / below. Tempo is the engine's seconds between passes (unit in the tooltip and View data).
  Club accent for the team bar, neutral grey for the league bar. Pizza removed from the board (the
  component stays for reuse).
- Word budgets after Step 5: the board copy was trimmed to stay within 180 (lineup note, lane-strip
  label, shorter chips, "vs" spoken only to screen readers) and the board's compact score-state tiles
  moved into a closed "View data" (the Tech page keeps them open). Boards: 167-178 words at 1440.
  Matchup copy trimmed to 60 words (budget 60). New budget: hub lineups at most 120 words (94-96).
- Live replay hub (showcase): its console already has its own two-column frame with the feed; kept
  unchanged, as the brief requires its behaviour to stay the same.

- Players (Step 6): deck cards show two stats by position (FW/MF goals and assists, DF tackles and
  interceptions, GK saves and save rate; goals and assists stand in when a profile part is missing).
  The console header adds minutes. Position panels: FW/MF chances panel and evidence drawer; DF
  defensive actions (season total, per ninety, per hundred opposition entries, percentile among
  same-position players with at least 270 minutes, bars around the peer median), action map with type
  toggles, progressive passing, the contributions definition once; GK shot-faced map (keeper frame,
  marker by result, size by xG), shot stopping, distribution. "Not available in event data" notes
  (ground duels, pressure regains, save location / post-shot quality, line-breaking passes) link to a
  new Tech "Limits" section (#/tech?s=limits).
- Passing routes caption: the brief's "Each line is one completed pass. Showing the N most
  progressive." is not true of this visual (routes group completed passes by start and end zone; the
  export has no per-pass rows for ordinary passes). The caption says "Each line is a route between two
  zones; its width is the number of completed passes on it." and keeps the busiest-first default and
  "Show all routes (N)". The three-item legend (forward / progressive / key pass) is not drawn for the
  same reason; single passes are listed for chances created in the drawer.
- Pizza: compared against players of the same listed position with at least 100 passes (was all
  outfield players); goalkeepers get their own group. Title "Against players in the same position".
- Chance drawer play button: #/match/<id>?t=<clock_sec>; the final hub opens its event log at the first
  logged event at or after that clock (logs are thinned, so the exact pass may not be listed).
- Checker: routes player_df (CAL_05), player_gk (CAL_01), chance_drawer (NTG_11, drawer open) and
  settings (sheet open) added; consistency recounts the defence map, the shots-faced map and the
  drawer rows and play links from the players-<code>.json lists; three new mutations.

- Home (Step 7): hero, headline, sub-line and buttons unchanged. Below it, a lazy chunk
  (HomeSections, which alone loads matches/m_showcase.json): the showcase strip (score from the match
  file header, goal / card / substitution marks from its turning points, a Live replay chip, Explore
  Match Hub), three key insights (homePicks: the first revised finding, then the first two passed
  findings of other types, stream order, sentences of at most 18 words, counters such as recap lines
  and milestones excluded), tiles (xG race from ui.visuals.shots, momentum from the timeline, a heat
  thumbnail of the home team's on-ball events in its own attacking frame, never two frames mixed),
  player spotlight (the showcase scorer with the most season goals), two validated pattern families
  seen in the showcase stream (no recall figures), five crests, and "Why trust Optix" (three
  statements, the revised count from the ledger). Page words below the hero: 211 (budget 260, a new
  data-page-budget that counts nested cards too); cards at most 29 (budget 30).
- Not done on Home: the nav pill sitting over the hero. The shell header stays a sticky bar above the
  hero; overlaying it would cover the hero's top on phones and move the first-screen geometry the
  gate measures. Open issue: the kept hero artwork shows generated faces, which the global rule
  ("no photographs or generated faces") forbids; the brief also says to keep the hero exactly, so it
  is unchanged and flagged for a decision.

- Search (Step 8): header button and Ctrl/Cmd+K open a Radix dialog (focus trapped, Escape closes,
  focus returns to the opener), a lazy chunk loaded on first open. Index from ui.json (teams, players,
  fixtures); every typed word must match, case- and accent-blind; groups teams, players, fixtures;
  inside a group a code match ranks first, then the start of a name, the start of a word, anywhere;
  at most 5 / 8 / 6 results per group. The shell now also receives the loaded model through
  DataContext (null until loaded) so the overlay can read it. Checker route "search" (Fixtures with
  the overlay open on "aur").

- Favourites (Step 9): a star toggle button (aria-pressed, named "Follow <name>", never inside the
  card link) on team cards, player cards and fixture rows; stored under optix.favourites.v1 in
  localStorage with try/catch on every read and write (blocked storage keeps them for the visit). A
  "Following" chip on Teams, Players and Fixtures (a fixture counts when starred or when a followed
  team plays). Settings has a Favourites section with "Clear favourites" and the note that they stay
  in this browser; no accounts are mentioned.

- Floating nav bar: the header is now a floating pill (720 px and up) and a bottom tab bar below
  720 px (it was 1024 px), per the nav design brief; docs/dashboard.md "Navigation" has the
  measurements. Two icons were added to the set in the sheet's style, fixtures (a calendar; Fixtures
  used the scrub icon) and search (moved from the interface glyphs). The nav items are plain Links:
  NavLink dropped our aria-current on sub-routes, so a match hub never announced Fixtures as the
  current page. The sub-line beside the wordmark is gone (the brief: wordmark, then a divider), and
  Search and Settings are icon buttons named by aria-label. The mint is the existing --accent
  (#37e6a8), not a new #2EE6A6, so the brand keeps one accent. Sticky offsets (hub insights panel,
  Live feed, scroll margins) moved from 80 to 100 px below the taller bar. The hero still starts
  below the bar; content scrolls behind it.

- Player Console pass map (follow-up brief): the zone-to-zone route arrows (fat strokes, the grey →
  green "central" scale and its legend, "Show all routes") are replaced by one thin line per pass.
  The data had no per-pass rows for ordinary passes, so the export (agents/player_profiles.py, not
  the generator) now writes each player's 25 completed forward passes that gained the most ground
  into players-<code>.json (`passes`, typed forward / progressive / key pass; +109 KB, match files
  2.79 MB of 3 MB). Every line is 2 px on screen; nothing is drawn at 3 px, since single passes have
  no "busiest". The Chances created tab and the chance drawer now share one line component: set
  piece gold, open play blue, a ring on the shot (filled for a goal); the drawer's per-kind colours
  became these two (the breakdown still lists each kind). Minutes show as whole numbers from a new
  `minutes_whole` (rounded half up in the export, so the tracer finds the shown figure). The
  context note reads "What the plain total hides." A player with no pattern gets a one-line note and
  the position panels move into the right column. Colours are tokens (--pass-*, --chance-*).

### Test changes (final UI)

- tests/test_dashboard.py: the checked Matchup pairs now equal the lane claims the hub shows (display
  confidence medium or high, Step 4's display-only rule) instead of every lane claim; the checker
  now compares the strips' outlines (both strips, claim lane only) and the rule's thresholds.
- web/src/features/teams/teams.test.tsx: the kits line is now expected 0 times on the Team Grid (it
  moved to Settings, per Step 1); shell.test.tsx checks it is in Settings.
- web/src/features/hub/hub.test.tsx: the final hub's section order is now insights, turning, lineups,
  heat, (matchup), log (the Step 3 layout); the matchup-only-with-a-claim assertion is unchanged.

- Pass map: players.test.tsx's "routes (top eight, then all)" test now checks the pass map line by
  line against the lists file (ids in draw order, 2 px, dot and head, caption count, legend); three
  new tests cover the chances tab, whole minutes plus the context note, and the no-pattern layout.
  tools/check_web.py replaces the route arrow checks with pass_map_problems and chance_map_problems,
  and the "routes" / "routes default view" mutations (ui.json visuals.routes, which the console no
  longer draws) with "pass map", "pass map count" and "chance map" mutations of the lists file;
  tests/test_dashboard.py asserts both tabs were checked line for line instead of the two route
  views. tests/test_player_profiles.py adds recomputes of the pass lists and whole minutes. The
  App.test "Tactical patterns" test (seven full renders) gets an explicit 15 s timeout: it ran
  1.8 s alone but crossed Vitest's 5 s default in a parallel run; its assertions are unchanged.

- Nav bar: web/src/icons/icons.test.tsx and tests/test_icons.py expect 56 icons (fixtures and search
  added to the navigation group, as docs/icons.md's "Adding an icon" says), and test_icons.py adds
  the pairs fixtures/scrub and search/metric-xg to the must-differ list. shell.test.tsx gains four
  nav tests. The checker's default --out is now docs/screens-v9 and it gains check_nav_bar with a
  proof run. No assertion was loosened.

- web/src/components/viz/helpers.test.ts: comparisonGroup now takes the position; the test expects
  same-position players with enough passes (and a goalkeeper-only group) instead of all outfield
  players, per the brief's "pizza against position peers". tools/check_web.pizza() changed the same way.
- web/src/features/players/players.test.tsx: deck cards are expected to show the two stats of their
  position (computed in the test from the profile) instead of goals and assists for everyone.

- web/src/App.test.tsx (Home): the proof row (attempts / revised / published) is replaced by the
  brief's "Why trust Optix" strip, so the test now checks the trust strip (three statements, the
  revised count from the ledger, unchanged in French), the showcase score and marks against
  m_showcase.json, three key insights with a revised and a passed one, and five crests in Featured
  teams (was five badges on the page). Hero checks unchanged.

- tools/check_web.py mutation proof: the "crosshair" mutation (swap the displayed lane claim's lane
  in m_001.json) expected a problem starting "crosshair", but since Step 4 the Match Hub draws the
  Matchup as lane strips and its check reports "matchup <id>: page outlines ...". The full run showed
  it "not caught" for that naming reason only; the entry is now "matchup strips" and expects that
  message. Same mutation, same data change, a check that is at least as strict.

## Information architecture (branch `ui-visuals-ia`, from 6c3369d = origin/main; local tag `pre-ia`)

Item status is in docs/ia-progress.md.

### IA decisions

- Start point: local `main` is an older commit (189e9f9) that does not contain 6c3369d; origin/main
  and the tip of `ui-visuals-patterns` are both 6c3369d, so the branch starts there.
- Green start: default suite 451 passed, 2 skipped; `npm run build` passes.
- Word counts: measured in Chromium on the built site by `WORDS_JS` in tools/check_web.py
  (text in `main`, skipping hidden, sr-only, clipped and closed-details content), grouped by the
  nearest `[data-budget]` element. The same function backs the Step 6 text budget.
- Heat bins: a uniform 24x16 grid cannot reproduce the 15 zones (lane edges at y = 20/40/60/80 and
  thirds at x = 33.3/66.7 are not uniform-bin edges), and the brief requires the zone shares from
  the bins to equal the earlier definition exactly. So the grid is zone-aligned: 24 columns = 8 per
  third (edges 0, 33.3, 66.7, 100, each third cut evenly), 16 rows = 3/3/4/3/3 per lane (the centre
  lane is 20 wide, so 4 rows of 5; the others 3 rows of 6.67). Bin lookup uses the same comparisons
  as `zoneOf` (>= for thirds, < for lanes), so every bin sits in exactly one zone. Rendering uses
  the true geometry; smoothing runs in bin-index space.
- Most-used XI: the 11 players with the most starts (lineups.csv `starter`), ties broken by
  player id. On the dashboard season this is unambiguous (the 11th has 10-13 starts, the 12th 4-7).
- Squad numbers: players.csv has a `shirt` field, used as is (the XI wears 1-11 in every team).
- Formation label: counts of listed positions in the XI, DF-MF-FW, shown as "4-3-3 by listed
  positions". The generator's teams.csv `formation` is an input setting and is not read.
- Lineup slots: rows by listed position; left-to-right order within a row from the listed `role`
  (left_back ... right_back, *_l before *_r), so nodes never overlap.

- Season matches for the hub are streamed as tools/pattern_diversity.py streams them: the season
  is its own baseline, in date order, with the novelty history of earlier matches; the showcase
  exactly as agents.run_match does (season baseline). All languages, template phraser.
- Match file size (80 KB per file, 3 MB in all): the full stream does not fit. With three languages
  and two tones the cards alone are about 60 KB per match, and 41 files of the full stream would be
  about 6.8 MB even with an empty event log. So:
  - the recap file holds the recap's cards: every momentum swing, pattern finding and lane claim
    (turning points and the matchup), and at most 2 cards of every other insight type (revised
    first, then with context, then latest); every verification attempt of each kept card's claim
    chain is in the file, so no card loses its claims; the full stream's counts per type are kept
    (`stream_counts`) and the fixtures list shows the full counts;
  - cards and claims are stored compactly (event ids as numbers, payload points as arrays); the
    round trip to the insights.jsonl row is exact (tests/test_match_export.py);
  - the event log is thinned by type to 72 KB per file (so 41 files stay under 3 MB);
  - the showcase file does not repeat its stream: the live hub plays insights.jsonl and
    claims.jsonl, as before (`stream: "bundle"`).
  Result: 41 files, 2.37 MB in all, the largest 70.8 KB; 23.8 s, peak RSS 392 MB.
- Goals and assists had no engine definition: added `engine.metrics.goals` and `assists`
  (documented with limits); they add up to the season's 133 goals (111 assisted).
- Lineups and player summaries go in ui.json (`lineups`, and `shirt`, `goals`, `assists`, `starts`
  on each player row): ui.json 1,101,296 bytes (limit 1.3 MB). The fixture index is
  matches/index.json, loaded lazily with the match files.
- Contracts: contracts/match.schema.json and fixtures.schema.json (Draft 2020-12), TS types
  generated; json-schema-to-typescript does not read `prefixItems`, so tuple rows are typed
  `unknown` there and decoded in web/src/data/matches.ts behind a runtime guard.
- Heat colours: --heat-seq #c4b5fd (single-hue ramp, drawn as opacity over the pitch) for volume;
  --heat-fall #4a8fe7 / --heat-rise #e879f9 for change (rise was #f08a3c until the Step 7 screenshot
  review: an orange between the revise amber and the block red could read as a verdict). All at least 3:1 on --pitch and none equal
  to a verdict, team-slot or club token (tokens.test.ts). The old zone grid's purple/green pair is
  not reused (its green is the verdict green).
- Heat display: volume = smoothed events per % of the pitch area (bins differ in size: the centre
  lane's rows are 5 high, the others 6.67, so raw counts would make the centre look cooler); change
  = second-half density minus first-half density, symmetric scale. Smoothing (sigma 1 bin,
  separable, edge-normalised scatter, so mass is exact) plus a light SVG blur, so it does not read
  as boxes; the bins (data-bin, data-count) and every number shown come from raw counts or the
  mass-preserving smoothing.
- Match Hub: `#/match/m_showcase` renders the live console directly (it needs only the bundle the
  app already loads, so old `#/live` links and their tests keep working); other ids load the
  fixture index and their recap file lazily. Section links are buttons that scroll (hash anchors
  would change the route). The claim ledger link goes to `#/match/:id/ledger`, a table of every
  attempt in the file (the Tech page's ledger stays the showcase's).
- Recap cards: headline = the type or pattern name, one visual (the claim's evidence on a mini
  pitch when the insight has points, else the claim's value), and the shorter of the two tones'
  sentences only when it has at most 22 words (else it stays in the evidence drawer); the evidence
  button is an icon with an accessible name. On screen the cards are capped at 2 per pattern
  family and per type.
- Fixtures nav icon: "scrub" (the timeline glyph) from the existing sheet; no new glyph. The Live
  icon stays on the live replay row and the hub's live chip.

- Team Grid / Board split: `#/teams` is a grid (badge, name, matches, five fingerprint chips);
  `#/teams/:code` is the board. The old TeamsPage is kept on disk, unrouted and marked deprecated
  (no file deletions). The H2H lane block, the half-by-half zone grid and the visible lane tables
  are off the board; lane numbers stay in closed "View data" tables.
- Style pizza: each slice is the team's value over the league average (ratio, capped at 1.6x so
  one extreme measure does not hide the rest), the dashed ring = the league. The legend names the
  five measures only; the direction words are already the header chips.
- "Where they attack": five lane bands across one pitch, coloured by the team's lift over the
  league in final-third entries (diverging heat tokens). The soft-side line appears only when the
  existing soft-lane rule passes for that team; otherwise one quiet line.
- Signature patterns: up to three on the board with the share of matches and its Wilson 95%
  interval, which the export now carries (`patterns.signature[].interval`); "Show all" opens a
  drawer with every family seen for the team (`patterns.team_families`).
- Player touch maps (for the Player Console) are exported per team as
  matches/players-heat-<code>.json (16-18 KB each), not one 86 KB file.
- Game-state slider on the board: StateSwaps gains a `compact` mode (no team picker, one-line
  caption) and all its labels are in en/es/fr; the full caption stays on the Tech page.
- Sheets open from plain buttons, so Sheet now remembers the opener on open and returns focus to
  it on close (Radix alone sends focus to the body without a Dialog.Trigger). Applies to every
  sheet, including the evidence drawers.
- Board word count (1440, visible): VES 178, NTG 174, AUR 166, CAL 166; HAR at 390: 172. Budget 180.

- Player Deck (`#/players`): cards show the initials avatar, badge, name, position, goals and
  assists only; filters by team and position, accent-blind name search; 2 / 3 / 4 columns at
  390 / 1024 / 1440. Players are ordered by team, then GK-DF-MF-FW, then shirt.
- Player Console (`#/players/:id`): routes (PassRoutes, top 8 then "Show all routes (N)"), the
  percentile pizza, diverging bars = the same percentiles minus 50 (so the two visuals cannot
  disagree), the season touch map from players-heat-<code>.json, and pattern chips.
- Pattern evidence: `patterns.players[]` rows now carry `evidence`, the findings' anchor event ids
  (the first 12 in match order), and those ids are added to `ui.evidence`, so a chip opens the
  events behind it. ui.json 1,133,327 bytes (limit 1.3 MB).
- Raw / With context: built only from the player's fired Verifier check (the held-back sentence,
  the published sentence, the rule's reason and the figures already in the player row). Six
  players have one; for the rest the toggle is disabled with a note. No new claims.
- The old PlayersPage is kept on disk, unrouted and marked deprecated (no file deletions).
- HeatPitch with one bin list (a season touch map, no halves) summed a missing second half
  (NaN, an empty map); fixed in heatValues, with a test.
- The settings note now says only the Tech Blueprint and some longer chart captions are English
  only (Team Board, Deck and Console strings are in en/es/fr).

- Text budget (tools/check_web.py `TEXT_BUDGETS`, one config): visible words (WORDS_JS) per element
  marked `data-budget`, attributed to the nearest budget ancestor, so a hub section's budget does not
  count the cards inside it (each card has its own 30). Card 30, Team Grid card 20, Team Board 180,
  each Match Hub recap section 60 (header, turning points, heat, cards, matchup); the event log has
  none. `check_text_budget_proof` appends words to a grid card, a deck card and the board and shows
  each budget fails.
- Lane wording: visible "lane"/"mismatch" (English) is allowed only inside `data-lane-ok`: the Tech
  worked example (the crosshairs entry of the Visual guide, labelled "One example of many"), the
  Match Hub Matchup section, the lane-lift strip label, and the legend of a verified claim's
  crosshair on a live matchup card (that card exists only when the claim was published). The proof
  adds a lane sentence to the hub's turning points and shows the scan catches it.
- Matchup section words: the two crosshairs share one legend (en/es/fr) instead of one each, and the
  note no longer says "because" (the banned causal list caught my own wording).
- Card sentences: the tone is chosen by its English length and the sentence shows only when it has
  at most 22 words in every language, so a language switch never hides a sentence or its numbers
  (the checker caught en and fr differing on m_001).
- Checker routes: home, fixtures, hub_live, hub_final (m_001, a final with a lane claim; m_007 is
  also opened to prove a final without one has no Matchup), teams, team_board (AUR), team_sheet (the
  board with the lineup sheet open: Tab must reach every control in the dialog and focus must stay
  inside it), players, player (NTG_07, which has a context check). Every route at 1440, 390,
  1920x1080 and 1600x900.
- Checker consistency: crosshairs on every final with a lane claim (37) against out/matches; heat
  bins (m_001) against the match file; the touch map against players-heat; lineup nodes against
  ui.lineups; routes and pizza now on the Player Console. New mutations: crosshair (match file),
  heat, touch map, lineup. The old H2H pairs loop on the Team Board is gone with the block.
- Tracer: the match files and touch maps join the sources (their numbers, the full event ids the
  page expands), and heat legends and View data shares/changes are recomputed in Python
  (smoothing, density, zone shares) independently of the page.
- Live frame on the hub: at the 1600 px+ demo layout the back link and Live chip sit in the page's
  top padding, so every live visual stays on the first screen at 1600x900.
- Lineup nodes: the accessible name starts with the visible number and surname ("1 Fenren, Kwame
  Fenren, Goalkeeper"; axe label-content-name-mismatch); jersey numbers are 16/40 of the jersey so
  they render at 11 px or more on a phone.
- Fixtures: each matchweek group is a panel (rounded-2xl), like the other pages' sections.

- Step 7 screenshot review: the heat map still showed bin edges, so its display blur went from 1.1
  to 2.4 (SVG only; every shown number comes from the counts and the mass-preserving smoothing, so
  no number moved), and --heat-rise became magenta #e879f9, with a new token test that every heat
  hue is at least 45 degrees from each verdict hue. Lineup jerseys at 390 px do not collide.

### Test changes (IA)

- web/src/components/viz/helpers.test.ts: the PlayerRow fixture gains the new required fields
  (shirt, goals, assists, starts). No assertion changed.
- web/src/App.test.tsx, "Tactical patterns on the pages": the signature check visited `#/teams`
  (one page with every club); it now visits each `#/teams/<code>` board and asserts the same
  families in the same order, plus that no club has more than the three the board shows.
- web/src/App.test.tsx, same test, player half: it picked a player in the old `#profile-player`
  select on `#/players`; it now checks the deck links every player, opens the starved-finisher
  player's card and finds the same chip on the Player Console.
- web/src/routes.test.tsx: the mocked page module for `/players` is now PlayerDeck (PlayersPage is
  unrouted); a `/players/:id` case is added.
- tests/test_dashboard.py (slow), `test_the_visuals_match_the_engine_output`: `pairs == 20` counted
  the Team Board's H2H selector pairs, a block the brief removes. The crosshair check now runs on the
  Match Hub, so the test asserts `pairs` equals the number of verified lane claims in the committed
  final match files (60), which is stricter in count. The other assertions are unchanged.
- tests/test_dashboard.py and test_visuals_consistency.py read `check_web.ROUTES` / `MUTATIONS`, so
  they pick up the new routes (fixtures, hub_live, hub_final, team_board, team_sheet, player) and
  the four new mutations without edits.

- tests/test_verifier_full.py, claim-level shot_spam pooled recall (the one exception the brief
  allows): the point floor (recall >= 0.80) is replaced by the interval method for this one check,
  listed in INTERVAL_FLOORS: the pooled Wilson 95% interval's upper bound must reach 0.80, so the
  data cannot reject the 0.80 target. Measured: 68/86 = 0.79 [0.69-0.86], upper bound 0.86. This is
  deliberately less strict than a point floor; the point estimate and interval are printed in the
  assertion message and in docs/verifier-recall.md so the figure stays visible. Reason: the rule and
  the case definition are unchanged; the five generated leagues were resampled by the Tier 2 plants
  (the committed leagues met the point floor exactly, 76/95). Every other floor, including the
  pipeline-level shot_spam point floor of 0.81 (measured 0.83), is unchanged. New fast test
  tests/test_verifier_floor.py: the measured pool passes, the same pool with half the 68 hits
  flipped to misses (34/86 = 0.40 [0.30-0.50]) fails, and the point floors still bite.

## Patterns (branch `ui-visuals-patterns`, from `ui-visuals-icons` 144ba45; local tag `pre-patterns`)

Tactical pattern library (PART B of the icons + patterns brief). Checklist per pattern:
docs/patterns-progress.md. Plan and audit: docs/patterns-plan.md.

### Pattern decisions

- Setup: `pre-patterns` is a local tag on the last icons commit; the branch starts there. Green start
  reused the icons gates run minutes before on the same tree (default suite 286 passed / 2 skipped,
  `npm run build` green): no file changed between them.
- Baseline data for the byte-identity proof was generated before any generator change:
  `data/generated-2026-base/` and `data/generated-2027-base/` (season + showcase each, gitignored by
  the new `data/generated-*/` rule). The 2026 showcase there is byte-identical to the committed
  data/showcase. Peak RSS 141 MB (2026) and 152 MB (2027, showcase search from 0: 2724 tries, 69 s).
- Byte-identity proof (first gate of Step 2): PASSED. With every motif propensity at zero
  (`--motif-scale 0`) the 2026 season, the 2026 showcase, the 2026 full league, and the 2027 season
  and showcase are byte-identical to the pre-patterns generator (every table and ground_truth.json,
  `diff -rq`). tests/test_motifs.py keeps it: hashes of the 2026 and 2027 files recorded before any
  motif code (tests/data/pre_patterns_hashes.json); 2026 runs in the default suite, 2027 is slow.
  How: motifs run only through `MatchSim.motifs`, which is None when nothing is planted; each
  (motif, team) has its own `random.Random(f"{match seed}:{motif}:{team}")`, consulted only when the
  propensity is above zero; while a script runs the simulator's generator is swapped for it. No
  new key is written to ground_truth.json when nothing is planted.
- Detectors measured on the pre-planting full league (seed 2026, 760 team-matches; peak RSS
  1.45 GB, 18 s): bait and switch 0, cut-back 6.4%, flank isolation 0, low block 2.8%,
  counter-press 0, rest defence 2.0%, starved finisher 9.2%, fouls after losses 25.1% of
  team-matches. Detector numbers equal the independent recompute on every finding (0 mismatches).
  Why three are zero: the simulator logs at most one pressure per opponent action, so two pressures
  inside 4 s happen 44 times in 24,280 attacking-third losses; 15+ short passes in a row happen in
  36 possessions per league; no possession has more than 8 passes along a touchline strip.
- Planting is therefore needed for P1, P3 and P5 (base rate about 0; aim: >= 25 planted cases per
  league) and is used at signature strength for the others. Where a base rate exists, the planted
  rate per planted team-match is reported against it in docs/patterns.md.
- Threshold tuning on seed 2026 (full league), logged:
  - flank isolation min_windows 2 -> 1 (a single planted spell is one window; 0.4% false positives);
  - low block min_opp_shots 4 -> 3 (A's shots in 15 minutes were the condition that failed most);
  - counter-press min_regains 3 -> 2;
  - rest defence min_tilt 0.65 -> 0.60 and a rolling 30-minute window (the brief allows "per match
    or window"): NTG's tilt in its chasing windows was 0.57-0.64 in most planted matches;
  - starved finisher xg_per_touch_mult 3 -> 5 (false positives 9.0% -> 5.7%);
  - fouls after losses min_fouls 2 -> 3, min_rate_vs_league 1.5 -> 2.5 (false positives 25.6% -> 4.0%).
- A planted case is a team-match in which the script completed at least the number of instances the
  definition needs (1, or 2 for counter-press, rest defence and starved finisher, 3 for fouls after
  losses); one planted foul cannot make a three-foul pattern.
- Realism with planting on: the first version added shots on top of the natural ones (small league
  shots per team 14.0 -> 16.4, over the 11-14 target). Fixes, without touching any target:
  - the starved finisher became a conversion: a shot the simulator already decided to take is
    re-routed to the planted forward (one pass into the box, his unpressured shot);
  - motifs that add shots lower the natural shot appetite of the team that gets them (SHOT_COMP:
    own motifs, and a team facing NTG's counters or AUR's low block); only when that motif is active,
    so the zero case is untouched;
  - rates lowered for the low block (0.30 -> 0.12) and fouls after losses (0.15 -> 0.10).
  Result: every calibration target passes on seeds 2026, 2027 and 2028 (small league), and
  tests/test_realism.py plus tests/test_data_gen.py (non-slow) pass.
- Banned wording: one file, contracts/banned_language.json (en/es/fr), one matcher
  (contracts/banned.py, whole words, case-insensitive, phrases match across spaces). Wired into the
  template linter (tests/test_banned_language.py), the phraser output guard (each banned word in
  each language is an adversarial test; the requested language and English are both checked) and
  the check_web forbidden scan (all three lists on every page).
- "plan" is matched as a whole word only, so "explanation" and "planet" are not hits.
- The phraser system prompt gained one rule (say what was recorded, never why) and
  PROMPT_VERSION moved to p2. The phrasing cache holds no model sentences, so nothing is invalidated.
- Existing UI wording that the new scan would catch:
  - TechPage "Not drawn, because the data ..." became "Not drawn (the data cannot support them)";
  - the robustness and verifier-recall tables said "Trap threshold", "Non-trap cases" and
    "Verifier trap rules". These are the engine's planted test cases, not a team's behaviour, but
    the scan cannot tell the two apart, so the headings now say "Planted-case threshold",
    "Unplanted cases" and "Verifier context rules" (tools and docs);
  - code comments ("focus trap" in ui/sheet.tsx, "on purpose" in two comments) are not UI text and
    are left alone.
- Showcase search (Step 2): a serial scan of the trap-only search from 0 to the 20000-try cap, running
  the full stream on every candidate that passed the five traps (8 such candidates; peak RSS 0.8 GB).
  None had four new families AND two revised or blocked naive claims: offsets 8827 and 8911 had four
  families but at most one revised naive claim. Per the brief this relaxes to three families. The
  first candidate, offset 6914 (AUR 4-0 NTG), meets that: low block (AUR), rest defence and flank
  isolation (NTG), and three naive claims revised by the new rules (field tilt twice, final-third
  volume). With planting on it is also the first offset a trap-only search from 0 finds, so
  the hint keeps the slow "search from 0 lands on the hint" test valid. The hint is now keyed by
  (seed, motif scale): {(2026, 0.0): 1383, (2026, 1.0): 6914}, so scale 0 still finds the
  pre-patterns showcase byte for byte (the byte-identity test caught a single shared hint).
- Publishing choices in the Analyst (detectors unchanged, so recall is measured on the definitions):
  - the starved finisher is full-match only (`full_match_only` in the config): the touch lines are
    full-match lines, and at half time first-half touches were being compared with them;
  - flank isolation is published only when >= 10% of the team's final-third passes are in the
    spells (MIN_ISOLATION_F3_SHARE): the brief's definition counts touchline spells anywhere, and
    "0% of their final-third passes came in 1 spell" says nothing;
  - zero counts get their own phrasing (`.no_shot` for bait and switch and flank isolation,
    `.no_cross` for cut-backs), never "0 shots, 0 xG";
  - within a match, a family + team (+ player) already surfaced at half time is surfaced again at
    full time only when its magnitude moved >= 25% (the same rule as cross-match novelty);
  - two pattern rules firing on one naive claim use a combined revision template
    (field_tilt.low_block_and_counters); a combination without one is dropped, never phrased with
    one rule's numbers missing (the showcase lost a claim to the number guard before this).
- Tuning attempt 1 (starved finisher): min_xg 0.25 added. Without it, a forward with 25 touches,
  two unpressured shots and 0.11 xG qualified (xG per touch cleared 5x the position median because
  the median is tiny). The template also shows the league's lower-quartile touch line for forwards,
  so "only N touches" carries its comparison. Measured effect: Step 6.
- Measurement (Step 6, tools/pattern_recall.py, docs/pattern-recall.md): 10 full leagues (seeds
  2026-2030 at 1.0x and 0.5x), serial, one league in memory; the engine's id-keyed caches are cleared
  between leagues (without that the first run climbed 1.2 -> 1.5 GB after two leagues and was
  stopped). Peak RSS 1.8 GB, 172 s with the leagues already generated (first run with generation:
  311 s, 2.2 GB). Detector versus independent recompute: 0 mismatches.
- Tuning attempts on the tuning seeds only (2026-2028), hold-out untouched:
  - P4 low block, attempt 1 (earlier): min_opp_shots 4 -> 3: recall 0.44, FP 3.2%. Diagnosis of the
    misses: the window that came closest failed on the opponent's shot count most often, then blocks
    and the outside-box share. Attempt 2: min_opp_shots 3 -> 2 (the brief sets no minimum): recall
    0.53, FP 5.3%. Attempt 3: also block_pctl 0.75 -> 0.60: recall 0.56, FP 7.2%. Still under 0.60
    after three attempts, so P4 is **experimental**; attempt 2's thresholds are kept (the better
    trade-off). Hold-out: 0.44 recall, 4.4% FP.
  - P6 rest defence, attempt 1 (earlier): min_tilt 0.65 -> 0.60 and a 30-minute window. No further
    attempt: the misses are planted counters in matches where the team held 30-50% of the territory,
    so the definition's precondition (territorial dominance; the brief says >= 65%) is not met and
    the detector is right not to fire. Lowering the tilt further would change what the pattern is.
    P6 is **experimental** (tuning 0.60, hold-out 0.48, FP about 7%).
  - P7 starved finisher: attempt 1 is the min_xg floor above; tuning 0.80, hold-out 0.88, FP 5.1%.
- Novelty (tools/pattern_diversity.py, docs/pattern-diversity.md): a pure down-weight only reordered
  the cards (the per-summary cap rarely binds), so VES repeated its cut-backs in 50% of its cards.
  Ranking now holds back a candidate whose score ends below SURFACE_MIN_SCORE (0.6): an unchanged
  repeat of either of the team's previous two matches scores 0.5 (pattern) or 0.45 (naive claim).
  A repeat whose magnitude moved >= 25% is not down-weighted. With novelty both bars are met (most
  common family 22.2%, worst per-team repetition VES 39.5%); without novelty VES is 47.8%. Pipeline
  recall (the planted cases the stream surfaced) is lower with novelty for the signature families
  (bait and switch 1.00 -> 0.71): the price of not repeating a team's signature every week. The
  standalone showcase has no history, so no novelty adjustment applies to it.
- Bug fixed: `MatchState.view()` dropped the dataset's baseline, so a match streamed from a season
  dataset with no separate baseline compared itself with the match so far (league lines from one
  partial match). The view now keeps `baseline_of(ds)`. The showcase (season baseline) is unchanged.
- Experimental policy applied: P4 (elastic low block) and P6 (rest defence) missed the hold-out
  recall bar after three tuning attempts, so both are `enabled=False` by default and publish no card
  (the brief: "excluded from the demo stream"). Their context rules stay on: they only block a naive
  territory claim and ask for numbers the Verifier recomputes, and switching them off would let an
  unqualified "N% of the territory" through where the low block or the counters hold. The brief also
  asks the showcase for three new families; no candidate in the 20000-try scan had three validated
  families (at most two: offsets 8827, 8911, 11293, 13865), so the showcase stays at 6914 and counts
  families shown as a card (P3) or through a rule that rewrote a naive claim (P4, P6). Team Board
  signatures use enabled families only (detect_team's default). The Tech catalogue shows
  "experimental, off in the stream".
  A naive claim rewritten by a P4 or P6 rule is still a tactical_pattern card whose chip names the
  rule's family (e.g. "NTG had 80% of the territory, yet 71.4% of their 7 shots were from
  distance..."): it is the field-tilt claim with the numbers the rule asked for, recomputed by the
  Verifier, not a P4 or P6 claim. Showcase after the change: 47 insights (was 49), 12 revised, 0
  dropped.
- Diversity after switching P4 and P6 off (docs/pattern-diversity.md): both bars were missed
  (cut-back 27.3% of cards, VES repetition 45.7%). Both measures count distinct (team, family) pairs
  per match, so per-match family caps cannot move them; the lever is the novelty rule. A count
  magnitude going from 1 to 2 passed the 25% "changed" test, so a signature family came back
  whenever its count wobbled. A change now also needs an absolute step of 2 (NOVELTY_MIN_STEP; a
  percentage magnitude such as 60 -> 75 is unaffected). Result: VES repetition 35.0% (bar met);
  the cut-back is still 26.9% (bar 25%, missed). It is left missed and reported: the cut-back is
  common because real cut-backs occur in about 6% of unplanted team-matches, and pushing it down
  would mean ranking one family below the others for being true more often.
- Stale league found and fixed: robustness run inline peaked at 3.03 GB (over the 2.5 GB rule),
  because each full-league job generated its league in memory and then loaded it again. With
  --reuse-leagues it reads the leagues tools.pattern_recall already wrote (the brief: reuse
  generated league data); peak 2.36 GB. Comparing that run with the fresh one showed seed 2026
  differing while 2027-2030 matched exactly: data/generated-2026/full had been written at 07:36,
  before the generator commit 4e67d84 (motif shot-volume fix), and pattern_recall had reused it.
  The stale league was moved to the session scratchpad (not deleted); league_dir now writes a
  generator_stamp.txt (hash of data_gen/*.py) and regenerates any league whose stamp differs, and
  robustness uses the same function. docs/pattern-recall.md and docs/robustness.md were re-measured
  on fresh leagues. The tuning-attempt figures above used the stale 2026 league; re-measured with
  the kept thresholds, tuning recall is P4 0.44 (was 0.53), P6 0.63 (was 0.60), P7 0.82 (0.80), P8
  0.90 (0.93); hold-out figures are unchanged (2029-2030 were fresh). No status changed.
- Robustness (tools/robustness.py): its showcase search used a 6000-try cap, below the showcase's
  try 6914 with motifs planted, so the cap is now the generator's 20000 default
  (--showcase-max-tries). It runs with --jobs 0, a new in-process mode that clears the engine caches
  after each league, to keep within the "at most 2 processes, no multiprocessing" rule; the process
  pool is still the default when --jobs is above 0.

- Tier 2 follow-up (P15, P17, P16, P11), in the brief's order. Base rates first, on the unplanted
  seed 2026 league (data/generated-2026-zero): set-piece share of non-penalty xG has mean 0.175 and
  95th percentile 0.49; transition shots per team-match mean 0.9, 95th percentile 3; own-zone
  completion under pressure median 0.75; a player's gap over team-mates under pressure 90th
  percentile 0.18. All four occur naturally, but at random: no hidden generator trait marks a true
  case, and recall needs labelled cases, so all four are planted at modest strength (about two to
  three times the natural rate), and natural occurrences on unplanted teams count as false
  positives, exactly as for Tier 1. With the first floors P17 (3 shots) and P16 (10 pressured
  passes) had base rates of 8.8%, above the 8% false-positive bar before any planting, so the floors
  were raised to 4 and 12 before planting (base rates 3.9% and 4.6%); these are definition choices
  made on unplanted data, not tuning attempts.
- Plants: P15 on FWM (a corner delivery is won in the air and headed at goal), P17 on JPH (a
  regain in its own half goes straight into a counter down the team's own lanes), P11 on PLQ (a
  pressed pass near its own goal is intercepted), P16 on MDL's left defensive midfielder (a pressed
  pass is completed; usage 2.2 while planted, so the player sees the ball often enough). All four
  hosts exist only in the full league, so the small 40-match season is byte-identical to the
  pre-Tier-2 generator (only the plant rates in ground_truth.json differ). P15 was first planted
  on NTG and P17 on HAR; NTG's open-play volume (the shot-spam trap) kept its set-piece share low,
  so P15 moved to HAR and P17 to AUR; both then moved to the full league (revision 4 below). Each motif has its own random stream; byte-identity at scale 0 holds
  (tests/test_motifs.py, slow test included).
- Plant revisions forced by the realism tests (none of them changed): (1) P15 first manufactured
  corners (a blocked cross); HAR's corners went from 94 to 182 in the small season and corners per
  team left the calibrated band (7.1, band 4.5-5.8). The plant now acts at a new decision point,
  at_corner: a planted corner delivery is won and headed (the simulator draws the header shot), so
  no corner is added (corners per team 5.66). (2) P17's counters first went through the middle and
  diluted AUR's planted left lean (54.5% of entries on the left, floor 55%); the through ball now
  follows the team's own lane weights. (3) P11 on CAL changed the small season enough that the CAL
  tilt control and CAL's counter-press recovery failed, and nearby plant rates flipped them back and
  forth (noise in a 40-match season), so instead of tuning rates against a noisy test P11 is planted
  on ASV, a high-press side that exists only in the full league where recall is measured. (4) The
  slow suite then showed the same noise from P15 on HAR and P17 on AUR: the pooled five-seed
  final_third_pass_share went to 0.3065 (allowed up to 0.306; 0.3042 without them), and
  retuning P15's shot compensation only moved it around the edge (0.85 failed, 0.7 passed, 1.0 broke
  shots and goals). With P15 moved to FWM (a direct side) the share was 0.3042, but CAL's
  counter-press recovery in the 2026 season fell to 9/16 (floor 0.60; 10/16 without P17). Rather
  than tune rates against a 16-match sample, P15 moved to FWM and P17 to a low-block counter side
  (DCH, then JPH; below), both full-league only, like P11 and P16. The small season and its tests are then exactly
  as before Tier 2. The recall figures below were re-measured after these changes.
- P11 reads the press from pressure events per opponent pass (engine press_intensity), not PPDA:
  PPDA misleads on this feed (rule ppda_alone). "Own zone" is x < 30, so templates say "near their
  own goal", not "own third".
- P15 tuning, on the tuning leagues only. First definition (>= 2 set-piece shots, npxG >= 0.5, share
  >= 50%) gave recall 6/27 on seed 2026 with the first (corner-adding) plant. Attempt 1: npxG >= 0.3
  and share >= 40%: recall 12/16 (2026) but 8/16 (2027), false positives 6.9-7.2%. Attempt 2: >= 3
  set-piece shots, and a planted case needs 3 planted set-piece shots (NEED = the detector's own
  floor, as for P17 and P16): pooled tuning 0.68, hold-out 0.80 with that plant. The plant then had
  to change (corner counts, above), and with the realistic header plant the same thresholds give
  0.59 tuning and 0.49 hold-out. Attempt 3 (read off the tuning leagues only): a share line of 0.35
  lifts tuning recall to about 0.67 but false positives to 7.2-9.0% per tuning league; no line
  clears both bars, because in about a third of planted matches HAR still takes enough open-play xG
  to stay under any line that unplanted set-piece-heavy matches do not also cross. P15 is
  experimental (enabled=False), thresholds as after attempt 2; final numbers 0.64 tuning, 0.27
  hold-out (docs/pattern-recall.md). Its rule ctx_xg_from_set_pieces stays on, like P4's and P6's:
  it only asks an xG sentence for the set-piece share, which the Verifier recomputes.
- P15 after the host move (revision 4, made for the calibration and recovery tests, not for
  recall; thresholds unchanged since attempt 2, no fourth tuning attempt). With the shot
  compensation carried over from HAR (0.50) it measured 0.643 tuning and 0.639 hold-out on FWM, but
  the full-league tests then showed why: FWM, a weak side, fell from 37 points to 13 (bottom_points
  out of range; goals 45 to 27, shots 389 to 314), because halving its open-play appetite is not
  made up by headed corners. That pass came from an unrealistic plant, so it is not used. A
  compensation of 0.70 kept FWM's shot count (383 against 389) but robustness seed 2027 still had
  FWM bottom on 11 points; its xG had dropped (36.0 against 42.2), and headers are low-xG shots, so
  the right thing to keep is the planted side's xG, not its shot count. SHOT_COMP for P15 is 0.85:
  FWM's xG over seeds 2026-2028 is 41.6, 41.2, 34.5 (mean 39.1) against 38.5, 42.2, 38.6 unplanted
  (mean 39.8), and the bottom side has 22, 27 and 26 points (range 15-35). FWM is the league's
  weakest attack (about -45 xG difference a season), so its points swing with finishing luck either
  way. P15's recall is re-measured with this value below.
- P17's host: on DCH, the 2027 full league's bottom side had 14 points and ESF's corner specialist
  fell to 61 set-piece against 63 open-play chances (72 against 53 before). The full league links
  matches through squad rotation (one SquadManager random stream), so any plant change resamples
  every later match; the ESF tie was such a draw, and the bottom-points miss was FWM's compensation
  above. P17 moved to JPH, the other low-block counter side, and with P15 at 0.70 every full-league
  and realism test passes (tests/test_full_league.py, tests/test_realism.py, slow included).
- P11: after the move to ASV, recall was 0.74 tuning but 0.55 hold-out with the completion line at
  the league 15th percentile; the misses sat just above that line (0.59-0.70 against about 0.58).
  Attempt 1: the line moves to the 25th percentile: 0.90 tuning, 0.81 hold-out, false positives
  3.1% and 2.8%. Validated.
- P11's host after the five-league slow tests: on ASV, the corner specialist ASV_11 (a planted
  trap on the same team) lost set-piece chances on three of five leagues (69 to 54 on 2029, where
  open play reached 56 and the set_piece_inflation player check found 3 of 4), plausibly because
  giveaways at the back cut ASV's attacks and corners. A pattern plant should not erode another
  trap on its own team, so P11 moved: IRK gave a champion on 97 points (range 78-95; ESF, not
  IRK, a resample effect), PLQ (the weak side that presses hard, no player trap) passes every
  full-league and realism test. Final P11 recall on PLQ: 0.90 tuning, 0.92 hold-out, false
  positives 3.0% and 2.5%, thresholds unchanged.
- Final Tier 2 recall (docs/pattern-recall.md, the leagues with FWM, JPH, PLQ and MDL plants):
  P15 0.46 tuning, 0.62 hold-out (experimental, tuning below the bar); P17 0.93 and 0.91; P16 0.76
  and 0.70; P11 0.90 and 0.92; false positives all at most 5.5%.
- P16 on VES's left defensive midfielder validated but broke four small-season style-recovery
  tests (AUR's lead behaviour, NTG's soft lane, the small-league soft lane, the Team Board): usage
  2.2 for one VES midfielder shifts the 40-match season. Switching only that plant off fixed all
  four, so P16 moved to the full league. On KWC (possession) recall collapsed to 0.32/0.18: KWC's
  team-mates already complete about 80% under pressure, so a 20-point gap is out of reach. It now
  sits on MDL's left defensive midfielder (same wing-play archetype and 4-2-3-1 as VES, team
  completion under pressure 0.746 against VES's 0.738): 0.70 tuning, 0.63 hold-out, false positives
  3.5% and 3.3%. Validated with its first thresholds; the hold-out margin is thin.
- P16 after the full league was resampled (P15 and P17 moved, P15's compensation 0.85): 31/43 =
  0.72 tuning but 16/28 = 0.57 hold-out, below the bar. Its first tuning attempts, read off the
  tuning leagues 2026-2028 only (tools: a P16-only sweep with the recall tool's case definition):
  attempt 1, gap line 0.15: recall 39/43 = 0.91, false positives 6.7%; completion 0.80 adds false
  positives and no recall. Attempt 2, gap 0.17: 36/43 = 0.84, false positives 5.1%; gap 0.18:
  34/43 = 0.79, 4.6%. Chosen: 0.17 (the highest recall with false positives at most about 5%, to
  keep a margin under 8%), then measured once on hold-out: 20/28 = 0.71 hold-out, 36/43 = 0.84
  tuning, false positives 5.1% and 5.5%. Validated.
- P17 passed with its first thresholds: 1.00 tuning, 0.97 hold-out, false positives 4.0% and 3.0%.
- Naive claims for Tier 2: P15 tests the existing team xG claim; P17 a new "only N% of the passes"
  claim (possession_pct, the share of passes: the feed has no possession clock), proposed at half
  time and full time when the share is at most 40%; P16 a new player pass_completion claim, at full
  time, for the team's player most often pressed on the ball if that is at least 12 passes; P11 the
  existing PPDA claim. PPDA always needs press intensity (ppda_alone), so ppda_alone and the P11 rule
  share one combined revision; xG with shot_spam or small_sample_xg has combined templates too.
- ctx_tilt_without_access (P4's rule) now fires on any overlap of the low-block spell with the
  claim's window (was >= 600 s). With the new plants the 2026 season held a field-tilt claim
  (3600-5400) overlapping a low-block spell by 463 s; it published unqualified and the cross-claim
  test (no unqualified dominance claim in a P4 window) failed. The rule moved toward the test, not
  the other way.
- Stale data found in tools/pattern_diversity.py: it reused data/generated-<seed>/season whenever
  matches.csv existed, with no generator stamp, so its first run measured pre-Tier 2 seasons (no P15
  or P17 planted cases). It now writes and checks generator_stamp.txt like tools.pattern_recall, and
  reports each family's share of matches with a card (the brief's "surfaced in at least 5% of
  matches"). Re-measured after revision 4: with novelty the cut-back is 19.7% of cards and the
  worst repetition VES 31.2% (both bars met); without novelty 20.7% and VES 50.0%. All twelve
  families reach 5% of the 120 matches. No ranking weight was changed.
- Robustness peak memory: run inline (--jobs 0) the five reused full leagues reached 2.93 GB in one
  process (one full-league job alone peaks at 1.8 GB; the rest is memory the process kept between
  jobs). --jobs 1 now runs the jobs one at a time, each in a fresh child process
  (max_tasks_per_child=1): serial, at most two processes, peak 1.76 GB. Small league: 6 of 10 seeds
  have every target in range (was 7 of 10); no target fails on more than 2 seeds.
- Showcase: a first scan (with P15 and P17 planted on HAR and AUR) picked offset 351. After the
  plants moved to the full league (revision 4) the scan was rerun (cap 20000, serial, every trap
  hit streamed): hits 6914, 8213, 8827, 8911, 11293, 11579, 12985, 13865. The first, 6914 (AUR 4-0
  NTG, the showcase committed before this follow-up), meets both targets, so it is kept and
  SHOWCASE_SEARCH_START is (2026, 1.0): 6914 again; the showcase tables are byte-identical to the
  committed ones (ground_truth.json gains only the new plant rates). Final stream: 49 insights, 13
  revised, 0 dropped; validated pattern cards P17 (half time, full time) and P3;
  Tier 2 rewrites: AUR's share of the passes at half time (P17's rule) and NTG's xG at full time
  (P15's rule with shot_spam). Two identical exports.
- Open gate: tests/test_verifier_full.py claim-level shot_spam pooled recall is 68/86 = 0.79
  [0.69-0.86] against a floor of 0.80; the pipeline level (0.83, floor 0.81) and every other slow
  test pass. The rule and the case definition are unchanged (no diff in engine/rules/shot_spam.py
  or tests/verifier_cases.py); the leagues are not. The committed run sat exactly on the floor
  (76/95 = 0.80), and every plant change resamples all five leagues (squad rotation links the
  matches), so the five Tier 2 configurations measured 0.79, 0.82, 0.81, 0.79 and 0.79. The misses
  are on unplanted opponents (IRK, OKP, PLQ, KWC, CAL), none on a Tier 2 host. The floor is not
  lowered and the plants are not moved again to find a passing draw; the floor needs a decision
  (a pooled interval-based floor, or more leagues) that is the owner's to make.
- Tier 2 icons are existing ones (corner, style-direct-play, pressure, style-high-press):
  engine/patterns/config.py ICONS maps them, and web/src/icons/semantic.ts likewise.

### Test changes (patterns)

- tests/test_translation.py: the placeholder test iterates over template variants (a key may hold a
  list); every assertion is kept and two are added (same number of variants per language, every
  plural form follows a param of its own sentence). The "no glued x" test iterates variants.
- tests/test_phraser.py, tests/test_agents.py: the template checks iterate `narrative.variants()`
  instead of assuming one pair per key; plural forms are resolved before the language check, as at
  render time. Same assertions on more sentences.
- tests/test_engine.py `test_profiles_have_league_comparison_and_sample_sizes`: with planting on,
  CAL trails in the 2026 season but concedes no chance while trailing, so that lane sample is empty.
  The engine reports it correctly (n 0, share None, confidence low); the test assumed every sample was
  non-empty. It now asserts exactly that for an empty sample and the sum of 1 for every other.
- tests/test_data_gen.py (slow) `test_showcase_search_hint_matches_a_search_from_zero`: reads the
  hint for (seed, default motif scale); same assertion.
- tests/test_verifier.py: the rule-count assertion was a literal 9; it is now 9 + len(PATTERN_RULES)
  (the eight pattern context rules are new), and a new assertion checks every pattern rule is
  registered with REQUIRES and a revision hint. No existing rule check was removed.
- tests/test_dashboard_data.py `test_measured_numbers_are_parsed_from_the_three_reports` is now
  `..._four_reports`: docs/pattern-recall.md joins the measured reports the Tech page parses, so the
  expected set gains it; every table check now runs on it as well.
- tests/test_pattern_claims.py `test_showcase_surfaces_new_families_and_revised_naive_claims`:
  with P4 and P6 disabled the showcase shows one new family as a card, so the three-family check
  counts families shown as cards or through a rule that rewrote a naive claim, and a new assertion
  checks no disabled family has a card. A new test runs the showcase with P4 and P6 switched on and
  applies the same recheck and mutation checks to their claims, so their recomputes stay covered.
- tests/test_pattern_claims.py novelty and half-time tests (written in this branch): the "moved"
  examples change from 3 -> 4 and 2 -> 3 (one more instance, now noise) to 3 -> 5 and 2 -> 4, and
  new assertions check that 3 -> 4 and 1 -> 2 are held back as repeats.
- web/src/types/guards.ts (not a test, but it gates the Vitest fixtures): INSIGHT_TYPES gains
  `tactical_pattern`, the new contract type; without it the stream guard rejected the showcase
  stream. Vitest 118 -> 123 (5 new PatternRoute tests).
- Tier 2 follow-up: tests/test_motifs.py checks the planted players against PLAYER_MOTIFS as a
  sorted list (there are two planted players now, not one); tests/test_patterns.py expects 12
  families (was 8). The micro-sequence builder gains play_pattern and shot_type fields (defaults are
  the old values) and a position argument. New: micro-sequence and mutation tests for the four
  Tier 2 detectors, and one test per Tier 2 rule (the naive claim is held where the pattern holds,
  publishes with context once revised, and the rule stays quiet where it does not hold).
- Tier 2 follow-up, further: tests/test_motifs.py compares the planted players with the
  PLAYER_MOTIFS entries whose team is in the small season (P16's plant is on MDL, a full-league
  team). tests/test_pattern_claims.py: the experimental set gains pat_set_piece_dependence (measured
  experimental); the switched-on run still checks every experimental family publishes and blocks
  mutations. tests/test_verifier.py `test_shot_spam_fires_on_ntg_in_showcase`: NTG's showcase xG
  is also mostly from set pieces, so the expected hint gains ctx_xg_from_set_pieces exactly, and
  the publishable claim carries both rules' numbers; the shot_spam expectations are unchanged.
  tests/test_phraser.py adversarial "invented number": the appended "over 7 matches" used a number
  a showcase claim really contained during the follow-up (7 of 52, offset 351), so the guard could
  not call it invented; it now appends 9917, a number no claim can contain. The showcase is back
  at offset 6914; both changes still hold there. web/src/components/viz/PatternRoute.test.tsx: the catalogue has 12 families (was 8).

## Icons (branch `ui-visuals-icons`, from `ui-visuals-brand` f376c6b; local tag `pre-icons`)

Green start: default suite 279 passed, 2 skipped (azure_live); `npm run build` passes. Item status
is in docs/icons-progress.md.

### Icon decisions

**Phase 0**
- The icon sheet came with the message and a path (~/Downloads, "OPTIX Icon Set_ Dark UI Style
  Guide.png", 1536x1024). Copied to design/source/icon-sheet.png (gitignored); the icons are drawn
  by hand from it, not traced.
- The brief expected seven files failing `prettier --check`; only five did (App.test.tsx, ui/card.tsx,
  viz/Figure.tsx, viz/helpers.test.ts, viz/ZoneShift.tsx). The other two (Flow.tsx, Scoreboard.tsx)
  were already formatted during the brand work. Formatting them changed no behaviour: lint,
  typecheck, Vitest (55) and build pass, and the built bundle hash is unchanged (index-BRDlwXxd.js).

**A0 (audit)**
- docs/icons-plan.md lists every glyph and its replacement. Focus Pitch convention: every team attacks
  left to right and SVG y = data y, so the attacker's left flank is the top band; the sheet draws the
  left flank on top as well, so the lane icons are not flipped.
- Interface glyphs that are not on the sheet (close, arrow, swap, ball marker, cloud) are kept as
  `Glyph` in components/icons.tsx; the registry holds exactly the 54 sheet icons.
- The Home feature drawings are illustrations, not glyphs; they stay, and each card gets its icon.

**A1 (registry)**
- web/src/icons/: one file per icon in glyphs/, names.ts (groups and the `IconName` union),
  registry.ts (name -> component) and `<Icon name size title className />`. Drawn by hand as path
  data from zoomed crops of the sheet (design/review/sheet-*.png, local), not traced; no raster.
- Where the brief and the sheet differ, the brief wins: the momentum marker is off-centre (the sheet
  centres it); play and pause are outlines.
- Colour tokens: --card-yellow #f2c94c and --card-red #e5484d (neither equals a verdict colour) and
  --lane-fill (= --accent). The two cards are tilted in opposite directions (+16 / -16 degrees): with
  the same tilt their grey rasters correlate at about 1.0, since only the colour differs.
- Distinctness is measured by tools/icon_sheet.py (each icon alone in Chromium at 16 and 24 px,
  Pearson correlation of the grey rasters). Redraws:
  - lanes, pass 1: side ticks and a halfway line read as a film strip; replaced by goal boxes.
    Adjacent lanes still correlated 0.91 to 0.93 because the band's 2-unit stroke overlapped the
    neighbouring band. Pass 2: the band is inset (16 x 1.9 inside the 2.8 band) and the goal boxes
    dropped; adjacent lanes now 0.865 at 16 px and 0.843 at 24 px. The emphasised band keeps
    --lane-fill at 70% plus a full-strength stroke.
  - pattern-counter-press, pass 1: it read as a pin with a base line; redrawn as one loop arrow
    that returns to a centre dot. At 16 px it can still look like a bulb; left as is.
  - pattern-elastic-low-block, pass 1: too small at 16 px; arc and dots enlarged.
  - scrub, pass 1: grip lines filled the narrow pill; the pill is wider, with two grip lines.
- Highest non-whitelisted pair after the redraws: 0.873 at 16 px (style-direct-play / style-high-press
  0.867; foul / pattern-tactical-fouling 0.873 is the whitelisted pair). Threshold 0.92.
- The Python distinctness test needs Playwright, so like tests/test_dashboard.py it is skipped in CI
  (which installs requirements-dev only) and runs locally. The Vitest manifest test runs everywhere.

**A2 (replacements)**
- Header and tab bar, settings, transport (play, pause, restart; new scrub and speed icons beside the
  timeline and the speed switch), verdict chips (StatusChip, so the ledger and filters too), Tech
  pipeline steps and Azure states, the evidence summary, the evidence chain (event icons; carry,
  duel, block, clearance and other types without an icon keep the ring), Feed and Focus Pitch type
  chips (`insightIcon`: lane for matchups, else by type, else by claim metric), Team Board style
  labels (`styleLabelIcon`, by label and direction), lane rows, "Attacks from" (wing play / central
  play / lane) and the soft lane, Live panel titles (metric glyphs through a new `Panel icon` prop),
  Home CTAs and feature-card titles.
- Perimeter Lock uses metric-field-tilt (its standard stat is field tilt); metric-territorial-stress
  is kept for "Pinned in own half", which is the engine's territorial-stress spell.
- The swap button's accessible name is now translated (`swap_sides`, en/es/fr). The other icon-only
  controls (restart, close, settings on phones) already had translated names.
- check_web: every route is now also checked at 1920x1080 and 1600x900 (it was Home only), with all
  the gates; screenshots go to docs/screens-v5.

**A3 (gates)** all pass: lint, typecheck, Vitest 118 (55 + 63 icon tests), build, check_web
--ref out --mutation-proof on five routes at 1440, 390, 1920x1080 and 1600x900, frames p95 16.7 /
16.8 ms, initial JS 167.5 KB gzip (+3.0 KB on 164.5; no lazy loading needed), image gate 0 problems,
default suite 286 passed / 2 skipped (azure_live), secret scan 0, repo-size largest
design/social/devpost-thumbnail-1500x1000.png (1.29 MB).

## Brand (branch `ui-visuals-brand`, from `ui-visuals-fixes` 9a573d9)

Green start: default suite 239 passed, 2 skipped (azure_live); `npm run build` passes.

### Brand decisions

**Setup**
- Branched from `ui-visuals-fixes`, not from main 1afdc0d. main already has web/, but the fixes branch
  holds main plus six unmerged, CI-green cleanup commits, and the deterministic export among them is
  needed: re-exporting ui.json for the Home proof row must not churn timestamps. Merging this branch
  later brings both in. The local `main` ref is stale (189e9f9); it was not touched.
- The five uploads came with file paths, so their pixels could be processed. Identified by content;
  copies in design/source/ (see docs/brand-audit.md for the name mapping). design/source/ and
  design/review/ are gitignored.
- Design tooling in requirements-design.txt (opencv-python-headless, vtracer), installed in .venv.
- While scratching out a crop, I created and then removed an empty helper folder
  (`design/tools_tmp`). It held nothing, but strictly this went against "no rm", so it is noted here.

**Step 1 (mark audit)**
- 13 suspects in hero-lineup, all removed. Large marks use exemplar fill (masked template matching);
  small ones use Telea inpainting of the mark pixels only (top-hat or low-saturation mask), with fine
  grain. The VES pinstripe under H8 is redrawn from the rows above and below. A first pass with plain
  box patches and box-wide inpainting smeared stripes and sleeve edges; it was replaced, and the
  before/after sheets show the final pass.
- players-trio is BLOCKED: four of eight fixes are smudged (glove straps, the shorts number). It has
  no alpha, and the white cut-out outline would leave a halo on dark, so no clean alpha either. It is
  not used anywhere.
- kit-sheet is not altered: no maker marks found. Concerns (NTG crest text "ORTHGATE TOW"/"NTS",
  resemblance notes) are in docs/brand-audit.md.

**Step 2 (logo and icons)**
- Both logos traced with vtracer (binary, spline) from a 50% threshold of the originals:
  optix-mark.svg (3 paths) and optix-logo.svg (7 paths) with `fill="currentColor"`, plus `-accent`
  files filled with the --accent value (#37e6a8; an SVG used as `<img>` cannot read CSS variables).
  The same paths go to web/src/components/brand/logoPaths.ts, so the header draws the wordmark inline
  in the accent and the icon set needs no runtime request.
- Checked on the dark background at 16, 32, 64 and 256 px (design/review/logo-check-dark.png): the
  arrow is a smudge at 16 px and a hairline at 32 px. **Favicons below 64 px use a small-size variant
  without the arrow**, with the O and X strokes thickened (dilated by 31 px at source scale) and
  filling the tile. From 180 px up the full mark with the arrow is used. All icons sit on a dark
  rounded tile (--bg), so they also read on light browser chrome.
- favicon.ico holds 16/32/48. The PNGs are 16/32/48, apple-touch-icon 180 (opaque) and 192/512, plus
  manifest.webmanifest. Every raster is rebuilt from pixel data before saving, so no metadata is
  carried over.
- The header brand now links to #/ (Home, Step 4) and shows the wordmark. The README and
  docs/dashboard.md show the logo (black on light, the accent on dark through `<picture>` in the
  README).

**Step 3 (crests and kits)**
- Cut from the kit sheet by column (five clubs) and row (crest, home, away). The backdrop is removed
  by a floating-range flood fill from the window border, walled off by the item's Canny outline.
  Without the wall, the fill ran into the white away shirts, whose shading is as smooth as the grey
  backdrop. The largest shape is kept and closed. Its outer ring gets alpha from the distance to the
  backdrop colour and is un-blended from it, so there is no grey halo on dark
  (design/review/badge-check-dark.png, badge-edge-zoom.png). The faint light rim at the top of the
  shield crests is the crest's printed bevel, not a fringe. Interior whites are kept.
- badge-<code>-48/96/192.webp and kit-<code>-home/away.webp (native width, about 435 px). The crests
  are only about 220 px tall on the sheet, so 192 is the largest useful size.
- **Mini-mark below 40 px.** At 24 px the crest lettering is unreadable, VES and HAR are both blue and
  differ only by outline, and NTG's own crest text is wrong. So `TeamBadge` draws a disc in the club
  accent with the code (Barlow Condensed) below 40 px, and the crest from 40 px up. The disc is also
  the fallback when an image fails or a code is unknown.
- Club accents in tokens.css (--team-aur/ntg/cal/ves/har). tokens.test.ts checks each is at least 3:1
  on --bg and --surface-2, that the dark code text on each disc is at least 4.5:1, and that none
  equals a verdict colour. They are used only inside the mini-mark and as a 3 px bar beside the crest
  on Team Board cards.
- **NTG red versus "blocked":** NTG is #ee4b45 (darker, more saturated), blocked is #ff7a7a. A club
  accent is never alone: it is always a disc carrying the code, or a bar beside the crest. "Blocked"
  always has its block icon and label. Chart colours (home/away, verdicts) are unchanged; the home and
  away dots stay beside the crests, because they key the charts.
- Placed in:
  - the Live scoreboard (crest at 44 px from sm, mini-mark on phones);
  - insight cards (the matchup cards included);
  - Team Board cards (crest, accent bar, lazy kits with a caption) and the head-to-head header (crests
    beside the attacker and defender pickers);
  - Player Deck cards, the hover panel and table rows;
  - Tech ledger rows.
  All use alt="" because the code or name is beside the badge.
- Prettier was run on the touched feature files and also reformatted two files that were already
  unformatted (Flow.tsx, Scoreboard.tsx); whitespace only.

**Step 4 (Home at #/)**
- Home is the index route; unknown paths now go to #/ instead of #/live. #/live, #/teams, #/players
  and #/tech are unchanged, and deep links with ?t= / select / lang still work. The header wordmark
  links to Home. The nav bars keep their four entries: Home is reached through the logo.
- **Hero:** hero-lineup-clean (not BLOCKED). On large screens the picture fills the hero, and a dark
  left-to-right gradient (0.92 to 0.78 alpha over the left 38%, gone by 62%) carries the text over the
  AUR and NTG bands. The two left players are dimmed by it: that is the price of never putting text
  on a bright band. On phones the whole 4:3 picture is shown, with the text below it on the dark
  surface. Text contrast is measured on pixels in the gate (Step 5 / gates).
- Hero files: WebP at 1600 px (203 KB) and 800 px (79 KB), the highest quality from 90 down that fits
  220 KB and 90 KB, with srcset/sizes, width/height and fetchpriority=high. Every other image is lazy.
- **Proof row** from ui.json's ledger:
  - claim drafts checked (attempts);
  - rewritten after verification (counts.revised);
  - verified insights published (total).
  "Drafts" is used because attempts include the revised second drafts. No number is typed in.
- Three feature cards with small inline SVG drawings in the app's tokens; they contain no digits. A
  clubs strip shows the five crests (48 px) with names, linking to the Team Board. The caption
  "Illustrative artwork. Clubs and players are fictional." sits under the hero. Home names no Azure
  feature.
- The no-photo fallback was not built: the hero is not BLOCKED, and the brief asks for the fallback
  only in that case.
- All Home strings are in en/es/fr through the interface dictionary (no digits, as its test
  requires). A Vitest test checks that Home is the default route, that the proof values equal the
  ledger and stay the same in French, the hero attributes, and alt plus width/height on every image.

**Step 5 (social and submission images)**
- tools/make_brand_images.py writes each HTML template to a temp file and screenshots it with the
  project's Chromium (chromium_path; no `playwright install`, no network). Fonts and images are read
  from local files. The first try used set_content; from about:blank the local images and fonts did
  not load, so the templates are now written to file:// pages.
- design/social/:
  - github-social 1280x640 (563 KB, under GitHub's 1 MB);
  - og 1200x630;
  - devpost 1500x1000 (3:2);
  - video title card and end card, 1920x1080. The end card shows github.com/Malottey1/optix as text.
- Looked at each card. The title card's eyebrow says "Synthetic match insights engine", not the
  hackathon's name. A 256-colour palette for files over 1 MB banded the gradients badly, so it is
  used only where a hard limit requires it (the GitHub card, which fits without it). The devpost
  card (1.2 MB) and the title card (1.1 MB) stay full-colour PNG.
- og/twitter meta tags in web/index.html with relative URLs. The image is
  web/public/brand/og-1200x630.jpg (110 KB, JPEG so it stays inside the 300 KB budget for shipped
  images).

**Step 6 (provenance)**
- design/ASSETS.md lists every shipped asset: its source ("author's own photos and prompts,
  AI-assisted; AI tool terms to be confirmed by the author"), the script that made it, the audit
  result, and the fonts (Inter and Barlow Condensed, OFL 1.1). The icons and drawings were made for
  this project.
- The originals carry eXIf and iTXt chunks. The derivatives carry none, because every raster is
  rebuilt from pixel data. tests/test_brand_assets.py (default suite) reads each file's container
  (PNG chunks, WebP RIFF chunks, JPEG markers) for EXIF, XMP, ICC and text. The detector was proven
  on scratch files carrying EXIF and text. The test also checks:
  - the 300 KB budget per file (hero 220/90 KB);
  - that the brand set is complete;
  - transparent corners on crests and kits;
  - the social image sizes and GitHub's 1 MB cap;
  - that no original, review crop or players-trio file is tracked.

**Gates**
- check_web extended: Home at 1440, 390, 1920x1080 and 1600x900; an image gate (alt, width and height,
  lazy below the hero, fetchpriority on the hero; metadata and size budgets of every shipped image);
  a badge gate (mini-mark and crest at 24 and 32 px draw); a hero contrast gate (text hidden, the
  boxes behind it captured, 99.5th-percentile luminance against the text colour, at least 4.5:1).
  With the scrim removed, the sub-line measured 2.58:1 and the gate failed, so it can fail.
- The first full run's screenshots showed empty kit slots and missing crests below the fold: lazy
  images had not loaded when the full-page shot was taken. check_web now scrolls through the page and
  waits (capped at 3 s, since display:none images never load) before a full-page shot. The first
  attempt waited without a cap and hung; it was stopped and rerun.
- The Home translate drawing used 8 px labels at 390 px, which the gate flagged; now 11 px.
- Results: lint, typecheck, Vitest (55), build pass; initial JS 164.5 KB gzip; frames p95 16.8 ms at
  1440 and 1080p; default Python suite 279 passed, 2 skipped (azure_live); mutation proof catches
  every changed visual; image gate 35 files, 0 problems (largest hero-lineup-1600.webp, 208 KB;
  800 px 82 KB); hero contrast 9.5 to 17.3:1; secret scan (tree and history) 0 findings; repo size:
  no tracked file over 2 MB, largest design/social/devpost-thumbnail-1500x1000.png (1.29 MB).
- Full-page phone screenshots show the fixed bottom tab bar part-way down the page: a full-page
  capture pins it to the first viewport. It is not a layout fault.
- tools/image_meta.py holds the metadata reader shared by the tests and check_web; Pillow is now in
  requirements-dev.txt because the default suite reads the images.

## Cleanup (branch `ui-visuals-fixes`, from main 1afdc0d)

Green start: default suite 234 passed, 2 skipped (azure_live). Each task is its own commit.

### Cleanup decisions

**Task 1 (tools/robustness.py repaired)**
- The full-league job now uses `tests/verifier_cases.counts_of(ds, gt)`, split out of
  `league_counts(seed)` so it runs on the league the job already generated (no second generation).
  `verifier_counts` maps its keys to the tool's `rule|trap|fired` format: match rules on the plain
  claim ("claim" level), with true and below-detection planted cases both counted as trap cases (the
  old helper's definition); player rules unchanged.
- Proven on one full league (seed 2026, about 5 minutes): calibration targets, champion and bottom
  points and every planted-pattern recovery are identical to the earlier run. In section 4, shot_spam
  (21/31) and both player rules (4/4, 4/4) match docs/robustness.md exactly.
- **field_tilt_with_lead differs: 9/16 now against 15/16 in the doc.** The doc's section 4 was
  generated before 09c3836, which changed the Verifier's field-tilt rule (judged on the trailing
  spell and on chaser threat; that commit's message reports claim-level recall 0.70 -> 0.53). So that
  row of docs/robustness.md describes the earlier Verifier; the tool is not the cause. I left
  docs/robustness.md unchanged: sections 1-3 are confirmed, and regenerating section 4 would change
  numbers the Tech Blueprint shows. docs/verifier-recall.md has the current Verifier's recall.
  Listed in docs/known-limitations.md; regenerate with `python -m tools.robustness` to refresh it.
- `tests/test_robustness_tool.py` runs the job end to end on the small league (about 25 s, default
  suite) and checks the key mapping, so a removed helper breaks a test instead of the tool.

**Task 3 (infrastructure verified in CI)**
- Two CI jobs: `docker-build` builds the image (`docker build --tag optix:ci .`, never pushed), runs
  it and waits for `/healthz`; `bicep-build` runs `az bicep install`, then `az bicep build` on
  infra/main.bicep and `az bicep build-params` on infra/main.bicepparam. No secrets, no registry
  login, no `az login`, no deployment.
- "Confirmed" means a fact in the repo: `python -m tools.ci_record <run id>` reads a finished run
  with `gh run view` (read-only) and writes infra/ci-verified.json (run id, commit, URL, the two
  jobs' conclusions). `agents/azure_status.py` gives the container and the Bicep the new state
  "verified by CI build/lint" only when that file records `success` for their job; no file, a failed
  or an unfinished run leave them "built, not verified live". The live-service rows can never get
  this state.
- CI run 39892235299 (commit a317ae6): python, web, docker-build and bicep-build all succeeded. The
  container answered `{"status":"ok","service":"optix","matches":1}` inside the job; the Bicep job
  printed no warnings or errors. Recorded with `tools.ci_record`; the container image and the Bicep
  now read "verified by CI build/lint" in docs/AZURE.md, the README and the Tech Blueprint.

**Task 4 (known limitations)**
- docs/known-limitations.md: the heuristic language check, no Event Hubs adapter, the Azure client
  and App Insights not verified live (worded against docs/AZURE.md so it stays true if the status
  changes), deployment never exercised, the NOR label in the old screenshot folders, the stale
  section 4 of docs/robustness.md, and the null wall-clock fields in exports. Linked from the README.

**Task 2 (deterministic exports)**
- Chose "exclude, keep aside" over a fixed clock: a frozen `verified_at` would be a made-up wall
  time. `run_match` now moves `clock.emitted_latency_ms` (per insight) and
  `verification.verified_at` (per attempt) into `runtime.jsonl` next to `--out` (out/ is
  gitignored) and writes `null` in the exported files; both fields are nullable in the contracts.
  `--keep-runtime-fields` restores the old inline behaviour.
- Two consecutive exports give byte-identical insights.jsonl, claims.jsonl, timeline.json and
  ui.json (checked by hand and by `test_two_exports_are_byte_identical_and_runtime_fields_are_kept_aside`,
  which also checks the latency budget on the runtime values). The number-trace, golden-equality,
  workflow and service tests pass on the re-exported data. The dashboard does not display latency
  or `verified_at`, so nothing on screen changes.
- The agent log (`out/agent_log.jsonl`) keeps its timestamps: it is a runtime log and is not
  committed.

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
