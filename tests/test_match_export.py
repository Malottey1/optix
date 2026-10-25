"""Per-match recap files and the fixture index (agents/match_export.py), lineups and player
summaries in ui.json (agents/dashboard_data.py): zone-aligned heat bins, exact round trip of the
compact stream, the recap selection, size limits, schemas, determinism."""
import json
from collections import Counter
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agents import match_export as X
from agents.dashboard_data import TRACK_TYPES, _zone, lineups_section, starts_by_player
from agents.narrative import languages
from agents.stream import InsightStream
from engine import metrics as M
from engine.tables import load, match_events

ROOT = Path(__file__).resolve().parent.parent
SEASON = ROOT / "data" / "generated"
COMMITTED = ROOT / "web" / "public" / "data" / "matches"
FIRST = 3

pytestmark = pytest.mark.skipif(not (SEASON / "matches.csv").exists(), reason="needs data/generated")


@pytest.fixture(scope="module")
def season():
    return load(SEASON)


@pytest.fixture(scope="module")
def exports(tmp_path_factory):
    a, b = tmp_path_factory.mktemp("a"), tmp_path_factory.mktemp("b")
    X.export(SEASON, ROOT / "data" / "showcase", a, log=lambda *_: None, first=FIRST)
    X.export(SEASON, ROOT / "data" / "showcase", b, log=lambda *_: None, first=FIRST)
    return a, b


def test_grid_is_zone_aligned():
    assert (X.HEAT_COLS, X.HEAT_ROWS) == (24, 16)
    for x in X.HEAT_X_EDGES[:-1] + [33.29, 33.3, 66.69, 66.7, 99.99, 100.0]:
        for y in X.HEAT_Y_EDGES[:-1] + [19.99, 20.0, 39.99, 40.0, 59.99, 60.0, 79.99, 80.0, 100.0]:
            for dx in (0.0, 0.001):
                xx = min(100.0, x + dx)
                assert X.bin_zone(X.heat_bin(xx, y)) == _zone(xx, y), (xx, y)


def test_bins_reproduce_the_zone_counts_of_the_track_exactly(season):
    for mid in ("m_001", "m_002"):
        evs = match_events(season)[mid]
        tl_periods = X.timeline(season, mid)["periods"]
        heat = X.heat_section(season, mid, tl_periods)
        for code, halves in heat["teams"].items():
            for p, bins in zip(tl_periods, halves):
                track = [e for e in evs if e["event_type"] in TRACK_TYPES and season.code(e["team_id"]) == code
                         and p["start_sec"] <= e["clock_sec"] <= p["end_sec"]]
                assert sum(bins) == len(track)
                want = Counter(_zone(e["x_start"], e["y_start"]) for e in track)
                assert X.zone_counts(bins) == [want[z] for z in range(15)]


def test_compact_stream_round_trips_exactly(season):
    s = InsightStream(season, "m_001", languages=tuple(languages()))
    ins = s.run()
    for i in ins:
        i["clock"]["emitted_latency_ms"] = None
    claims = [X.claim_row("m_001", x) for x in s.attempts()]
    for i in ins:
        assert X.expand_insight("m_001", X.compact_insight("m_001", i), claims) == i


def test_two_exports_are_byte_identical_and_match_the_committed_files(exports):
    a, b = exports
    names = sorted(p.name for p in a.glob("m_*.json"))
    assert len(names) == FIRST + 1
    for n in names:
        assert (a / n).read_bytes() == (b / n).read_bytes(), n
        assert (a / n).read_bytes() == (COMMITTED / n).read_bytes(), f"{n}: rerun python -m agents.match_export"


def test_committed_files_fit_the_limits_and_the_schemas():
    match_v = Draft202012Validator(json.loads((ROOT / "contracts" / "match.schema.json").read_text()))
    index_v = Draft202012Validator(json.loads((ROOT / "contracts" / "fixtures.schema.json").read_text()))
    files = sorted(COMMITTED.glob("m_*.json"))
    total = 0
    for p in files:
        size = p.stat().st_size
        total += size
        assert size <= X.MAX_FILE_BYTES, p.name
        errs = [e.message for e in match_v.iter_errors(json.loads(p.read_text()))]
        assert not errs, (p.name, errs[:3])
    assert sum(p.stat().st_size for p in COMMITTED.glob("*.json")) <= X.MAX_DIR_BYTES
    for p in COMMITTED.glob("players-heat-*.json"):
        assert p.stat().st_size <= X.MAX_FILE_BYTES, p.name
    index = json.loads((COMMITTED / "index.json").read_text())
    assert not list(index_v.iter_errors(index))
    assert {f["id"] + ".json" for f in index["fixtures"]} == {p.name for p in files}


def test_index_lists_only_played_matches_with_the_showcase_first(season):
    index = json.loads((COMMITTED / "index.json").read_text())
    rows = index["fixtures"]
    assert rows[0]["id"] == X.SHOWCASE and rows[0]["status"] == "live"
    assert [r["status"] for r in rows[1:]] == ["final"] * len(season.matches)
    for r in rows[1:]:
        m = season.matches[r["id"]]
        assert r["score"] == [m["home_score"], m["away_score"]]
        assert (r["home"], r["away"]) == (season.code(m["home_team_id"]), season.code(m["away_team_id"]))


def test_recap_keeps_every_turning_point_and_every_attempt_of_a_kept_claim():
    for p in sorted(COMMITTED.glob("m_0*.json"))[:10]:
        f = json.loads(p.read_text())
        ids = {i["id"] for i in f["insights"]}
        assert {t["insight_id"] for t in f["turning_points"] if "insight_id" in t} <= ids
        by_claim = {c["claim_id"]: c for c in f["claims"]}
        for i in f["insights"]:
            c = by_claim[i["claim"]]
            while "revision_of" in c:
                c = by_claim[c["revision_of"]]
        types = Counter(i["type"] for i in f["insights"] if i["type"] not in X.UNCAPPED)
        assert max(types.values()) <= X.TYPE_CAP
        assert sum(f["stream_counts"]["types"].values()) == f["stream_counts"]["insights"] >= len(f["insights"])
        # the matchup block exists exactly when a verified lane claim was published
        lane = [i for i in f["insights"] if i["type"] == "matchup_mismatch"]
        assert bool(lane) == ("matchups" in f)


def test_header_numbers_come_from_the_events(season):
    f = json.loads((COMMITTED / "m_001.json").read_text())
    evs = match_events(season)["m_001"]
    m = season.matches["m_001"]
    for side, tid in (("home", m["home_team_id"]), ("away", m["away_team_id"])):
        r = M.xg_sum(evs, season.shots, tid)
        assert f["header"][side]["xg"] == round(r.value, 2) and f["header"][side]["shots"] == r.sample_size
    assert [f["header"]["home"]["goals"], f["header"]["away"]["goals"]] == [m["home_score"], m["away_score"]]


def test_goals_and_assists_add_up_to_the_scores(season):
    goals = sum(M.goals(season.events, season.shots, pid).value for pid in season.players)
    assists = sum(M.assists(season.events, season.shots, pid).value for pid in season.players)
    assert goals == sum(m["home_score"] + m["away_score"] for m in season.matches.values())
    assert 0 < assists <= goals


def test_lineup_is_the_most_started_eleven_with_listed_numbers_and_label(season):
    starts = starts_by_player(SEASON)
    lu = lineups_section(season, SEASON)
    assert set(lu) == {t["code"] for t in season.teams.values()}
    for code, t in lu.items():
        tid = season.team_by_code(code)
        squad = sorted((p for p, r in season.players.items() if r["team_id"] == tid),
                       key=lambda p: (-starts.get(p, 0), p))
        assert {r["id"] for r in t["xi"]} == set(squad[:11])
        assert len({r["shirt"] for r in t["xi"]}) == 11
        assert all(r["shirt"] == int(season.players[r["id"]]["shirt"]) for r in t["xi"])
        count = Counter(r["position"] for r in t["xi"])
        assert count["GK"] == 1 and t["label"] == f"{count['DF']}-{count['MF']}-{count['FW']}"
        slots = {(r["line"], r["slot"]) for r in t["xi"]}
        assert len(slots) == 11                                     # one node per slot: nothing overlaps
    assert lu["HAR"]["label"] == "4-4-2" and lu["AUR"]["label"] == "4-3-3"


def test_player_touch_maps_count_every_on_ball_event(season):
    from agents.dashboard_data import TRACK_TYPES as TT
    for tid in sorted(season.teams)[:2]:
        f = json.loads((COMMITTED / f"players-heat-{season.code(tid).lower()}.json").read_text())
        for pid, (bins,) in list(f["players"].items())[:5]:
            n = sum(1 for e in season.events if e["player_id"] == pid and e["event_type"] in TT and e["x_start"] is not None)
            assert sum(bins) == n
