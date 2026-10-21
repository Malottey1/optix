# Engine (v1)

Pure, stdlib-only Python over the CSV tables. It never imports the generator and never reads
`ground_truth.json`; the loader (`engine/tables.py`) also drops the hidden generator columns in
`teams.csv` and `players.csv`. Only tests compare engine output with ground truth.

| Module | What it does |
|---|---|
| `zones.py` | lanes, thirds, final third, box; attacker point of view; `flip` to change frame |
| `tables.py` | load a data directory; game state of an event for a team (`score_diff`, 3 and 5 brackets) |
| `metrics.py` | metric functions; each returns `MetricResult(value, evidence_event_ids, sample_size, sd, detail)` and documents definition, inputs and known limits |
| `profiles.py` | `team_style_profile(ds, team, bracket)` against the league average in the same bracket; `bracket_shift` for own-bracket changes |
| `matchup.py` | `lane_matchup` (attack share vs defender concede share per lane) and `matchup_claim` (pending claim object) |
| `report.py` | `python -m engine.report --team AUR --opponent NOR [--data DIR] [--json]` |

## Reading the numbers

- League average is the metric pooled over every team in the same game-state bracket.
- z-scores are sampling z-scores against that average. They grow with sample size, so over a
  season most style differences are "significant"; read value, league value and n together.
  Event-level observations within a match are not independent, so treat z as a ranking signal,
  not a p-value.
- Mismatch score per lane = (attacker z + defender concede z) / sqrt(2), only counted when both
  are positive.
- Pressing: `press_intensity` (pressures per opponent pass) is the press signal. `ball_won_height`
  mostly reflects where the opponent plays and does not single out the pressing team on this
  data; standard `ppda` (tackles and interceptions only) does not either.

## Known gaps

- HAR's planted weak lane (`right_flank`) is not recoverable from the current season: the share
  of entries HAR concedes there is at the league average. Either the plant is too weak in the
  generator or it needs a completion-rate metric rather than a share.
- npxG equals xG because the data has no penalties yet.
