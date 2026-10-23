# Optix

**We explain why a match is unfolding, and we catch stats that are true but misleading.**

Optix is a multi-agent engine that turns synthetic football event data into live talking points, timed overlays and recaps. Every statement is backed by evidence events and checked twice before it reaches the screen:

- **Fact check:** does the event log support the claim?
- **Context check:** is it true but misleading given game state, sample size or metric limits? (For example, high field tilt from a team that is trailing and passing around a deep block.)

> Status: data generator (small and 20-team league), engine (metrics, effect sizes, xT, flow), Verifier with nine context rules, agents with a block-and-revise loop, timed insight stream in English, Spanish and French, and a dashboard in `web/` (Vite, React, TypeScript: Live Center, Team Board, Player Deck, Tech Blueprint). See `docs/PROGRESS.md`.

## Who it is for

Fans (second-screen explanations and recaps), broadcasters and studios (trustworthy on-air talking points), and streaming platforms (recaps and overlays at scale). Clubs and leagues own the data; they are not the users.

## Pipeline

| Stage | Component |
|---|---|
| Ingest | Ingest agent and event stream |
| Interpret | Analyst agent: style profiles, matchup vulnerability, xT, momentum |
| Explain | Narrative agent plus Verifier (fact and context check) |
| Render | Timed insight stream, dashboard with Focus Pitch |
| Personalize | Personalization agent: analyst/casual, favorite club, player focus, single metric, language |

## Design principles

1. Numbers are computed deterministically; sentences are filled from templates with already-calculated facts (no language model is used in this build; LLM phrasing is planned and would only reword those facts behind the same number guard).
2. Claims are verified as language-independent objects, then translated.
3. Everything is explainable: each insight links to the events behind it.
4. Synthetic data only; fictional teams; no real trademarks.
5. Describes the present and past. It does not predict outcomes.

## Repo layout

```
contracts/   JSON Schemas: claim object, insight stream
data_gen/    synthetic data generator
engine/      metrics, style profiles, matchup, momentum, Verifier rules
agents/      Ingest, Analyst, Verifier, Narrative, Personalization agents; orchestrator; stream; templates
web/         dashboard (current): Vite + React + TypeScript, Tailwind, hand-written SVG; data in web/public/data
app/         deprecated no-build dashboard (reference only; replaced by web/)
tools/       headless dashboard checks (check_web for web/), report generators
legacy/      the first dashboard (deprecated, reference only)
docs/        design notes
tests/       tests
```

See `docs/contracts.md` for how the claim object and insight stream fit together, `docs/data-dictionary.md` for the synthetic data, and `CLAUDE.md` for project rules.

## Quick start (5 commands)

```bash
python3 -m venv .venv && source .venv/bin/activate      # 1. fresh environment (Python 3.10+)
pip install -r requirements-dev.txt                      # 2. jsonschema + pytest, nothing else
python -m data_gen.generate --seed 2026                  # 3. season (data/generated) + showcase match
python -m agents.run_match --match m_showcase --out out/insights.jsonl   # 4. stream the match through the agents
cd web && npm ci --ignore-scripts && npm run dev        # 5. dashboard on http://127.0.0.1:5173/ (Node 20.19+)
```

Optional:

```bash
python -m pytest -q                                      # tests (slow ones: -m slow)
python -m engine.report --team AUR --opponent NTG        # style profiles and matchup, as text
python -m agents.personalize --mode casual --lang es --favorite NTG   # personalized feed in the terminal
python -m data_gen.generate --league full                # 20 teams, 380 matches (data/full, ~15 s)
cd web && npm run build && npm run preview               # production build in web/dist, served on :4173
pip install -r requirements-ui.txt && python -m tools.check_web     # headless gates on every route + docs/screens-v3/
```

What you get: `out/insights.jsonl` (timed insights, contracts/insight.schema.json), `out/claims.jsonl`
(every verification attempt, including blocked ones), `out/timeline.json` and `out/agent_log.jsonl`
(structured logs), `out/ui.json` (team, player, ledger and report data for the dashboard). Architecture: `docs/ARCHITECTURE.md`. Engine and Verifier: `docs/engine.md`.
Dashboard (stack, pages, checks): `docs/dashboard.md`. Visuals (what each draws, formula, caveats, skipped ones): `docs/visuals.md`.

## Not built yet (planned)

These are design intentions, not features of this repo:

- Azure deployment (hosting, Event Hubs ingestion, Application Insights telemetry) and any
  Microsoft Agent Framework wiring. The agents here are plain Python classes run in one process.
- Live LLM phrasing. Every sentence today comes from the templates in `agents/templates/`.

## License

MIT. See `LICENSE`.
