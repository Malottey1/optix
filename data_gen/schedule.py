"""Fixtures and calendar.

`double_round_robin`: the circle method. Every team plays once per matchweek (a bye when the number
of teams is odd), every pair meets twice, once at each ground, the second half of the season
mirrors the first with venues swapped, and venues alternate so that no team has more than two home
or two away matches in a row (byes do not break a run).

`calendar`: one date window per matchweek: a weekend (Friday to Monday, most matches on Saturday at
15:00) or, for a few rounds, a midweek (Tuesday/Wednesday evening); no round on international-break
weekends; the season runs from mid-August to late May.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

MAX_RUN = 2


def _circle_rounds(ids: list) -> list[list[tuple]]:
    """Single round robin, circle method; None marks a bye. Venue alternates by round for the fixed
    team and by round + slot for the others (Berger tables)."""
    ids = list(ids) + ([None] if len(ids) % 2 else [])
    n = len(ids)
    fixed, rest = ids[-1], ids[:-1]
    rounds = []
    for r in range(n - 1):
        pairs = []
        a = rest[r % (n - 1)]
        pairs.append((fixed, a) if r % 2 else (a, fixed))
        for k in range(1, n // 2):
            h, w = rest[(r + k) % (n - 1)], rest[(r - k) % (n - 1)]
            pairs.append((h, w) if k % 2 else (w, h))
        rounds.append([p for p in pairs if None not in p])
    return rounds


def max_run(rounds: list[list[tuple]], team) -> int:
    """Longest run of consecutive home (or away) matches for `team` (byes skipped)."""
    seq = [("H" if h == team else "A") for rnd in rounds for h, a in rnd if team in (h, a)]
    best = cur = 1 if seq else 0
    for x, y in zip(seq, seq[1:]):
        cur = cur + 1 if x == y else 1
        best = max(best, cur)
    return best


def double_round_robin(team_ids: list, rng: random.Random) -> list[list[tuple]]:
    """Rounds of (home, away) pairs: the first half, then the second half with venues swapped. Team
    order is shuffled with `rng`. An exact mirror gives some teams three in a row at the turn of the
    season, so the second half's round order is rotated (the smallest rotation, else reversed) until
    no team has a same-venue run longer than MAX_RUN."""
    ids = list(team_ids)
    rng.shuffle(ids)
    first = _circle_rounds(ids)
    mirror = [[(a, h) for h, a in rnd] for rnd in first]
    for rev in (False, True):
        for k in range(len(first)):
            second = mirror[k:] + mirror[:k]
            rounds = first + (second[::-1] if rev else second)
            if all(max_run(rounds, t) <= MAX_RUN for t in team_ids):
                return rounds
    raise RuntimeError("no schedule without long same-venue runs")


def season_rounds(team_ids: list, rng: random.Random, cycles: int = 1, max_tries: int = 500) -> list[list[tuple]]:
    """`cycles` double round robins back to back (the 5-team league plays two). Later cycles are
    redrawn until the whole season keeps every same-venue run within MAX_RUN."""
    rounds = double_round_robin(team_ids, rng)
    for _ in range(cycles - 1):
        for _ in range(max_tries):
            cand = rounds + double_round_robin(team_ids, rng)
            if all(max_run(cand, t) <= MAX_RUN for t in team_ids):
                rounds = cand
                break
        else:
            raise RuntimeError("no multi-cycle schedule without long same-venue runs")
    return rounds


# Weekend kick-off slots (day offset from Saturday, time) and how often each is used.
WEEKEND_SLOTS = [(-1, "20:00", 0.05), (0, "12:30", 0.10), (0, "15:00", 0.45), (0, "17:30", 0.12),
                 (1, "14:00", 0.13), (1, "16:30", 0.10), (2, "20:00", 0.05)]
MIDWEEK_SLOTS = [(0, "19:30", 0.45), (0, "20:00", 0.15), (1, "19:30", 0.25), (1, "20:00", 0.15)]
# Saturdays (offset in weeks from the opening Saturday) with no league round: international breaks
# (September, October, November, March) and a cup weekend in January.
INTERNATIONAL_BREAKS = (3, 8, 13, 21, 32)
# Rounds played midweek (Tuesday), inserted after these weekend rounds (counted from 1): the
# December/January programme.
MIDWEEK_AFTER = (16, 19)


def round_windows(n_rounds: int, start: date = date(2026, 8, 15)) -> list[tuple[date, str]]:
    """(anchor date, kind) per round: kind 'weekend' (anchor = Saturday) or 'midweek' (Tuesday).
    Rounds that do not fit the standard pattern (short seasons) are all weekends."""
    out, week = [], 0
    weekend_done = 0
    while len(out) < n_rounds:
        if week in INTERNATIONAL_BREAKS and n_rounds > 20:
            week += 1
            continue
        sat = start + timedelta(weeks=week)
        out.append((sat, "weekend"))
        weekend_done += 1
        if weekend_done in MIDWEEK_AFTER and n_rounds > 20 and len(out) < n_rounds:
            out.append((sat + timedelta(days=3), "midweek"))
        week += 1
    return out


def calendar(rounds: list[list[tuple]], rng: random.Random, start: date = date(2026, 8, 15)) -> list[dict]:
    """One fixture dict per match: matchweek, date, kickoff, home, away (rounds in order)."""
    out = []
    for wk, ((anchor, kind), rnd) in enumerate(zip(round_windows(len(rounds), start), rounds), start=1):
        slots = WEEKEND_SLOTS if kind == "weekend" else MIDWEEK_SLOTS
        for h, a in rnd:
            off, ko, _ = rng.choices(slots, [s[2] for s in slots])[0]
            out.append(dict(matchweek=wk, date=(anchor + timedelta(days=off)).isoformat(), kickoff=ko,
                            home=h, away=a))
    return out
