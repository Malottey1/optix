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
    # soft lanes (attacker point of view), strength scales the weak-lane bonus (1.0 = NTG's plant)
    "OKP": dict(weak_lane="right_flank", weak_strength=2.5),
    "HBC": dict(weak_lane="left_flank", weak_strength=2.0),
    "MDL": dict(weak_lane="right_half_space", weak_strength=1.5),
    "FWM": dict(weak_lane="center", weak_strength=1.0),
    "RVD": dict(weak_lane="left_half_space", weak_strength=0.6),
    "IRK": dict(weak_lane="right_flank", weak_strength=0.3),
}

# Player plants, keyed like config.PLAYER_TRAITS.
_VOLUME = dict(usage=1.4, cross_mult=0.15, wide_forward=True, trap_flag="volume_passer")
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


# Formations per archetype (the first is used unless the team carries a winger plant).
FORMATION_BY_ARCHETYPE = {
    "high_press": ("4-3-3", "4-2-3-1"),
    "low_block_counter": ("4-4-2", "4-1-4-1", "3-5-2"),
    "possession": ("4-3-3", "4-2-3-1"),
    "direct": ("4-4-2", "3-5-2"),
    "wing_play": ("4-2-3-1", "4-3-3"),
    "balanced": ("4-2-3-1", "4-4-2", "4-1-4-1"),
}
WINGER_FORMATIONS = ("4-3-3", "4-2-3-1")

# Team quality: a hidden strength draw that shifts the correlated dials, as in a real league where
# the strongest clubs also keep the ball and press more. A few teams defy their strength (the
# style does not follow the quality), so the correlations are not perfect.
QUALITY = {"ASV": 1.8, "DCH": -1.0, "ESF": 2.0, "FWM": -1.1, "GRM": 0.2, "HBC": -0.3, "IRK": 0.8,
           "JPH": -1.2, "KWC": 0.9, "LMF": -0.9, "MDL": -0.2, "OKP": -0.6, "PLQ": -1.2, "QNT": 0.4,
           "RVD": 0.1}
DEFY_STRENGTH = {"PLQ", "LMF"}     # a weak side that presses hard; a strong-ish one would be direct


def _vary(rng: random.Random, base: tuple, q: float = 0.0, defy: bool = False) -> dict:
    """One team's dials: the archetype values, seeded noise, and the quality shift. Every dial is
    bounded to a plausible range."""
    style, lanes, att, dfn, press, tempo, direct, deep, ao, counter, spam = base
    w = [l * rng.lognormvariate(0, 0.15) for l in lanes]
    total = sum(w)
    clip = lambda v, lo, hi: max(lo, min(hi, v))
    sq = -q if defy else q           # style follows quality, unless the team defies it
    return dict(
        style_seed=style,
        lane_weights=tuple(round(x / total, 3) for x in w),
        att=round(clip(att + 0.06 * q + rng.uniform(-0.02, 0.02), 0.85, 1.15), 3),
        dfn=round(clip(dfn + 0.06 * q + rng.uniform(-0.02, 0.02), 0.85, 1.15), 3),
        press=round(clip(press + 0.06 * sq + rng.uniform(-0.06, 0.06), 0.1, 0.95), 3),
        tempo=round(clip(tempo * rng.uniform(0.92, 1.08), 3.2, 6.5), 2),
        directness=round(clip(direct - 0.05 * sq + rng.uniform(-0.04, 0.04), 0.2, 0.9), 3),
        sit_deep=round(clip(deep - 0.05 * q + rng.uniform(-0.08, 0.08), 0.05, 0.95), 3),
        attacking_output=round(clip(ao * (1 + 0.12 * q) * rng.uniform(0.95, 1.05), 0.6, 1.8), 3),
        counter=round(clip(counter + rng.uniform(-0.08, 0.08), 0.05, 0.9), 3),
        shot_spam=round(clip(spam + rng.uniform(-0.05, 0.05), 0.0, 1.0), 3),
    )


def extra_teams() -> list[TeamSpec]:
    rng = random.Random(FULL_LEAGUE_TEAM_SEED)
    winger_plants = {code for code, role in EXTRA_PLAYER_TRAITS if role.endswith("winger")}
    out = []
    for code, name, arch in EXTRA_TEAMS:
        kw = _vary(rng, ARCHETYPES[arch], QUALITY[code], code in DEFY_STRENGTH)
        kw.update(TEAM_TRAPS.get(code, {}))
        forms = FORMATION_BY_ARCHETYPE[arch]
        if code in winger_plants:
            forms = [f for f in forms if f in WINGER_FORMATIONS] or list(WINGER_FORMATIONS)
        formation = forms[rng.randrange(len(forms))]
        out.append(TeamSpec(team_id=f"t_{code.lower()}", code=code, name=name, weak_lane=kw.pop("weak_lane", None),
                            archetype=arch, formation=formation, **kw))
    return out


def full_teams() -> list[TeamSpec]:
    """The five original teams exactly as they are, then the 15 generated ones."""
    originals = {"AUR": "low_block_counter", "NTG": "possession", "CAL": "high_press",
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
