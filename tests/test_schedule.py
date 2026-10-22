"""Fixture structure and calendar for both leagues (data_gen/schedule.py)."""
import random
from collections import Counter, defaultdict
from datetime import date, timedelta

import pytest

from data_gen.config import TEAMS
from data_gen.generate import fixtures_for
from data_gen.league import full_teams
from data_gen.schedule import MAX_RUN, max_run, season_rounds

SMALL = [t.team_id for t in TEAMS]
FULL = [t.team_id for t in full_teams()]


def _runs(fixtures, team):
    seq = [("H" if f["home"] == team else "A") for f in sorted(fixtures, key=lambda f: f["matchweek"])
           if team in (f["home"], f["away"])]
    best = cur = 1
    for a, b in zip(seq, seq[1:]):
        cur = cur + 1 if a == b else 1
        best = max(best, cur)
    return best


@pytest.mark.parametrize("ids,cycles,n_matches,per_team,weeks", [(FULL, 1, 380, 38, 38), (SMALL, 2, 40, 16, 20)])
def test_round_robin_structure(ids, cycles, n_matches, per_team, weeks):
    fx = fixtures_for(ids, 2026, cycles)
    assert len(fx) == n_matches
    assert len({f["matchweek"] for f in fx}) == weeks
    per_week = Counter((f["matchweek"], t) for f in fx for t in (f["home"], f["away"]))
    assert set(per_week.values()) == {1}                       # at most once per matchweek
    if len(ids) % 2 == 0:
        assert len(per_week) == weeks * len(ids)                # even league: every team every week
    else:
        byes = Counter(t for w in range(1, weeks + 1) for t in ids if (w, t) not in per_week)
        assert set(byes.values()) == {weeks // len(ids)}        # odd league: byes spread evenly
    games = Counter(t for f in fx for t in (f["home"], f["away"]))
    assert set(games.values()) == {per_team}
    home = Counter(f["home"] for f in fx)
    assert set(home.values()) == {per_team // 2}
    ordered = Counter((f["home"], f["away"]) for f in fx)
    assert set(ordered.values()) == {cycles} and len(ordered) == len(ids) * (len(ids) - 1)
    for t in ids:
        assert _runs(fx, t) <= MAX_RUN, t


def test_each_double_round_meets_every_pair_once_each_way():
    rounds = season_rounds(SMALL, random.Random(1), cycles=2)
    half = len(rounds) // 2
    for block in (rounds[:half], rounds[half:]):
        ordered = Counter(p for rnd in block for p in rnd)
        assert set(ordered.values()) == {1} and len(ordered) == 20


def test_calendar_one_window_per_matchweek_and_a_real_season():
    fx = fixtures_for(FULL, 2026)
    by_week = defaultdict(list)
    for f in fx:
        by_week[f["matchweek"]].append(date.fromisoformat(f["date"]))
    prev_end = None
    midweek = 0
    for wk in sorted(by_week):
        ds = by_week[wk]
        assert max(ds) - min(ds) <= timedelta(days=3), wk          # one weekend (Fri-Mon) or midweek slot
        days = {d.strftime("%a") for d in ds}
        assert days <= {"Fri", "Sat", "Sun", "Mon"} or days <= {"Tue", "Wed"}, (wk, days)
        midweek += days <= {"Tue", "Wed"}
        if prev_end:
            assert min(ds) > prev_end, wk                         # matchweeks never overlap
        prev_end = max(ds)
    assert 1 <= midweek <= 4
    first, last = min(min(v) for v in by_week.values()), max(max(v) for v in by_week.values())
    assert first.month == 8 and last.month == 5 and last.day >= 15
    kick = Counter(f["kickoff"] for f in fx)
    assert kick.most_common(1)[0][0] == "15:00" and len(kick) >= 5


def test_schedule_is_deterministic():
    assert fixtures_for(FULL, 2026) == fixtures_for(FULL, 2026)
    assert fixtures_for(FULL, 2026) != fixtures_for(FULL, 2027)
