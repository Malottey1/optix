# IA plan and audit (Step 0)

Audit of the dashboard at 6c3369d (before the information-architecture rebuild). Measured in the
browser with the built site (tools/check_web.py WORDS_JS; script kept in the branch's scratch, numbers
copied here). Nothing is deleted from git: components the new routes stop using are kept and marked
deprecated in their header comment.

## Routes and components

| Route | Page | Components |
|---|---|---|
| `#/` | features/home/HomePage.tsx | hero, proof cards, how-it-works, team badges |
| `#/live` | features/live/LivePage.tsx | Scoreboard, Transport, FocusPitch, Feed, EvidenceDrawer, Flow (rhythm), PerimeterLock, Momentum, LiveShots, CardVisual, MismatchCrosshairs (in a matchup card) |
| `#/teams` | features/teams/TeamsPage.tsx | HeadToHead (MismatchCrosshairs, lane table), StateSwaps (V3), ZoneShift (V10, 15-zone grid), TeamCard x5 (style chips, kits, signature patterns, "Attacks from" and "Concedes" LaneLift tables) |
| `#/players` | features/players/PlayersPage.tsx | ContextCard x6, Profile (PassRoutes V4, PercentilePizza V8, PlayerPatterns), VolumeQuality, ChanceSources, PlayerTable |
| `#/tech` | features/tech/TechPage.tsx | pipeline, one claim end to end, ledger, measured reports, pattern catalogue, visual guide, Azure status |
| any other | redirect to `#/` | |

Shared: components/shell (AppShell, SettingsSheet), components/ui (badge, button, card, segmented,
sheet, tabs, tooltip, skeleton, scroll-region, switch), components/viz (Figure, EvidenceChain,
PatternRoute, ShotBlocks, StateSwaps, ZoneShift, MismatchCrosshairs, PassRoutes, PercentilePizza),
components/pitch/Pitch, components/brand/TeamBadge, icons/.

## What each page reads

| Page | Data |
|---|---|
| Home | ui.teams.teams, ui.ledger, timeline |
| Live | insights, attempts (claims.jsonl), timeline (periods, goals, momentum, players), ui.track, ui.visuals (shots, rhythm, stress), ui.rewrites, ui.reasons, ui.evidence, ui.teams (lanes, head_to_head for the matchup card) |
| Teams | ui.teams (profiles, head_to_head, lanes), ui.visuals (states, zones), ui.track and timeline.periods (zone shift of the showcase match), ui.patterns.signature |
| Players | ui.players, ui.visuals (routes, zones, league_hot_share), ui.patterns.players, ui.evidence |
| Tech | ui.ledger, ui.rewrites, ui.reasons, ui.measured, ui.patterns, ui.azure_status, timeline.periods |

Everything is loaded at start in one bundle (ui.json 1.09 MB, insights.jsonl, claims.jsonl,
timeline.json) for the one showcase match. No per-match data exists for the 40 season matches.

## "Lane" and "mismatch" in the UI (visible text at 1440)

| Where | What | Size | Decision |
|---|---|---|---|
| Teams, Head-to-head panel (first block on the page) | title "Head to head: lane mismatch", subtitle, crosshair chart, verified sentence, lane table | full-width panel, 182 words | remove from Teams; lives in a Match Hub matchup section only when a verified claim exists for that fixture |
| Teams, every team card | "Attacks from" lane lift table (5 rows) | about 40 words per card | replace with one lane-lift heat strip; table kept in a closed "View data" |
| Teams, every team card | "Concedes" lane table and soft-lane sentence or "No lane passes the soft-lane rule." | about 45 words per card | remove the table from view (kept in "View data"); soft-lane note only when the rule passes, else one quiet line |
| Live, matchup card in the stream | "verified claim lane" crosshair label | one card | keep (it is a verified claim in that match) |
| Tech, visual guide | "Mismatch crosshairs" entry | one tile | keep as the one worked example of a Verifier rule, labelled as one of many |

Hidden occurrences (sr-only tables, closed details): 25 on Teams, 2 on Live.

## Visible words per route

| Route | 1440 | 390 |
|---|---|---|
| home | 140 | 140 |
| live | 630 | 621 |
| teams | 984 | 984 |
| players | 1075 | 1075 |
| tech | 2324 | 2324 |

Per card or section (1440, 390):

| Route | Card / section | 1440 | 390 |
|---|---|---|---|
| home | :Match talking points you can trace back  | 43 | 43 |
| home | :In the showcase match | 19 | 19 |
| home | :How Optix works | 53 | 53 |
| home | :The clubs of the synthetic league | 25 | 25 |
| live | :section | 24 | 15 |
| live | focus:Focus Pitch | 53 | 53 |
| live | rhythm:Rhythm | 41 | 41 |
| live | feed-panel:Verified stream | 7 | 7 |
| live | NTG:article | 73 | 73 |
| live | AUR:article | 33 | 33 |
| live | AUR:article | 30 | 30 |
| live | NTG:article | 33 | 33 |
| live | AUR:article | 29 | 29 |
| live | NTG:article | 33 | 33 |
| live | AUR:article | 33 | 33 |
| live | AUR:article | 69 | 69 |
| live | perimeter:Perimeter Lock | 40 | 40 |
| live | momentum:Momentum | 22 | 22 |
| live | stress:Pinned in own half | 60 | 60 |
| live | live-shots:Shot quality | 46 | 46 |
| teams | h2h:Head to head: lane mismatch | 182 | 182 |
| teams | :Lane table: completion conceded and mism | 8 | 8 |
| teams | states:When the score changes | 118 | 118 |
| teams | zone-shift:Where the ball was, half by half | 107 | 107 |
| teams | AUR:AUR | 92 | 92 |
| teams | CAL:CAL | 90 | 90 |
| teams | HAR:HAR | 107 | 107 |
| teams | NTG:NTG | 109 | 109 |
| teams | VES:VES | 108 | 108 |
| players | context:Context the Verifier adds | 34 | 34 |
| players | NTG:Bram Drazek | 75 | 75 |
| players | :Evidence (15 events) | 3 | 3 |
| players | NTG:Callum Corzek | 74 | 74 |
| players | :Evidence (15 events) | 3 | 3 |
| players | AUR:Ennis Quinova | 74 | 74 |
| players | :Evidence (15 events) | 3 | 3 |
| players | AUR:Fabian Hartholt | 74 | 74 |
| players | :Evidence (15 events) | 3 | 3 |
| players | HAR:Marek Belvik | 70 | 70 |
| players | :Evidence (9 events) | 3 | 3 |
| players | VES:Bodhi Belhurst | 70 | 70 |
| players | :Evidence (5 events) | 3 | 3 |
| players | profile:Player profile | 145 | 145 |
| players | volume-quality:Volume against quality | 72 | 72 |
| players | chance-sources:Where the chances come from | 69 | 69 |
| players | deck:All players | 260 | 260 |
| tech | pipeline:Pipeline: math first, language second | 208 | 208 |
| tech | walkthrough:One claim, end to end | 168 | 168 |
| tech | ledger:Verification ledger | 568 | 568 |
| tech | measured:Measured numbers | 80 | 80 |
| tech | :Realism report (seed 2026) (47 rows) | 382 | 382 |
| tech | :xG calibration by bin (full league) (5 r | 8 | 8 |
| tech | :Goal timing (full league, goals by footb | 10 | 10 |
| tech | :League correlations (full league, 20 tea | 8 | 8 |
| tech | patterns:Tactical patterns | 245 | 245 |
| tech | visual-guide:Visual guide | 246 | 246 |
| tech | azure:Microsoft and Azure: what is built and w | 367 | 367 |

The Team Board carries 984 visible words; its five team cards 90-109 each and the head-to-head
block 182. The Player Deck carries 1075, the context cards about 74 each.

## Lineup data (data/generated, the 40-match season the dashboard reads)

| Field | Exists | Notes |
|---|---|---|
| player id, name | yes | players.csv |
| listed position | yes | players.csv `position` (GK, DF, MF, FW) and `role` (goalkeeper, left_back, centre_back_l, ..., striker) |
| shirt number | yes | players.csv `shirt`; the most-started XI of every team wears 1-11, no duplicates in a squad |
| starts per match | yes | lineups.csv `starter` (1/0) per match and player |
| minutes per match | yes | lineups.csv `minutes_played`, `on_sec`, `off_sec` |
| formation | a generator setting only | teams.csv `formation` is a generator input; not used. The label is derived from listed-position counts of the XI ("4-3-3 by listed positions") |
| goals, assists | not as columns | derived from shots (`shot_result` goal) and the assisting pass (`assist_event_id`) |

Most-started XI per team (starts of the 11, then the 12th player's starts): AUR 16..10 (12th 6),
CAL 16..11 (6), HAR 16..11 (7), NTG 16..13 (4), VES 16..11 (5); listed-position counts give 4-3-3
for AUR, CAL, NTG, VES and 4-4-2 for HAR.

## Plan

Steps 1-7 of the brief in order: export (fixture index, per-match recap files, heat bins, lineups,
player summaries), HeatPitch, Fixtures and Match Hub, Team Grid and Team Board with the lineup pitch,
Player Deck and Console, text budget gate, tests and gates. Decisions are logged in docs/PROGRESS.md
("IA decisions"); status in docs/ia-progress.md.
