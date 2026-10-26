# Personalization

The same verified stream reaches a casual fan and a data-hungry analyst as two different
experiences. Personalization **filters, ranks, relabels and hides**. It never changes a number and
never rewrites a claim sentence: every card it shows is the very object the Verifier passed.

## One config, two implementations

`contracts/personalization.json` (schema `contracts/personalization.schema.json`) is read by
`engine/personalize.py` and by its TypeScript twin `web/src/lib/personalize.ts`:

| Key | Meaning |
|---|---|
| `modes` | `fan`: at most 5 cards (`max_cards`); `analyst`: every card, paged 5 at a time |
| `fan_priority` | insight types in Fan ranking order (then clock, then id) |
| `metrics` | the focus metrics: icon, the insight families they keep, their existing series, whether a played match carries it |
| `glossary` | Fan wording keys for labels, chips and readouts (xG → "Chance quality", xT → "Threat", field tilt → "Territory", PPDA → "Pressing", rhythm → "Match rhythm", momentum → "Who is on top", territorial stress → "Pressure in own half"); never used in claim sentences |
| `not_offered` | metrics with no time series, so no focus readout: field tilt, xT, PPDA |

Metrics offered (each has a series in the data): **momentum** (`timeline.momentum`, also in every
played match file), **xG** (`ui.visuals.shots`, summed per side as the shot captions already do),
**rhythm** (`ui.visuals.rhythm`), **territorial stress** (`ui.visuals.stress`). The data holds no
league-typical reference for these series, and the readout says so.

`tools/personalize_golden.py` writes `tests/fixtures/personalize_golden.json` (14 profiles with the
ids Python selects). `tests/test_personalize.py` and `web/src/lib/personalize.test.ts` both assert
those ids, so the two implementations cannot drift.

## personalize(stream, profile, involved)

Profile: `mode`, `language`, `clubs`, `players`, `metric` (all optional). Order of rules:
player (keep insights whose `player_ids` or evidence events involve the player; `involved` maps an
event id to its player and related player), metric (keep the metric's families), then mode (Fan:
rank, followed clubs first, cap at 5; Analyst: stream order, followed clubs first at the same clock).
Unknown modes and metrics are ignored. An empty profile returns the stream unchanged. The output is a
sub-list of the input objects; the golden tests check values, sentences and determinism.

## Service

`GET /api/match/{id}/stream` takes optional `mode`, `lang`, `club`, `player`, `metric`. Values the
match does not know (an unknown mode, club, player or metric) are dropped, so the stream falls
back to the full one. The chosen insights replay in clock order. `/healthz` is unchanged.

## In the dashboard

- **Fan | Analyst view** (Match Hub header and Settings; Fan by default; stored in localStorage
  `optix.view.v1` inside try/catch). Fan: scoreline, turning points, lineups, one heat map and the top
  five cards (headline, one sentence, a visual, a "Verified" tick that opens the evidence drawer).
  Analyst: everything (paged cards, chips, matchup, event log, ledger). Live Fan: scoreboard,
  scrubber, momentum, the stress gauges and the top feed cards.
- **Follow a player**: "Focus on this player" in the lineup sheet and on the Player Console. The
  hub shows "Following: name ×", highlights the jersey and keeps only that player's insights, with a
  "Player so far" card. In the live hub the card counts the showcase's events up to the clock, from
  `matches/events-m_showcase.json` (agents/showcase_events.py, fetched only while following). A
  played match's file has a thinned log, so its card counts shots, goals, cards and substitutions
  and says so. A player who is not in the match is ignored there.
- **Focus metric**: one large readout for the clock (value, plain one-liner, sparkline), and the
  cards narrow to the metric's families. "None" restores the default view.
- **For you** (Home): appears only when something is starred. It shows followed clubs' fixtures and
  followed players with season goals and assists (or minutes and pass completion). There are no accounts.

## What it cannot do

Personalization cannot compute a metric, change or round a value differently, rewrite or shorten a
claim sentence, or show an insight the Verifier did not pass. tools/check_web.py proves this on the
built site with three checks. Fan numbers are a subset of Analyst numbers. The mode and language
switches change no number. Fan cards keep every number of their claim sentence. Mutations prove
each check: a dropped Fan number, another player's event under focus, and a changed readout are all caught.
