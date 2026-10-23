"""Planted motifs (data_gen/motifs.py): the byte-identity proof (all propensities zero gives the
pre-patterns data, byte for byte) and season-level recovery by the pattern detectors."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from data_gen import motifs
from data_gen.config import MOTIFS, PLAYER_MOTIFS, TEAMS
from data_gen.generate import main as generate
from engine import patterns as P
from engine.tables import load

ROOT = Path(__file__).resolve().parent.parent
HASHES = json.loads((ROOT / "tests/data/pre_patterns_hashes.json").read_text())


def _hashes(d: Path) -> dict:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}


def test_zero_propensity_is_byte_identical_to_the_pre_patterns_generator(tmp_path):
    """Every table and ground_truth.json of the 2026 season and showcase, against hashes recorded
    from the generator before any motif code existed (seed 2027 and the full league: docs/patterns.md)."""
    generate(2026, tmp_path / "season", tmp_path / "showcase", motif_scale=0.0)
    assert _hashes(tmp_path / "season") == HASHES["2026/season"]
    assert _hashes(tmp_path / "showcase") == HASHES["2026/showcase"]


@pytest.mark.slow
def test_zero_propensity_is_byte_identical_for_a_second_seed(tmp_path):
    generate(2027, tmp_path / "season", tmp_path / "showcase", motif_scale=0.0)
    assert _hashes(tmp_path / "season") == HASHES["2027/season"]
    assert _hashes(tmp_path / "showcase") == HASHES["2027/showcase"]


def test_nothing_is_active_at_zero_and_scale_multiplies():
    assert motifs.active(TEAMS, 0.0) is None
    on = motifs.active(TEAMS, 0.5)
    aur = next(t for t in TEAMS if t.code == "AUR")
    assert on[aur.team_id] == {k: v * 0.5 for k, v in MOTIFS["AUR"].items()}
    assert any(isinstance(k, tuple) and k[0] == "player" for k in on)
    assert set(PLAYER_MOTIFS) and all(set(v) <= set(P.FAMILIES) for v in MOTIFS.values())


@pytest.fixture(scope="module")
def planted(tmp_path_factory):
    root = tmp_path_factory.mktemp("motifs")
    gt = generate(2026, root / "season", root / "showcase")
    return load(root / "season"), gt


def test_ground_truth_records_the_planted_motifs(planted):
    ds, gt = planted
    pm = gt["planted_motifs"]
    assert pm["scale"] == 1.0 and pm["teams"]["AUR"]["pat_bait_switch"] == 1.0
    assert len(pm["players"]) == 1 and next(iter(pm["players"].values()))["team"] == "VES"
    assert pm["instances"] and all("|" in k for rows in pm["instances"].values() for k in rows)


# share of planted team-matches (enough completed instances for the definition) the detector finds;
# the small season has 16 matches per team, so these are loose floors (the real measurement is
# tools/pattern_recall.py over five full leagues, docs/patterns.md)
FLOOR = {"pat_bait_switch": 0.8, "pat_cutback": 0.8, "pat_flank_isolation": 0.8, "pat_counter_press": 0.6}


def test_season_level_recovery_of_the_planted_teams(planted):
    ds, gt = planted
    code_id = {t["code"]: tid for tid, t in ds.teams.items()}
    inst = gt["planted_motifs"]["instances"]
    hit, case = Counter(), Counter()
    for mid, rows in inst.items():
        n = Counter()
        for k, v in rows.items():
            fam, code, _ = k.split("|")
            n[(fam, code_id[code])] += v
        for (fam, tid), v in n.items():
            if fam not in FLOOR:
                continue
            case[fam] += 1
            hit[fam] += any(f.family == fam for f in P.detect_team(ds, mid, tid, families=(fam,)))
    for fam, floor in FLOOR.items():
        assert case[fam] >= 3, fam
        assert hit[fam] / case[fam] >= floor, (fam, hit[fam], case[fam])
