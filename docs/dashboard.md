# Dashboard

A static site in `app/` (HTML, CSS, JS; no build step). It plays the showcase match on a clock and
shows the verified insight stream. The page computes no statistic: every number comes from
`out/insights.jsonl`, `out/claims.jsonl`, `out/timeline.json` (written by `agents.run_match`) or
from the event rows.

```
python -m agents.run_match --match m_showcase --out out/insights.jsonl
python -m http.server 8000          # from the repo root
open http://localhost:8000/app/
```

URL options (also used for the screenshots): `?t=2760&mode=analyst&lang=es&player=NOR_07&select=ins_0011&drawer=1&theme=dark&play=1`.

| Widget | What it shows | Source |
|---|---|---|
| Scoreboard and clock | score at the clock time | `timeline.goals` |
| Feed cards | insight text in the chosen mode and language, type, status badge (✓ verified, ! verified with context), confidence, context chip | `insights.jsonl` |
| Blocked-then-rewritten strip | on cards whose first attempt was blocked: the blocked template, the rule and the params it needed | `claims.jsonl` |
| Evidence drawer | claim value, scope, baseline, supporting values, every verification attempt, evidence events table | `claims.jsonl`, `events.csv` (season preview: payload points) |
| Focus Pitch (SVG) | the selected (or latest) insight's events, zoomed to its focus; lane band for matchups | `payload.points`, `payload.focus` |
| Momentum tug-of-war | engine momentum at the clock (bar) and so far (line, hover for values) | `timeline.momentum` |
| Perimeter Lock | box entries vs final-third passes for the latest perimeter_lock insight | `payload.metrics`, `payload.points` |
| Standard vs honest stat | the shallow stat (struck through) beside the verified sentence | `context_chip`, text |
| Controls | play/pause, speed, scrubber, analyst/casual, language (en/es/fr), player focus | |

Colours: teams use categorical slots 1 and 2 (blue, orange); status badges use the reserved status
colours with an icon and a label, never colour alone. Light and dark themes (OS setting, or
`?theme=`). `prefers-reduced-motion` disables all animation and autoplay.

## Checking it

`python -m tools.check_dashboard` (needs `pip install -r requirements-ui.txt`) serves the repo,
opens eight views in headless Chromium, writes `docs/screens/*.png` and fails on any console error,
page error, failed request or horizontal scroll. The slow test `tests/test_dashboard.py` runs the
same check on a fresh stream.

Screens: kickoff matchup, perimeter lock at half time, blocked-then-rewritten drawer, full time in
Spanish analyst mode, player focus in French, dark mode, mobile (390 px), reduced motion.
