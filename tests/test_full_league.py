"""The full 20-team league (slow). Generated fresh into a temp dir.

Checks totals, calibration, that the five original teams are unchanged, and that every planted
style and trap is visible in that team's (or player's) own aggregates. Ground truth is read here
only; the measurements use engine/ metrics, which never see it.
"""
import json
from collections import Counter

import pytest

from data_gen.calibration import check, season_stats
from data_gen.config import TEAMS
from data_gen.generate import main_full
from data_gen.league import EXTRA_TEAMS
from engine import metrics as M
from engine.profiles import bracket_shift, team_style_profile
from engine.tables import load, score_diff, team_events

pytestmark = pytest.mark.slow

ARCHETYPE_SIGNAL = {"high_press": "press_intensity", "low_block_counter": "counter_share",
                    "possession": "passes_per_sequence", "direct": "directness"}
REAL_CLUB_WORDS = ("Arsenal", "Chelsea", "Liverpool", "Manchester", "Tottenham", "Everton", "Newcastle",
                   "Villa", "Brighton", "Wolves", "Fulham", "Brentford", "Palace", "Forest", "Bournemouth",
                   "West Ham", "Leicester", "Leeds", "Southampton", "Burnley", "Premier League")


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    out = tmp_path_factory.mktemp("full")
    gt = main_full(2026, out)
    return load(out), gt, out


def test_totals(full):
    ds, gt, _ = full
    assert len(ds.teams) == 20 and len(ds.matches) == 380
    per_team = Counter()
    weeks = Counter()
    for m in ds.matches.values():
        per_team[m["home_team_id"]] += 1
        per_team[m["away_team_id"]] += 1
        weeks[(m["matchweek"], m["home_team_id"])] += 1
        weeks[(m["matchweek"], m["away_team_id"])] += 1
    assert set(per_team.values()) == {38}
    assert set(weeks.values()) == {1}                  # one match per team per matchweek
    pairs = Counter((m["home_team_id"], m["away_team_id"]) for m in ds.matches.values())
    assert set(pairs.values()) == {1} and len(pairs) == 380    # every ordered pair once
    assert 550_000 <= len(ds.events) <= 800_000
    assert gt["n_events"] == len(ds.events)


def test_full_league_meets_calibration(full):
    ds, gt, _ = full
    st = season_stats(list(ds.matches.values()), list(ds.shots.values()), list(ds.passes.values()))
    failed = {k: r for k, r in check(st).items() if not r["passed"]}
    assert not failed, failed


def test_original_five_unchanged_and_names_fictional(full):
    ds, gt, out = full
    for t in TEAMS:
        g = gt["teams"][t.code]
        assert tuple(g["lane_weights"]) == t.lane_weights and g["weak_lane_attacker_pov"] == t.weak_lane
        assert g["sit_deep"] == t.sit_deep and g["press"] == t.press
    codes = [c for c, _, _ in EXTRA_TEAMS]
    assert len(set(codes) | {t.code for t in TEAMS}) == 20
    text = (out / "teams.csv").read_text()
    for word in REAL_CLUB_WORDS:
        assert word not in text


def test_archetype_styles_visible(full):
    ds, gt, _ = full
    for code, t in gt["teams"].items():
        p = team_style_profile(ds, t["team_id"])
        if t["archetype"] in ARCHETYPE_SIGNAL:
            m = p["metrics"][ARCHETYPE_SIGNAL[t["archetype"]]]
            assert m["value"] > m["league"], (code, t["archetype"], m)
        elif t["archetype"] == "wing_play":
            l = p["lanes"]["entry_lanes"]
            wide = l["left_flank"]["share"] + l["right_flank"]["share"]
            assert wide > l["left_flank"]["league"] + l["right_flank"]["league"], code


def test_player_traps_visible(full):
    ds, gt, _ = full
    ranked = [p for p, _ in M.forward_passes_by_player(ds.events).value]
    n_vp = n_cs = 0
    for pid, v in gt["planted_players"].items():
        ev = team_events(ds, v["team"])
        if v["trap"] == "volume_passer":
            n_vp += 1
            team_rank = [p for p in ranked if ds.players[p]["team_id"] == v["team"]].index(pid) + 1
            assert team_rank == 1, pid
            assert ranked.index(pid) + 1 <= 0.10 * len(ranked), pid
            assert M.forward_passes_wide_share(ev, v["team"], pid).detail["wide_share"] >= 0.8, pid
        elif v["trap"] == "corner_specialist":
            n_cs += 1
            c = M.chances_created(ev, ds.passes, v["team"], pid)
            assert c.detail["set_piece"] > c.detail["open_play"], pid
    assert n_vp >= 4 and n_cs >= 4                    # NOR's plus at least 3 new of each


def test_team_traps_visible(full):
    ds, gt, _ = full
    by_id = {e["event_id"]: e for e in ds.events}
    tot, low = Counter(), Counter()
    for eid, s in ds.shots.items():
        e = by_id[eid]
        if score_diff(e, e["team_id"]) < 0:
            tot[e["team_id"]] += 1
            low[e["team_id"]] += s["xg"] <= 0.08
    league_trailing_low = sum(low.values()) / sum(tot.values())
    kinds = Counter()
    for code, traps in gt["team_traps"].items():
        tid = gt["teams"][code]["team_id"]
        for tr in traps:
            kinds[tr["trap"]] += 1
            if tr["trap"] == "shot_spam":
                assert low[tid] / tot[tid] > league_trailing_low, code
            elif tr["trap"] == "sit_deep_when_leading":
                s = bracket_shift(ds, tid)["field_tilt"]
                assert s["delta"] < s["league_delta"], code
    assert kinds["shot_spam"] >= 3 and kinds["sit_deep_when_leading"] >= 3 and kinds["soft_lane"] >= 5


# Stated recoverable size: a planted soft lane whose TRUE effect (lower bound, from the generator's
# own success probabilities) is at least this many percentage points must be recovered.
RECOVERABLE_EFFECT_PP = 5.0


def test_soft_lanes_recovered_above_stated_size(full):
    from soft_lane_truth import true_soft_lane_effect
    from engine.profiles import soft_lane
    ds, gt, _ = full
    should, found, false_pos, unplanted = [], [], [], []
    for code, t in gt["teams"].items():
        got = soft_lane(ds, t["team_id"])
        if t["weak_lane_attacker_pov"] is None:
            unplanted.append(code)
            if got is not None:
                false_pos.append(code)
            continue
        eff = true_soft_lane_effect(ds, t["team_id"], t["weak_lane_attacker_pov"], t["weak_strength"])
        if eff["effect_pp_low"] >= RECOVERABLE_EFFECT_PP:
            should.append(code)
            if got is not None and got["lane"] == t["weak_lane_attacker_pov"]:
                found.append(code)
    recovery = len(found) / len(should)
    print(f"soft lanes: {len(found)}/{len(should)} recovered (true effect >= {RECOVERABLE_EFFECT_PP} pp), "
          f"false positives {len(false_pos)}/{len(unplanted)}")
    assert len(should) >= 6
    assert recovery == 1.0, (should, found)
    assert len(false_pos) <= 0.10 * len(unplanted), false_pos


def test_profile_and_matchup_run_on_full_league(full):
    from engine.matchup import lane_matchup, matchup_claim
    ds, gt, _ = full
    codes = list(gt["teams"])
    for a, d in zip(codes, codes[1:] + codes[:1]):
        m = lane_matchup(ds, gt["teams"][a]["team_id"], gt["teams"][d]["team_id"])
        assert m["n_attack"] > 0 and m["n_concede"] > 0
    claim = matchup_claim(ds, gt["teams"]["AUR"]["team_id"], gt["teams"]["NOR"]["team_id"])
    assert claim["zone"]["lane"] == "left_flank"
