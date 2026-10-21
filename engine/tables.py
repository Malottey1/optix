"""Load the event tables into plain Python structures.

Only observable columns are read. teams.csv and players.csv also carry the generator's hidden
parameters (style seed, lane weights, weak lane, usage, trap flags, ...); the engine never reads
them, so every pattern it reports is rediscovered from events alone.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

TEAM_COLS = ("team_id", "code", "name")
PLAYER_COLS = ("player_id", "team_id", "name", "shirt", "position")
_EVENT_FLOATS = ("x_start", "y_start", "x_end", "y_end")
_EVENT_INTS = ("period", "minute", "second", "clock_sec", "under_pressure", "possession_id",
               "sequence_id", "score_home", "score_away")
_PASS_FLOATS = ("pass_distance_m", "pass_angle_rad", "pass_difficulty", "ball_speed_kmh", "xa")
_PASS_INTS = ("is_forward", "is_progressive", "is_key_pass")
_SHOT_FLOATS = ("shot_distance_m", "shot_angle_rad", "xg", "shot_speed_kmh")
_SHOT_INTS = ("is_big_chance",)
_MATCH_INTS = ("matchweek", "home_score", "away_score")

BRACKETS3 = ("leading", "level", "trailing")


@dataclass(frozen=True, eq=False)       # identity hash, so results can be cached per dataset
class Dataset:
    teams: dict           # team_id -> {team_id, code, name}
    players: dict         # player_id -> {player_id, team_id, name, shirt, position}
    matches: dict         # match_id -> match row
    events: list          # event rows in file order (chronological within a match), + home_team_id
    passes: dict          # event_id -> pass row
    shots: dict           # event_id -> shot row
    label: str = ""       # dataset label (directory name), recorded in claims' baseline_source

    def team_by_code(self, code: str) -> str:
        for tid, t in self.teams.items():
            if t["code"] == code.upper():
                return tid
        raise KeyError(f"unknown team code {code!r}")

    def code(self, team_id: str) -> str:
        return self.teams[team_id]["code"]


def _read(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _convert(row: dict, floats=(), ints=()) -> dict:
    for k in floats:
        row[k] = float(row[k]) if row[k] != "" else None
    for k in ints:
        row[k] = int(row[k]) if row[k] != "" else None
    return row


def load(directory: str | Path) -> Dataset:
    d = Path(directory)
    teams = {r["team_id"]: {k: r[k] for k in TEAM_COLS} for r in _read(d / "teams.csv")}
    players = {r["player_id"]: {k: r[k] for k in PLAYER_COLS} for r in _read(d / "players.csv")}
    matches = {r["match_id"]: _convert(r, ints=_MATCH_INTS) for r in _read(d / "matches.csv")}
    events = []
    for r in _read(d / "events.csv"):
        e = _convert(r, _EVENT_FLOATS, _EVENT_INTS)
        e["sequence_index"] = int(e["sequence_index"]) if e["sequence_index"] != "" else None
        e["home_team_id"] = matches[e["match_id"]]["home_team_id"]
        events.append(e)
    passes = {r["event_id"]: _convert(r, _PASS_FLOATS, _PASS_INTS) for r in _read(d / "passes.csv")}
    shots = {r["event_id"]: _convert(r, _SHOT_FLOATS, _SHOT_INTS) for r in _read(d / "shots.csv")}
    return Dataset(teams, players, matches, events, passes, shots, label=d.name)


def score_diff(event: dict, team_id: str) -> int:
    """Goal difference from `team_id`'s point of view at the moment of the event (before it, if
    the event is itself a goal)."""
    diff = event["score_home"] - event["score_away"]
    return diff if event["home_team_id"] == team_id else -diff


def bracket5(diff: int) -> str:
    """Contract bracket (claim.schema.json game_state.bracket)."""
    if diff >= 2:
        return "leading_2plus"
    if diff == 1:
        return "leading_1"
    if diff == 0:
        return "level"
    return "trailing_1" if diff == -1 else "trailing_2plus"


def bracket3(diff: int) -> str:
    return "leading" if diff > 0 else ("level" if diff == 0 else "trailing")


_INDEX: dict = {}


def match_events(ds: Dataset) -> dict:
    """match_id -> that match's events in order (built once per dataset)."""
    key = (id(ds), "match")
    if key not in _INDEX:
        idx: dict = {}
        for e in ds.events:
            idx.setdefault(e["match_id"], []).append(e)
        _INDEX[key] = (ds, idx)          # keep ds alive so its id is not reused
    return _INDEX[key][1]


def team_events(ds: Dataset, team_id: str | None) -> list:
    """Events (both teams') of every match `team_id` played, in file order; all events if None.
    Every per-team metric only needs these, so profiles pass them instead of the whole table."""
    if team_id is None:
        return ds.events
    key = (id(ds), "team", team_id)
    if key not in _INDEX:
        by_match = match_events(ds)
        evs = [e for mid, m in ds.matches.items() if team_id in (m["home_team_id"], m["away_team_id"])
               for e in by_match.get(mid, ())]
        _INDEX[key] = (ds, evs)
    return _INDEX[key][1]
