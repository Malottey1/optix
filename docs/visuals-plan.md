# Visuals plan: data availability audit

Branch `ui-visuals`. Each candidate visual is marked BUILD, ADAPT or SKIP, with the exact ui.json
fields it reads, the formula, and the caveat. "visuals.*" is the new ui.json section written by
`agents/dashboard_data.visuals_section`: plain exports of metrics the engine already computes,
with no new metric (each is tied to its engine function by tests in `tests/test_dashboard_data.py`).

| # | Visual | Verdict | ui.json fields | Formula | Caveat |
|---|---|---|---|---|---|
| V1 | Puncture Point Mismatch Crosshairs | BUILD | `teams.head_to_head[].lanes[l].attack_share`, `.league_share`; defender `teams.teams[].entry_lanes_conceded[l].share`, `.league`; `head_to_head[].claim.lane`, `.status`; stream `matchup_mismatch` payload `metrics.lane` | Bars up = attacker's entry share per lane, bars down = defender's conceded share; league mark on both. Crosshair on `claim.lane` only when `claim.status` is not blocked | Season aggregates, attacker's frame. The defender's own name for a lane is the mirror (`left_flank` ↔ `right_flank`) |
| V2 | Shot-Clustering Scatter Blocks | BUILD | `visuals.shots` = [event_id, clock_sec, team, player_id, x, y, xg, result, shot_type]; claim `window`, `subject` | Block side = k·√xG, so area ∝ xG. Caption: shots, Σxg, Σxg / shots over the claim's window and team | Shot location is the event location; xG from the generator's shot table |
| V3 | Game-State Style Coordinate Swaps | BUILD | `visuals.states[code].{leading,trailing}.{field_tilt,press_intensity}` (value, league, n, interval, confidence); `visuals.state_min_n` | x = field tilt, y = press intensity (`engine.profiles` brackets). A state is drawn only if both metrics have n ≥ `state_min_n` (the engine's medium-confidence sample size, 50) | Season brackets, the team's own score state. Descriptive: a shift is not a cause |
| V4 | Segmented Threat Velocity Arrows | BUILD | `visuals.routes[player_id]` = [kind, from_zone, to_zone, passes, sum]; `visuals.zones` | Zone = third·5 + lane (attacker POV). kind `fwd`: completed forward passes, sum = xT added (`threat.value_at`); `op`/`sp`: key passes open play / set piece, sum = xA. Width ∝ √passes, colour = sum / passes | xT grid is a season possession-value model; zones are coarse (3 × 5) |
| V5 | Territorial Stress gauges | ADAPT | `visuals.stress[code]` = [start_sec, end_sec, seconds, n_events] | The engine's territorial stress is "spells of a team keeping the ball in the opponent's half". Each team's gauge = cumulative seconds of the OPPONENT's spells up to the playhead, i.e. time pinned in its own half | Engine uses the half (x ≥ 50), not the own third, and "no on-ball event by the defending side" rather than "no clean exit". Labelled "pinned in own half" |
| V6 | Rhythm Pulse Waveform | BUILD | `visuals.rhythm` = [period, minute, start_sec, possession_changes, tempo_var] | `engine.flow.rhythm` per period (minutes 45–49 exist in both halves). Height = possession changes in the minute | Whole-second clock; added time is folded into the minute it is logged in |
| V7 | Action Route Circuit Nodes | ADAPT | `evidence[id]` (clock_sec, event_type, player, x, y); insight `evidence_event_ids` | The claim's evidence events in clock order as connected nodes; shape and colour encode event type | No pounce detection in the engine, so this is the evidence chain, not a detected sequence. Evidence is a sample of up to 15 events |
| V8 | Radial Percentile Pizza | BUILD | `players[]`: involvement, pass_completion, forward_passes, wide_share, pass_quality_ratio, chances_open_play, chances_set_piece | Percentile = 100 · (below + ½·equal) / n among outfield players with at least 100 passes (comparison group shown with n) | Percentiles are computed in the page from the engine's per-player values (documented formula, unit-tested, checked by an independent Python recomputation). Season totals, not per 90 |
| V9 | Diverging Performance Bars | SKIP | (none) | — | ui.json has season totals per player only; no per-match player values exist |
| V10 | Zonal Grid Shift Matrix | BUILD if time | `track` = [clock_sec, x, y, team] | Share of a team's on-ball events per zone of its attacking half, first half vs second half | Event locations only; on-ball share, not possession time |
| V11 | Defensive Footprint Polygons | SKIP | (none) | — | The showcase match has two cards, both yellow; no red card to split on |
| — | Off-Ball Attraction Space Vectors | SKIP | — | — | Needs tracking data; the data is event-based |
| — | Weighted Deficit Stack | SKIP | — | — | Needs fatigue / role data; no fitness data by design |
| — | Radar Equilibrium Diamonds | SKIP | — | — | Needs a "service starvation" claim the Verifier does not have |
| — | HIR Decay Lines | SKIP | — | — | Needs GPS speed data |

Export changes (logged in docs/PROGRESS.md under "Visuals decisions"):
- `head_to_head[].claim.lane`: the lane the claim object names (`claim.zone.lane`).
- `visuals` section as above; `ui.json` is now written with compact separators (1.02 MB instead
  of 1.17 MB). No engine, Verifier, Translator or contract change.
