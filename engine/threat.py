"""Expected threat (xT) on a 12 x 8 grid, threat added per pass, and pass quality ratio.

Grid value (a simple possession-value model, derived from the baseline season):
    V(zone) = mean, over every on-ball action (pass or shot) that STARTS in the zone, of the total
              xG of the shots that end that possession.
So V is "how much xG a possession that has the ball here goes on to produce". Possession =
(match_id, possession_id, acting team); every event is in the acting team's attacking frame.

Threat added by a completed pass = V(end zone) - V(start zone). Failed passes get 0 here (the
loss of the ball is a separate story). Known limits: no carries in the data, so ball progression
by dribbling is invisible; zones with few actions are noisy (cells with fewer than MIN_CELL_N
actions borrow the mean of their column); V is fitted on the season and applied to a match,
never fitted on the match itself.
"""
from __future__ import annotations

from collections import defaultdict

from .metrics import MetricResult, _acting, _completed_passes
from .tables import Dataset, baseline_of
from .zones import BOX_Y, FINAL_THIRD_X

NX, NY = 12, 8
MIN_CELL_N = 30
_GRIDS: dict = {}


def cell(x: float, y: float) -> tuple[int, int]:
    return min(int(x / (100 / NX)), NX - 1), min(int(y / (100 / NY)), NY - 1)


def fit_grid(events, shots) -> list[list[float]]:
    """V[i][j] for column i (x) and row j (y), from events and the shots table."""
    poss_xg = defaultdict(float)
    for e in events:
        if e["event_type"] == "shot":
            poss_xg[(e["match_id"], e["possession_id"], e["team_id"])] += shots[e["event_id"]]["xg"]
    tot = [[0.0] * NY for _ in range(NX)]
    cnt = [[0] * NY for _ in range(NX)]
    for e in events:
        if e["event_type"] not in ("pass", "shot"):
            continue
        i, j = cell(e["x_start"], e["y_start"])
        tot[i][j] += poss_xg.get((e["match_id"], e["possession_id"], e["team_id"]), 0.0)
        cnt[i][j] += 1
    grid = [[0.0] * NY for _ in range(NX)]
    for i in range(NX):
        col_n = sum(cnt[i])
        col_mean = sum(tot[i]) / col_n if col_n else 0.0
        for j in range(NY):
            grid[i][j] = tot[i][j] / cnt[i][j] if cnt[i][j] >= MIN_CELL_N else col_mean
    return grid


def xt_grid(ds: Dataset) -> list[list[float]]:
    """The grid fitted on ds's baseline (the season for a single match), cached per dataset."""
    b = baseline_of(ds)
    if id(b) not in _GRIDS:
        _GRIDS[id(b)] = (b, fit_grid(b.events, b.shots))
    return _GRIDS[id(b)][1]


def value_at(grid, x: float, y: float) -> float:
    i, j = cell(x, y)
    return grid[i][j]


def xt_added(events, grid, team_id=None, player_id=None, window=None, state=None) -> MetricResult:
    """Total threat added by completed passes: sum of V(end) - V(start).

    Inputs: events; a grid from xt_grid/fit_grid; team_id and/or player_id; optional window, state.
    Value: xT added (can be negative). detail["per_pass"]: event_id -> xT added.
    Evidence: the passes, highest threat added first.
    Known limits: see module docstring.
    """
    per = {}
    for e in _completed_passes(events, team_id, window, state):
        if player_id is not None and e["player_id"] != player_id:
            continue
        per[e["event_id"]] = value_at(grid, e["x_end"], e["y_end"]) - value_at(grid, e["x_start"], e["y_start"])
    ids = sorted(per, key=lambda k: -per[k])
    return MetricResult(sum(per.values()), tuple(ids), len(per), detail=dict(per_pass=per))


def high_threat_cells(grid, quantile: float = 0.75) -> set:
    """Cells whose value is in the top quarter of the grid AND that lie across the box width
    (22 <= y <= 78, cell centre): 'high-threat central zones'."""
    vals = sorted(v for col in grid for v in col)
    cut = vals[int(quantile * (len(vals) - 1))]
    floor = vals[0]
    out = set()
    for i in range(NX):
        for j in range(NY):
            yc = (j + 0.5) * 100 / NY
            # cells tied at the grid's minimum never count, even when the cut falls on a tie
            if grid[i][j] >= cut and grid[i][j] > floor and BOX_Y[0] <= yc <= BOX_Y[1]:
                out.add((i, j))
    return out


def pass_quality_ratio(events, grid, player_id, baseline_events=None, team_id=None) -> MetricResult:
    """Share of a player's completed forward passes (x gain >= 8) that end in a high-threat
    central zone, divided by the same share for every player in the baseline.

    Inputs: events with the player's passes; grid; player_id; baseline_events (default: events);
    team_id optional (narrows the scan).
    Value: ratio (1.0 = league average; 0.2 = a fifth as often as the league). detail: player
    share, league share, counts. Evidence: the player's forward passes that DID reach those zones,
    then the ones that did not.
    Known limits: forward passes only; a role that rarely sees the final third scores low by
    design (compare players in similar roles); small samples for low-volume players.
    """
    hot = high_threat_cells(grid)

    def forward(evs, pid):
        for e in _completed_passes(evs, team_id if pid else None):
            if (pid is None or e["player_id"] == pid) and e["x_end"] - e["x_start"] >= 8:
                yield e

    mine = list(forward(events, player_id))
    good = [e for e in mine if cell(e["x_end"], e["y_end"]) in hot]
    lg = list(forward(baseline_events if baseline_events is not None else events, None))
    lg_good = sum(1 for e in lg if cell(e["x_end"], e["y_end"]) in hot)
    share = len(good) / len(mine) if mine else None
    lg_share = lg_good / len(lg) if lg else None
    ratio = share / lg_share if share is not None and lg_share else None
    bad = [e for e in mine if e not in good]
    return MetricResult(ratio, tuple(e["event_id"] for e in good + bad), len(mine),
                        detail=dict(player_share=share, league_share=lg_share,
                                    high_threat=len(good), forward=len(mine)))


def threat_passes(events, grid, min_added: float = 0.02):
    """Completed passes adding at least `min_added` xT, in order: (event, xT added)."""
    for e in _completed_passes(events, None):
        d = value_at(grid, e["x_end"], e["y_end"]) - value_at(grid, e["x_start"], e["y_start"])
        if d >= min_added:
            yield e, d
