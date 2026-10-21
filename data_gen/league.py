"""The full 20-team league: the five original teams unchanged plus 15 generated ones.

The 15 extra teams are drawn from six archetypes with seeded random variation, then a handful of
traps are planted on top (volume passers, corner specialists, shot-spam teams, teams that sit deep
when leading, soft lanes of varying strength). Everything is fictional: invented place names and
3-letter codes that do not match any real club.

Team identities are fixed by FULL_LEAGUE_TEAM_SEED (independent of the match seed), so the same
20 teams appear whatever --seed is used for the matches.
"""
from __future__ import annotations

import random
from dataclasses import replace

from .config import TEAMS, TeamSpec

FULL_LEAGUE_TEAM_SEED = 1906

# archetype -> (style_seed text, lane_weights, att, dfn, press, tempo, directness, sit_deep,
#               attacking_output, counter, shot_spam)
ARCHETYPES = {
    "high_press": ("high press, wins the ball high",
                   (0.12, 0.20, 0.36, 0.20, 0.12), 1.01, 1.00, 0.80, 4.4, 0.55, 0.30, 0.95, 0.50, 0.0),
    "low_block_counter": ("low block, counters fast",
                          (0.22, 0.18, 0.20, 0.18, 0.22), 1.00, 1.01, 0.30, 4.2, 0.62, 0.70, 1.00, 0.60, 0.0),
    "possession": ("patient possession build-up",
                   (0.15, 0.22, 0.26, 0.22, 0.15), 1.03, 0.98, 0.45, 5.8, 0.38, 0.25, 1.30, 0.15, 0.2),
    "direct": ("direct long ball",
               (0.20, 0.20, 0.20, 0.20, 0.20), 0.98, 0.98, 0.45, 3.8, 0.78, 0.45, 0.90, 0.45, 0.4),
    "wing_play": ("wing play down both flanks",
                  (0.30, 0.15, 0.10, 0.15, 0.30), 1.02, 1.00, 0.50, 5.0, 0.50, 0.40, 1.20, 0.30, 0.0),
    "balanced": ("balanced, no strong lean",
                 (0.20, 0.20, 0.20, 0.20, 0.20), 1.00, 1.00, 0.50, 4.8, 0.50, 0.40, 1.05, 0.35, 0.1),
}

# code, name, archetype
EXTRA_TEAMS = [
    ("ASV", "Ashmere Vale", "high_press"),
    ("DCH", "Duncliff Harriers", "low_block_counter"),
    ("ESF", "Esterby Forge", "possession"),
    ("FWM", "Fallowmoor Lanterns", "direct"),
    ("GRM", "Glenrock Mariners", "wing_play"),
    ("HBC", "Hollin Bay Corsairs", "balanced"),
    ("IRK", "Ironsend Kites", "high_press"),
    ("JPH", "Juniper Port Herons", "low_block_counter"),
    ("KWC", "Kestwick Comets", "possession"),
    ("LMF", "Lowmarsh Ferrymen", "direct"),
    ("MDL", "Merrowdale Larks", "wing_play"),
    ("OKP", "Oakhurst Pilots", "balanced"),
    ("PLQ", "Pellinor Quarrymen", "high_press"),
    ("QNT", "Quenby Tides", "possession"),
    ("RVD", "Ravensholt Drovers", "balanced"),
]

# Team-level plants on top of the archetype draw. Each entry says what the data should show.
TEAM_TRAPS = {
    # shot spam: shoots from range when the opponent sits deep
    "ESF": dict(shot_spam=0.8),
    "LMF": dict(shot_spam=0.85),
    # sits deep when leading
    "DCH": dict(sit_deep=0.88),
    "JPH": dict(sit_deep=0.90),
    # soft lanes (attacker point of view), strength scales the weak-lane bonus (1.0 = NOR's plant)
    "OKP": dict(weak_lane="right_flank", weak_strength=2.5),
    "HBC": dict(weak_lane="left_flank", weak_strength=2.0),
    "MDL": dict(weak_lane="right_half_space", weak_strength=1.5),
    "FWM": dict(weak_lane="center", weak_strength=1.0),
    "RVD": dict(weak_lane="left_half_space", weak_strength=0.6),
    "IRK": dict(weak_lane="right_flank", weak_strength=0.3),
}

# Player plants, keyed like config.PLAYER_TRAITS.
_VOLUME = dict(usage=2.3, cross_mult=0.15, wide_forward=True, trap_flag="volume_passer")
_CORNER = dict(usage=0.4, cross_mult=0.5, set_piece_taker=True, trap_flag="corner_specialist")
EXTRA_PLAYER_TRAITS = {
    ("GRM", "right_winger"): _VOLUME,
    ("QNT", "left_winger"): _VOLUME,
    ("KWC", "right_winger"): _VOLUME,
    ("ESF", "left_winger"): _CORNER,
    ("MDL", "right_winger"): _CORNER,
    ("ASV", "left_winger"): _CORNER,
}

# What each plant should leave in the event data (recorded in the full league's ground truth).
EXPECTED_EVIDENCE = {
    "volume_passer": "his team's top forward passer and in the league's top 10%; >= 80% of his completed "
                     "forward passes end on a flank",
    "corner_specialist": "most of his key passes come from corners",
    "shot_spam": "while trailing (opponent sitting deep), a higher share of low-xG (<= 0.08) shots than "
                 "the league's trailing share",
    "sit_deep_when_leading": "field tilt falls more when leading (vs level) than the league's does",
    "soft_lane": "opponents complete more final-third entries into this lane (attacker POV) than the league does; "
                 "the effect grows with weak_strength",
}


def _vary(rng: random.Random, base: tuple) -> dict:
    style, lanes, att, dfn, press, tempo, direct, deep, ao, counter, spam = base
    w = [l * rng.lognormvariate(0, 0.15) for l in lanes]
    total = sum(w)
    clip = lambda v, lo, hi: max(lo, min(hi, v))
    return dict(
        style_seed=style,
        lane_weights=tuple(round(x / total, 3) for x in w),
        att=round(att + rng.uniform(-0.03, 0.03), 3),
        dfn=round(dfn + rng.uniform(-0.03, 0.03), 3),
        press=round(clip(press + rng.uniform(-0.08, 0.08), 0.1, 0.95), 3),
        tempo=round(tempo * rng.uniform(0.92, 1.08), 2),
        directness=round(clip(direct + rng.uniform(-0.05, 0.05), 0.2, 0.9), 3),
        sit_deep=round(clip(deep + rng.uniform(-0.08, 0.08), 0.05, 0.95), 3),
        attacking_output=round(ao * rng.uniform(0.92, 1.08), 3),
        counter=round(clip(counter + rng.uniform(-0.08, 0.08), 0.05, 0.9), 3),
        shot_spam=round(clip(spam + rng.uniform(-0.05, 0.05), 0.0, 1.0), 3),
    )


def extra_teams() -> list[TeamSpec]:
    rng = random.Random(FULL_LEAGUE_TEAM_SEED)
    out = []
    for code, name, arch in EXTRA_TEAMS:
        kw = _vary(rng, ARCHETYPES[arch])
        kw.update(TEAM_TRAPS.get(code, {}))
        # lane_weights may need renormalising after rounding; keep as drawn (sum ~1)
        out.append(TeamSpec(team_id=f"t_{code.lower()}", code=code, name=name, weak_lane=kw.pop("weak_lane", None),
                            archetype=arch, **kw))
    return out


def full_teams() -> list[TeamSpec]:
    """The five original teams exactly as they are, then the 15 generated ones."""
    originals = {"AUR": "low_block_counter", "NOR": "possession", "CAL": "high_press",
                 "VES": "wing_play", "HAR": "direct"}
    return [replace(t, archetype=originals[t.code]) for t in TEAMS] + extra_teams()


def team_traps(teams: list[TeamSpec]) -> dict:
    """Team-level plants as recorded in ground truth: code -> list of trap dicts."""
    out = {}
    for t in teams:
        traps = []
        if t.shot_spam >= 0.6:
            traps.append(dict(trap="shot_spam", shot_spam=t.shot_spam))
        if t.sit_deep >= 0.8:
            traps.append(dict(trap="sit_deep_when_leading", sit_deep=t.sit_deep))
        if t.weak_lane:
            traps.append(dict(trap="soft_lane", weak_lane_attacker_pov=t.weak_lane, weak_strength=t.weak_strength))
        if traps:
            out[t.code] = traps
    return out


def round_robin(team_ids: list[str], rng: random.Random) -> list[tuple[int, str, str]]:
    """Double round robin by the circle method: (matchweek, home, away), every team plays once per
    week, home and away swap in the second half of the season."""
    ids = list(team_ids)
    rng.shuffle(ids)
    n = len(ids)
    first = []
    for week in range(n - 1):
        for i in range(n // 2):
            a, b = ids[i], ids[n - 1 - i]
            first.append((week + 1, a, b) if (week + i) % 2 == 0 else (week + 1, b, a))
        ids = [ids[0]] + [ids[-1]] + ids[1:-1]
    second = [(w + n - 1, away, home) for w, home, away in first]
    return first + second
