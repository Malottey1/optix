# Realism audit of the synthetic data (v1 generator)

Audit only: this describes the generator as it was before "realism v2" (tag `pre-realism-v2`).
Measured on the full league (20 teams, 380 matches, 682,215 events, seed 2026) and the small league
(5 teams, 40 matches) where noted. Reference ranges come from public sources (listed at the end) or
are marked **approximate** (wide football-knowledge ranges, not measured).

**Verdict rule.** *Inside* = within the range; *Borderline* = outside by at most 10% of the range
midpoint; *Outside* = further, or not modelled at all.

## Summary

The aggregates the v1 generator was calibrated on (goals, shots, corners, home edge, table spread) look
like football. Almost everything it was not calibrated on does not:

1. **Missing game**: no fouls, cards, penalties, free kicks, offsides, throw-ins, substitutions or added
   time. Every team uses the same 11 players all season.
2. **The ball moves wrongly**: back passes are 5% of passes (approximate real range 10-20%), 41% of
   passes start in the final third (approximate 18-30%), and every lost pass is an interception (97 per
   team per match; approximate 7-12).
3. **Wrong chances**: 40% of shots are headers (approximate 12-18%) and 77% are inside the box
   (approximate 60-70%); the xG model itself is well calibrated.
4. **Team identity points the wrong way**: possession correlates negatively with shots (r = -0.39) and
   every team plays 518-605 passes a match regardless of style.
5. **Fixtures**: every full-league team plays one long block of home and one long block of away matches,
   up to 19 in a row.

28 gaps are registered below: 9 High, 11 Medium, 8 Low.

## A. Match-level levels (per team per match unless stated)

| Metric | Reference | Ours (full) | Ours (small) | Verdict (full) |
|---|---|---|---|---|
| Goals per match | 2.85 (22/23), 3.28 (23/24), 2.93 (24/25) [1] | 2.81 | 2.70 | Borderline (long-run 2.6-2.9 Inside) |
| Shots per team | 11-14 (approximate) | 12.2 | 12.0 | Inside |
| Shots on target share | 33-36% (approximate) | 41.0% | 39.1% | Outside |
| Conversion | 10-11% (approximate) | 11.5% | 11.3% | Borderline |
| xG per shot | 0.09-0.12 (approximate) | 0.120 | 0.108 | Inside |
| Season goals vs season xG | within ±10% (approximate) | -3.7% | +4.5% | Inside |
| Corners per team | 4.5-5.5 (approximate) | 5.22 | 5.61 | Inside |
| Passes per team | 400-500 (approximate) | 554 | 559 | Outside |
| Team spread of passes per match | 250-750 (approximate) | 518-605 | 509-589 | Outside |
| Pass accuracy | 80-84% (approximate) | 78.6% | 78.1% | Borderline |
| Possession SD across teams | 6-7 pp (approximate) | 3.9 pp | 4.8 pp | Outside |
| Fouls per team | about 11 (22-23 per match) [2] | 0 | 0 | Outside |
| Yellow cards per match | 4.2 (23/24 record) [3] | 0 | 0 | Outside |
| Red cards per match | 0.05-0.12 (approximate) | 0 | 0 | Outside |
| Offsides per team | about 2 (approximate) | 0 | 0 | Outside |
| Crosses per team / completion | 15-20 / 25-30% (approximate) | 19.2 / 28.7% | 20.1 / 30.2% | Inside |
| Tackles / interceptions per team | 15-20 / 9-12 (approximate) | 15.1 / 96.6 | 15.4 / 99.8 | Inside / Outside |
| Penalties per match | 0.28 (23/24), about 0.23 (24/25 part) [4] | 0 | 0 | Outside |
| Set-piece goal share | 19.8% excl. penalties (23/24) [5] | 7.3% | 11.1% | Outside |
| Shots inside the box | 60-70% (approximate) | 77.3% | 77.7% | Outside |
| Headers share of shots | 12-18% (approximate) | 39.9% | 44.4% | Outside |
| Mean shot distance | 16-18 m (approximate) | 15.7 m | 16.0 m | Borderline |
| Home / draw / away | 40.8 / 24.5 / 34.7% (24/25) [6]; about 48% home (22/23) [7] | 41.3 / 26.1 / 32.6 | 47.5 / 30.0 / 22.5 | Inside |
| Champion / bottom points | 80-95 / 20-35 (approximate) | 84 / 23 | n/a | Inside |
| Added time per match | 507 s (22/23) and 702 s (23/24) beyond 90 min [8] | 0 | 0 | Outside |
| Ball in play | 54:49 (22/23), 58:11 (23/24) [9] | about 85 min | about 85 min | Outside |
| Substitutions per team | 3-5 (approximate; five allowed) | 0 | 0 | Outside |
| Players used per team per season | 20-27 (approximate) | 11 | 11 | Outside |

Home/draw/away: v1's calibration target was 38/30/32 with a ±15-point tolerance. The recent seasons
above are more defensible (draws near 25%, not 30%), so v2 uses ranges from them.

## B. Distribution shapes (ours, full league)

- **Goals per team per match vs Poisson** (team mean at home/away): variance/mean 0.98 (real about
  1.0-1.2, approximate), chi-square 10.35 on 4 dof (p about 0.035): slightly too few 0-goal and 5+ games.
- **Goals by 15-minute block**: 16.0 / 14.7 / 18.3 / 17.6 / 15.3 / 18.0%. Approximate real shape:
  lowest at the start (about 14%), highest late (20-22%; 26.3% after minute 75 in one season [10]).
  Too flat; no added-time goals at all.
- **Shot xG bands**: <0.05: 35.6%, 0.05-0.15: 40.8%, 0.15-0.3: 11.8%, >0.3: 11.8%. Real is more
  skewed to low values (approximate: about half below 0.05, under 8% above 0.3).
- **Shot locations**: a third of all shots from 6-11 m central (headers from crosses); only 3% from
  central 16.5-25 m; about 5% from 35 m+ in the outer lanes.
- **Pass length** (m, share): 0-5 10.9, 5-10 10.9, 10-15 13.7, 15-20 15.0, 20-25 12.9, 25-30 10.3,
  30-40 14.2, 40-50 7.0, 50+ 5.0. Real passing peaks at 5-15 m (approximate); ours is flat.
- **Direction (by angle)**: forward 23.1%, lateral 71.6%, back 5.3%. Approximate real: forward
  30-40%, back 10-20%.
- **Completion by third**: 78 / 80 / 78%; final third should be clearly lowest (approximate).
- **Possessions**: 4.2 passes per possession (median 3, p95 12) is plausible; gaps between passes or
  shots are too regular (p99 13 s; real dead-ball pauses are 20-60 s).
- **Variability**: SD of a team's passes across its matches 97 vs SD between team means 25: team style
  barely shows in passing volume.

## C. Structural checks (ours, full league)

| Check | Result |
|---|---|
| Completed pass → next on-ball event by the recipient at the pass end | 631 violations of 330,863, all "successful" corners where nobody acts next |
| Failed pass → opponent gains at the mirrored point | 0 violations |
| Same player, under 5 s, over 40 m apart | 2,288 (6.0 per match): pressers and interceptors picked from home positions |
| Goalkeeper share of interceptions / tackles | 12.3% / 7.3% (approximate real: near 0) |
| Pass flight vs gap to next event | 21% of passes are followed by the next event in the same second |
| Pass difficulty vs completion | within 1.5 points per bin (circular by construction) |
| xG calibration by bin | within a few points up to 0.3; 0.59 mean xG scored 49% (69 shots) |
| Referential integrity, scores, clock | clean |
| Half-time | 2,617 events labelled period 2 before the second-half kick-off |
| Fixtures | each team once per week, each pair once each way; but venue blocks up to 19 in a row (CAL: 19 away then 19 home) |
| Calendar | 38 Saturdays, all 10 matches on one date |
| Names | 20 × 20 name pool: 51 duplicate names among 220 players; every team wears 1-11 in one 4-3-3 |

## D. League level (ours, full league)

- Champion JPH 84 points, bottom HBC 23; points SD 14.4; goal difference -37 to +32.
- Split-half persistence (odd vs even matches): xG difference 0.85, shot share 0.75, possession 0.93,
  goal difference 0.62 (approximate real 0.7-0.9 for xG difference and shot share).
- Team-season correlations: possession-shots **-0.39**, shots-goals 0.59, xG-goals 0.87,
  possession-pass accuracy 0.96, PPDA-possession **+0.11** (approximate real: possession-shots
  clearly positive, PPDA-possession clearly negative).
- PPDA 6.3 (team range 5.4-7.4); approximate real 8-16.
- Home goal edge +0.29 per match (approximate real 0.25-0.40).
- Teams: archetypes are distinct but extremes overshoot: high-press teams make about 150 pressures and 27
  tackles a match against 32 and 6 for JPH; direct LMF plays 560 passes at 44.5% possession, the same
  volume as possession side QNT (569 at 56.8%).

## E. Coverage gaps vs a real event feed

| Element | v1 | Effect of adding it | Effort |
|---|---|---|---|
| Fouls, free kicks | Missing | PPDA foul term, free-kick set pieces, discipline | M |
| Yellow / red cards | Missing | red-card game state (10 v 11), suspensions | S |
| Penalties | Missing | npxG differs from xG | S |
| Throw-ins, goal kicks, offsides | Missing | realistic restarts and dead time | S |
| Clearances, blocks | Missing / partial | defensive actions, low-block reading | S |
| Carries, dribbles | Missing | progression off the pass; fewer teleports | M |
| Duels (aerial, ground) | Partial (tackle) | headers need an aerial contest | M |
| Goalkeeper saves, claims, distribution | Partial | keeper actions, build-up from the back | M |
| Substitutions, lineups, bench, formations | Missing | player focus across matches, minutes | M |
| Injuries | Missing | dead time, forced substitutions | S |
| Added time, half and full-time whistles | Missing | 45+ / 90+ events, end-of-half triggers | S |
| VAR | Missing | reviewed goals and penalties | M |
| Body part for passes, second assists | Missing | aerial passing, build-up credit | S |
| Freeze frames, player ratings | Missing (keep out: tracking-derived or subjective) | — | — |

## F. Realism gap register

| ID | What is wrong | Evidence (ours) | Severity | Fix (effort) |
|---|---|---|---|---|
| G01 | No squads, substitutes or rotation | 11 players used per team per season; 0 subs | High | squads, lineups, subs (M) |
| G02 | No fouls, cards, penalties, free kicks, offsides | all 0 | High | discipline layer (L) |
| G03 | Every lost pass is an interception or tackle | 96.6 interceptions per team | High | lost-pass outcome model (M) |
| G04 | Pass vectors: almost no back passes, flat lengths | back 5%, lateral 72%, 30-40 m 14% | High | zone-conditioned pass vectors (M) |
| G05 | Passing volume ignores style; final third overloaded | 554 passes per team, team means 518-605; 41% of passes in final third; possession SD 3.9 pp | High | style-driven retention and volume (M) |
| G06 | Chance mix too cross-and-header | headers 40%, inside box 77%, on target 41%, xG > 0.3 12% | High | chance-mix model (S-M) |
| G07 | Fixture venues in long blocks | runs up to 19 home or away | High | alternating schedule (S) |
| G08 | No dead ball or added time | about 85 min ball in play; 0 added time | High | restarts with durations, added time (M) |
| G09 | Wrong-sign team relationships | possession-shots -0.39; PPDA-possession +0.11 | High | couple possession, territory, chances (S-M) |
| G10 | Pressing and tackling caricatures | pressures 32-156, tackles 5.6-27.5 per team | Medium | bounded press dial (S) |
| G11 | Teleporting players | 6.0 per match | Medium | positional anchors, involvement guard (S-M) |
| G12 | Set-piece goals too rare | 7% of goals | Medium | free kicks, penalties, corner play (M) |
| G13 | Goal timing flat | 0-15: 16%, 76-90: 18% | Medium | intensity ramp, added time (S) |
| G14 | xG not skewed to low values | <0.05 only 36% of shots | Medium | with G06 (S) |
| G15 | Team identity weak in passing | between-team pass SD 25 vs within 97 | Medium | with G05 (S) |
| G16 | Too many through balls | 19 per team per match (approximate real 1-3) | Medium | relabel counter balls (S) |
| G17 | Goalkeepers act as outfielders | 12% of interceptions, 7% of tackles | Medium | keeper-specific actions (S) |
| G18 | Unrealistic calendar | 38 Saturdays, one date per round | Medium | weekend slots, midweek rounds (S) |
| G19 | Half-time overrun labelled period 2 | 2,617 events | Medium | half-end whistle (S) |
| G23 | Thin naming, one formation | 51 duplicate names; all 4-3-3, shirts 1-11 | Medium | large invented pool, formations (S) |
| G20 | Scorelines a little too predictable | variance/mean 0.98; chi-square p 0.035 | Low | match-level variance (S) |
| G21 | Instant turnovers | 21% of passes followed in the same second | Low | flight time before turnover (S) |
| G22 | "Successful" corners with no follow-up | 631 | Low | first-contact events (S) |
| G24 | Pass accuracy slightly low | 78.6%, best team 84% | Low | with G05 (S) |
| G25 | Completion flat by third | 78 / 80 / 78% | Low | with G04 (S) |
| G26 | Speculative wide long shots | about 5% of shots | Low | shot zones (S) |
| G27 | Extreme luck outliers | best xG difference finishes 12th | Low | with G20 (S) |
| G28 | No final whistle | 435 events 90:00-90:16 | Low | with G08 (S) |

The "realism v2" work that addresses these is logged in `docs/PROGRESS.md`.

## Sources

1. Goals per match: The Analyst, https://theanalyst.com/articles/numbers-behind-premier-league-goal-explosion
   (2.85 in 22/23, 3.28 in 23/24); 2024/25 1,115 goals, 2.93 per match,
   https://en.wikipedia.org/wiki/2024%E2%80%9325_Premier_League
2. Fouls: about 22-23 fouls awarded per match by referees, https://www.olbg.com/blogs/men-middle-premier-league-referee-performances
   and https://theanalyst.com/articles/stat-viz-quiz-29-ref-data-erling-haaland-wayward-day-birthday-bonuses
3. Yellow cards: The Analyst, https://theanalyst.com/articles/new-premier-league-records-on-the-cards (4.2 per
   match in 23/24, a record; 5.1 early in 24/25)
4. Penalties: premierleague.com, https://premierleague.com/news/4029218 (107 in 23/24, 0.28 per match);
   The Analyst, https://theanalyst.com/articles/who-has-won-the-most-penalties-premier-league (about 0.23 per
   match part-way through 24/25)
5. Set pieces: https://www.fantasyfootballscout.co.uk/2025/10/18/just-how-important-are-set-pieces-in-fpl
   (19.8% of goals from set pieces excluding penalties in 23/24, 247 of 1,246)
6. 2024/25 results split (155 / 93 / 132): https://www.fiso.co.uk/premier-league-scoring-trends-2024-25-season-vs-2025-26-gw25-whats-changed/
7. Home wins in 22/23 near a record high: premierleague.com, https://www.premierleague.com/news/2916832
8. Added time: premierleague.com, https://www.premierleague.com/news/3860720 (seconds beyond 90 minutes
   507 in 22/23, 702 in 23/24)
9. Ball in play: The Analyst, https://theanalyst.com/articles/match-time-ball-in-play-referees-stats
10. Late goals: premierleague.com, https://premierleague.com/news/3871035
