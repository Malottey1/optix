# Optix

**We explain why a match is unfolding, and we catch stats that are true but misleading.**

Optix is a multi-agent engine that turns synthetic football event data into live talking points, timed overlays and recaps. Every statement is backed by evidence events and checked twice before it reaches the screen:

- **Fact check:** does the event log support the claim?
- **Context check:** is it true but misleading given game state, sample size or metric limits? (For example, high field tilt from a team that is trailing and passing around a deep block.)

> Status: contracts and the synthetic data generator are done (40 matches, five fictional teams, planted traps, one showcase match). Engine, agents and dashboard are next.

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

1. Numbers are computed deterministically; language models only write sentences from calculated facts.
2. Claims are verified as language-independent objects, then translated.
3. Everything is explainable: each insight links to the events behind it.
4. Synthetic data only; fictional teams; no real trademarks.
5. Describes the present and past. It does not predict outcomes.

## Repo layout

```
contracts/   JSON Schemas: claim object, insight stream
data_gen/    synthetic data generator
engine/      metrics, style profiles, matchup, momentum, Verifier rules
agents/      agent definitions and orchestration
app/         dashboard
docs/        design notes
tests/       tests
```

See `docs/contracts.md` for how the claim object and insight stream fit together, `docs/data-dictionary.md` for the synthetic data, and `CLAUDE.md` for project rules.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m data_gen.generate --seed 2026   # writes data/generated and data/showcase
python -m pytest -q
```

## License

MIT. See `LICENSE`.
