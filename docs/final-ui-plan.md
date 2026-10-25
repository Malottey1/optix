# Final UI plan and audit

Branch `ui-visuals-final-ui`, from a8ab229 (main = ui-visuals-ia; local tag `pre-final-ui`).
Item status: docs/final-ui-progress.md. Decisions: docs/PROGRESS.md, "Final UI decisions".

## 1. Data audit (dashboard season data/generated, 40 matches, 82,946 events; showcase data/showcase)

Facts measured with a csv scan of the generated tables (no generator change).

| Question | Answer | Field(s) |
|---|---|---|
| Tackles with a player id | yes, 1,568 | events.event_type `tackle`, player_id |
| Tackle outcome (won/lost) | yes: success 1,285, fail 283 | events.outcome |
| Interceptions | yes, 803 (outcome always success) | `interception` |
| Blocks | yes, 729 | `block` |
| Clearances | yes, 1,427; body_part head 1,107, foot 320 | `clearance`, body_part |
| Fouls committed | yes, 743 (outcome free_kick 734 / penalty 9; related_player_id = player fouled) | `foul` |
| Cards | yes, 150: yellow 142, second_yellow 7, red 1 | `card`, outcome |
| Pressures | yes, 5,988 (outcome `applied`) | `pressure` |
| Pressure regains | not a field; derivable only by a sequence rule (not exported, see decisions) | – |
| Ball recoveries | yes, 4,539 | `ball_recovery` |
| Duels | yes, aerial only: 9,588, all body_part head, success 4,927 / fail 4,661 | `duel` |
| Ground duels / dribbles past | dribbles 778 (success 418) by the ball carrier; no ground-duel event | `dribble` |
| Shot result values | goal 133, saved 247, blocked 285, off_target 447 (on target = goal + saved) | shots.shot_result |
| Shot type | open_play 860, header 155, set_piece 68, free_kick 20, penalty 9 | shots.shot_type |
| Keeper on shots | **no**: shots carry team_id only. Every `saved` shot is followed (0-1 s) by a `save` event whose player_id is the keeper (247 = 247, all GK). Goals carry no keeper | `save` (outcome held 117 / parried 130), `claim` (135) |
| Keeper location on saves | no: save events sit at a fixed x = 4 | – |
| Lineups | match_id, team_id, player_id, role, starter, on_sec, off_sec, minutes_played, sent_off | lineups.csv |
| Substitutions | yes, 367 events: player_id = player off, related_player_id = player on, outcome fatigue/tactical/injury; on_sec/off_sec in lineups agree | `substitution` |
| Keeper substitutions | 3 in the season (so "keeper on the pitch" matters) | lineups |
| Shirt, position | players.csv shirt, position (GK/DF/MF/FW), role | players.csv |
| Player minutes per match | yes, lineups.minutes_played (109 players with minutes) | lineups.csv |
| Pass flags | is_forward 16,539, is_progressive 14,346, is_key_pass 993 | passes.csv |
| Pass types | short, long_ball, throw_in, through_ball, cross, free_kick, goal_kick, corner | passes.pass_type |
| xA | passes.xa: > 0 on exactly the 993 key passes, and equal to the assisted shot's xg in all 993 (shots.assist_event_id links back) | passes.xa, shots.assist_event_id |
| Key pass start / end | events x_start, y_start, x_end, y_end (acting team's attacking frame) | events |
| Keeper distribution | 1,412 keeper passes (goal_kick 598, short 552, long_ball 255); pass_distance_m quartiles 13.6 / 20.1 / 32.3 m | passes.pass_distance_m |
| Line-breaking passes | **not observable**: needs opponent positions | – |
| Formations | **not observable** (teams.csv formation is a generator input, never read) | – |
| Off-ball movement | **not observable** (no tracking) | – |
| Keeper post-shot quality (PSxG) | **not observable**: no shot placement or speed on target model | – |

Coordinates: every event is in the acting team's attacking frame. Defensive actions are therefore in
the defender's own frame (x = 0 its own goal). Shots faced are mirrored into the keeper's defending
frame (x' = 100 - x, y' = 100 - y) for the keeper map.

## 2. Claim audit: Matchup

- **Rule and producer.** The lane claim is `metric: zone_mismatch`, `insight_type: matchup_mismatch`,
  made by `engine.matchup.matchup_claim` and proposed by `agents/analyst.py::_preview` at kick-off for
  each direction. No context rule in engine/rules/ handles it. The Verifier's fact check recomputes
  every value (`engine/claims.py::_zone_mismatch`), and it always matches, so the claim publishes.
- **Thresholds.** In `engine.matchup.lane_matchup`, a lane is a candidate when
  `attack_pp > 0 and completion_pp > 0`. Those are the attacker's share of final-third entries into
  the lane minus the league share, and the defender's conceded entry-pass completion rate in the lane
  minus the league's. There is no minimum size and no confidence floor; the top lane is the largest
  `attack_pp + completion_pp`. The thresholds are inline literals, not config.
- **Season or fixture.** It is season level: `matchup_claim(self.season, att, dfn)` uses the whole
  dashboard season, including later matches (the evidence ids of m_001's claim come from m_004 and
  m_005). Every fixture of the same pair therefore shows the same lane and numbers. The 61 published
  directions all equal the ui.json head-to-head row for that pair (checked).
- **Why 37 of 41.** With five lanes and two signs, almost every ordered pair has some lane where both
  differences are above zero: 15 of the 20 ordered pairs do. Most are tiny. HAR to CAL left half-space
  is +0.2 pp and +0.1 pp; 40 of 61 directions are "low" confidence.
- **Numbers it cites.** attack_share and league_share (percent), concede_completion and
  league_completion (percent), plus supporting values: concede_share, attack_effect_pp,
  completion_effect_pp, mismatch_pp and the samples.
- **Ring against the bars.** The current crosshairs draw the defender's share of entries *conceded*
  (concede_share) as the down bars, but the rule uses completion conceded. For AUR attacking NTG,
  the claim lane is the left flank because NTG concede +12.0 pp completion there. The displayed down
  bar shows NTG's share of entries conceded on the left flank, which is not what the rule tested, so
  the ring can sit on a lane whose bars show no gap. Report only: the rule is unchanged.

## 3. UI audit (measured on the a8ab229 build)

- **Match Hub, final (m_001).** Heat Maps and the cards sit in one 6/6 row, followed by Matchup and
  the event log. The cards column is 2,887 px tall and the heat column 639 px, so:

  | Viewport | Empty space under Heat Maps |
  |---|---|
  | 1440 | 2,248 px |
  | 1920x1080 | 2,524 px |
  | 390 (stacked) | none, but the cards section alone is 5,100 px |

  The page is 4,421 px tall at 1440.
- **Home.** Hero, then three proof numbers, three feature tiles with drawings, then the clubs row.
  There is no match content, and no insights, players or patterns.
- **Team Board.** The style block is a ratio pizza: slice = value / league, capped at 1.6x. There is
  no shared scale across teams, and the unit is not shown on the slices.
- **Player Console.** Built for passers. The pizza compares against all outfield players with at
  least 100 passes, not position peers. Defenders and keepers get the same passing visuals; nothing
  is defensive or keeper-specific.
- **Nav.** Fixtures, Teams, Players, Tech, plus Settings, with Home on the logo. Settings holds
  language, display switches and a note. The kits note repeats on the Team Grid and the Board.

## 4. Design decisions (filled in as built)

See docs/PROGRESS.md "Final UI decisions" for the running log; the final list is copied here at the end.
