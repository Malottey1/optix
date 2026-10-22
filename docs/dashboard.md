# Dashboard

`app/` is a React app with no build step. It replays the showcase match on a clock and shows the
verified insight stream, team style fingerprints, player context and how the pipeline checks
itself. The page computes no statistic. Every number comes from the files `agents.run_match` writes:
- `out/insights.jsonl`
- `out/claims.jsonl`
- `out/timeline.json`
- `out/ui.json` (built by `agents/dashboard_data.py` from engine/ outputs and the generated reports in docs/)

```
python -m agents.run_match --match m_showcase --out out/insights.jsonl
python -m http.server 8000          # from the repo root
open http://localhost:8000/app/
```

## Stack

- **React 18.3.1 and ReactDOM**, self-contained production ESM builds, plus **htm 3.1.1** for JSX-like
  tagged templates. Native browser ES modules: `index.html` has an import map that maps `react`,
  `react-dom/client` and `htm` to `./vendor/`, and loads one `<script type="module" src="./main.js">`.
- **Tailwind CSS 4.1.11 browser build** (`@tailwindcss/browser`), loaded from `./vendor/`. Colour tokens
  live as CSS variables in `app/styles/theme.css` and are mapped to Tailwind colours with `@theme inline`
  in `index.html`. The body background is set in plain CSS, so there is no white flash before Tailwind runs.
- **Hash routing:** `#/live`, `#/teams`, `#/players`, `#/tech`.
- **Native SVG** for the pitch, lanes, momentum, the Perimeter Lock and the pipeline diagram. There is
  no canvas and no chart library. Marks carry `data-event-id`, `data-lane`, `data-team` and similar
  attributes, so tests can inspect them.
- **System font stack** with tabular numerals.

There is no package.json, lockfile, bundler, build config or node_modules. The vendored files were
downloaded once with curl. `app/vendor/VENDOR.md` lists each one with its source URL, version, SHA-256
and licence. At runtime the page requests nothing except the server it is loaded from.

Code layout:
- `app/main.js`: data loading and routing.
- `app/lib/`: data loader, replay clock store, settings, interface strings, formatting.
- `app/components/`: shell and navigation, settings tray, pitch, Live Center widgets, insight cards
  and evidence drawer.
- `app/pages/`: one module per route.

Replay: `requestAnimationFrame` advances a small external store. Each component subscribes to the
slice it needs with `useSyncExternalStore` and a selector:
- the clock and scrubber update each frame;
- the ball marker updates when the latest event changes;
- momentum updates once per match minute;
- the feed updates when a new insight arrives.

## Pages

| Route | What it shows | Source |
|---|---|---|
| `#/live` Live Center | Scoreboard with a momentum tug-of-war; play, pause, scrub and speed; SVG Focus Pitch with the selected or latest insight's evidence and a ball marker at the latest event location (an event-based proxy, labelled as such); momentum chart; Perimeter Lock; the stream of verified cards. Each card has a headline (the stream's casual sentence), confidence, evidence count and attempt count, and an evidence drawer with the claim, every verification attempt and the evidence events. A card whose first attempt was blocked shows "Rewritten after verification", a Before / After toggle (the blocked claim's own wording vs. the published one) and the rule's reason in one sentence | `insights.jsonl`, `claims.jsonl`, `timeline.json`, `ui.json` (rewrites, reasons, evidence, track) |
| `#/teams` Team Board | Per team: style labels (tempo, press, passing, territory, counters), each with its rule and numbers in a tooltip (`engine/style_labels.py`); entry lanes against the league; soft lane (`engine.profiles.soft_lane`). Head to head: any attacker and defender, lane mismatch on a pitch in the attacker's frame, the verified matchup sentence, and the per-lane table | `ui.json` teams |
| `#/players` Player Deck | Involvement (`engine.metrics.involvement`), pass completion, forward passes, wide share, pass quality, chances created (open play / set piece). The Verifier's context cards for the volume passer and the set-piece creators, with Before / After and the reason | `ui.json` players |
| `#/tech` Tech Blueprint | Pipeline (Analyst → Verifier → Narrative with number guard); the verification ledger (every claim: passed / passed with context / revised / blocked, and the rule that decided it); the measured numbers, parsed from docs/realism-report.md, docs/robustness.md and docs/verifier-recall.md; "Planned Azure integration (not built)" | `ui.json` ledger, measured |

Settings (slide-over, not a page):
- language: en / es / fr, which switches between the stream's own translated, number-guarded sentences;
- reduce motion;
- density;
- show evidence by default;
- high contrast.

They are saved in localStorage inside try/catch, so the app works when storage is blocked. The dark
theme is the only theme. Only the insight sentences and the main interface strings are translated;
the Team Board, Player Deck and Tech page explanations are English. Each theme colour (status, team,
accent) appears with an icon or a label, never alone.

View options for screenshots and tests: `#/live?t=2760&select=ins_0009&lang=es&play=1`.

## Not available in this dataset

- **Minutes played.** Player figures are season totals, not per 90.
- **Positions or tracking.** Nothing on the Player Deck uses fatigue, distance, speed or fitness.
  The ball marker on the Focus Pitch is the location of the latest event, not a tracked ball.

## Checking it

`python -m tools.check_dashboard` (needs `pip install -r requirements-ui.txt`) serves the repo and opens
every route at 1440 px and 390 px in headless Chromium. It writes `docs/screens/<route>_<desktop|mobile>.png`
plus `live_1080p.png` (the first screen at 1920×1080), each under 300 KB. It fails on any of:
- a console error, page error, failed request, HTTP error, or request to a host other than localhost;
- horizontal scroll;
- overlapping text (text line boxes inside `<main>`, clipped by their scroll containers);
- a control that Tab never reaches;
- Tailwind not applied (computed styles of known utilities);
- an evidence drawer that lists an event id not in the stream;
- a number on screen that does not trace to the data (football clock times and counts of listed
  items are the only derived numbers);
- a language switch that changes a number, or a sentence that fails the number guard;
- a forbidden word (real club names, prediction or betting language);
- an error with storage blocked or with reduced motion.

It also records replay frame times while the match plays at fast speed. The slow test
`tests/test_dashboard.py` runs the same checks on a freshly streamed match. The fast tests:
- `tests/test_ui_stack.py`: no build tooling, no remote URLs, import map targets exist, VENDOR.md
  checksums match;
- `tests/test_dashboard_data.py`: ui.json content;
- `tests/test_number_trace.py`: the number tracer.

The first dashboard (plain HTML and vanilla JS) is kept for reference in `legacy/dashboard-v1/`.
