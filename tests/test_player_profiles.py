"""Player profiles (agents/player_profiles.py) in ui.json players[].profile, the per-team lists in
web/public/data/matches/players-<code>.json and the per-match lineups: every aggregate recomputed
here from the raw CSV rows with the csv module only (no engine code), plus schemas, sizes and
determinism."""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agents import player_profiles as PP

ROOT = Path(__file__).resolve().parent.parent
SEASON = ROOT / "data" / "generated"
DATA = ROOT / "web" / "public" / "data"
UI_MAX_BYTES = 1_300_000

pytestmark = pytest.mark.skipif(not (SEASON / "matches.csv").exists(), reason="needs data/generated")


def _csv(name, d=SEASON):
    with (d / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def raw():
    ev = _csv("events.csv")
    for e in ev:
        for k in ("x_start", "y_start", "x_end", "y_end"):
            e[k] = float(e[k]) if e[k] else None
        e["clock_sec"] = int(e["clock_sec"])
    return dict(ev=ev, passes={r["event_id"]: r for r in _csv("passes.csv")},
                shots={r["event_id"]: r for r in _csv("shots.csv")}, lineups=_csv("lineups.csv"),
                players={r["player_id"]: r for r in _csv("players.csv")}, matches=_csv("matches.csv"))


@pytest.fixture(scope="module")
def ui():
    return json.loads((DATA / "ui.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prof(ui):
    return {p["id"]: p["profile"] for p in ui["players"] if "profile" in p}


def _r(v, dp):
    return round(v, dp)


def test_ui_json_and_team_files_fit_their_limits_and_schema():
    assert (DATA / "ui.json").stat().st_size <= UI_MAX_BYTES
    v = Draft202012Validator(json.loads((ROOT / "contracts" / "players.schema.json").read_text()))
    files = sorted((DATA / "matches").glob("players-[a-z][a-z][a-z].json"))
    assert len(files) == 5
    for p in files:
        assert p.stat().st_size <= 80_000, p.name
        assert not [e.message for e in v.iter_errors(json.loads(p.read_text()))], p.name


def test_minutes_starts_and_substitute_minutes(raw, prof):
    mins, starts, subs, sub_min = Counter(), Counter(), Counter(), Counter()
    for r in raw["lineups"]:
        m = float(r["minutes_played"] or 0)
        if m <= 0:
            continue
        mins[r["player_id"]] += m
        if r["starter"] == "1":
            starts[r["player_id"]] += 1
        else:
            subs[r["player_id"]] += 1
            sub_min[r["player_id"]] += m
    assert set(prof) == set(mins)
    for pid, p in prof.items():
        assert p["minutes"] == _r(mins[pid], 1)
        assert (p["starts"], p["sub_apps"], p["sub_minutes"]) == (starts[pid], subs[pid], _r(sub_min[pid], 1))


def test_defensive_counts_rates_and_peers(raw, prof):
    c = defaultdict(Counter)
    for e in raw["ev"]:
        pid, t = e["player_id"], e["event_type"]
        if t in ("tackle", "interception", "block", "clearance", "foul", "pressure", "duel"):
            c[pid][t] += 1
            c[pid][t + ":" + e["outcome"]] += 1
            c[pid][t + ":" + e["body_part"]] += 1
    team = {pid: r["team_id"] for pid, r in raw["players"].items()}
    entries = defaultdict(list)
    for e in raw["ev"]:
        if (e["event_type"] == "pass" and e["outcome"] == "success" and e["x_end"] is not None
                and e["x_start"] < 66.7 <= e["x_end"]):
            entries[e["match_id"]].append(e)
    faced = Counter()
    for r in raw["lineups"]:
        if float(r["minutes_played"] or 0) > 0:
            on, off = int(r["on_sec"]), int(r["off_sec"])
            faced[r["player_id"]] += sum(1 for e in entries[r["match_id"]]
                                         if e["team_id"] != team[r["player_id"]] and on <= e["clock_sec"] < off)
    checked = 0
    for pid, p in prof.items():
        if raw["players"][pid]["position"] == "GK":
            assert "defence" not in p and "keeper" in p
            continue
        d, k = p["defence"], c[pid]
        assert (d["tackles"], d["tackles_won"], d["interceptions"], d["blocks"], d["clearances"]) == (
            k["tackle"], k["tackle:success"], k["interception"], k["block"], k["clearance"])
        assert (d["clearances_head"], d["fouls"], d["pressures"], d["aerials"], d["aerials_won"]) == (
            k["clearance:head"], k["foul"], k["pressure"], k["duel"], k["duel:success"])
        contrib = k["tackle"] + k["interception"] + k["block"] + k["clearance"]
        assert d["contributions"] == contrib and d["entries_faced"] == faced[pid]
        if p["minutes"] >= 270:
            assert d["p90"]["contributions"] == _r(90 * contrib / p["minutes"], 2)
            assert d["p100"]["tackles"] == _r(100 * k["tackle"] / faced[pid], 1)
            checked += 1
        else:
            assert d["p90"] is None and "peer_pctl" not in d
    assert checked > 40
    # position peers: percentile = share below + half the ties, rounded half up
    for pos in ("DF", "MF", "FW"):
        peers = [p for pid, p in prof.items() if raw["players"][pid]["position"] == pos and p["defence"]["p90"]]
        for p in peers:
            xs = [q["defence"]["p90"]["tackles"] for q in peers]
            v = p["defence"]["p90"]["tackles"]
            want = 100 * (sum(x < v for x in xs) + 0.5 * sum(x == v for x in xs)) / len(xs)
            assert p["defence"]["peer_pctl"]["tackles"] == math.floor(want + 0.5)


def test_keeper_figures_from_shots_saves_and_lineups(raw, prof, ui):
    team = {pid: r["team_id"] for pid, r in raw["players"].items()}
    saves = Counter(e["player_id"] for e in raw["ev"] if e["event_type"] == "save")
    shots_by_match = defaultdict(list)
    for e in raw["ev"]:
        if e["event_type"] == "shot":
            shots_by_match[e["match_id"]].append(e)
    end = Counter()
    for r in raw["lineups"]:
        end[r["match_id"]] = max(end[r["match_id"]], int(r["off_sec"] or 0))
    keepers = [pid for pid in prof if raw["players"][pid]["position"] == "GK"]
    assert keepers
    total_saves = 0
    for pid in keepers:
        rows = [r for r in raw["lineups"] if r["player_id"] == pid and float(r["minutes_played"] or 0) > 0]
        faced = [e for r in rows for e in shots_by_match[r["match_id"]]
                 if e["team_id"] != team[pid] and int(r["on_sec"]) <= e["clock_sec"] < int(r["off_sec"])]
        res = Counter(raw["shots"][e["event_id"]]["shot_result"] for e in faced)
        on_t = res["goal"] + res["saved"]
        xg = sum(float(raw["shots"][e["event_id"]]["xg"]) for e in faced
                 if raw["shots"][e["event_id"]]["shot_result"] in ("goal", "saved"))
        clean = sum(1 for r in rows if r["starter"] == "1" and int(r["off_sec"]) == end[r["match_id"]]
                    and not any(e["team_id"] != team[pid] and e["outcome"] == "goal" for e in shots_by_match[r["match_id"]]))
        k = prof[pid]["keeper"]
        # every saved shot faced is one of this keeper's save events
        assert k["saves"] == saves[pid] == res["saved"]
        total_saves += k["saves"]
        assert (k["shots_faced"], k["on_target"], k["conceded"], k["clean_sheets"]) == (len(faced), on_t, res["goal"], clean)
        assert k["xg_faced"] == _r(xg, 2) and k["conceded_minus_xg"] == _r(res["goal"] - xg, 2)
        if on_t:
            assert k["save_pct"] == _r(100 * saves[pid] / on_t, 1)
        ps = [e for e in raw["ev"] if e["event_type"] == "pass" and e["player_id"] == pid]
        long_ = sum(1 for e in ps if float(raw["passes"][e["event_id"]]["pass_distance_m"]) >= 32.0)
        assert k["passes"] == len(ps) and k["long_share"] == (_r(100 * long_ / len(ps), 1) if ps else None)
    assert total_saves == sum(saves.values())
    # the keeper map: one point per shot faced, mirrored into the keeper's frame
    files = {p.stem[-3:].upper(): json.loads(p.read_text()) for p in (DATA / "matches").glob("players-[a-z][a-z][a-z].json")}
    for pid in keepers:
        pts = files[raw["players"][pid]["team_id"][2:].upper()]["players"][pid].get("shots_faced", [])
        assert len(pts) == prof[pid]["keeper"]["shots_faced"]
        for eid, clock, x, y, result, xg in pts:
            e = next(e for e in shots_by_match[eid[:5]] if e["event_id"] == eid)
            assert (x, y, result) == (_r(100 - e["x_start"], 1), _r(100 - e["y_start"], 1), raw["shots"][eid]["shot_result"])


def test_passing_extras(raw, prof):
    c = defaultdict(Counter)
    for e in raw["ev"]:
        if e["event_type"] != "pass" or e["outcome"] != "success":
            continue
        k = c[e["player_id"]]
        k["prog"] += raw["passes"][e["event_id"]]["is_progressive"] == "1"
        k["ft"] += e["x_start"] < 66.7 <= e["x_end"]
        box = lambda x, y: x >= 84 and 22 <= y <= 78
        k["box"] += box(e["x_end"], e["y_end"]) and not box(e["x_start"], e["y_start"])
    for pid, p in prof.items():
        x = p["passing"]
        assert (x["progressive"], x["into_final_third"], x["into_box"]) == (c[pid]["prog"], c[pid]["ft"], c[pid]["box"])


def test_chance_lists_and_summaries(raw, prof, ui):
    assisted = {s["assist_event_id"]: s for s in raw["shots"].values() if s["assist_event_id"]}
    kp = defaultdict(list)
    for e in raw["ev"]:
        if e["event_type"] == "pass" and raw["passes"][e["event_id"]]["is_key_pass"] == "1":
            kp[e["player_id"]].append(e)
    files = {p.stem[-3:].upper(): json.loads(p.read_text()) for p in (DATA / "matches").glob("players-[a-z][a-z][a-z].json")}
    rows = {p["id"]: p for p in ui["players"]}
    total = xa_all = 0
    for pid, p in prof.items():
        evs = kp.get(pid, [])
        ch = p["chances"]
        assert ch["total"] == len(evs)
        sp = [e for e in evs if raw["passes"][e["event_id"]]["pass_type"] == "corner" or e["play_pattern"] == "set_piece"]
        assert ch["set_piece"] == len(sp) == rows[pid]["chances_set_piece"]
        assert ch["open_play"] == len(evs) - len(sp) == rows[pid]["chances_open_play"]
        assert ch["kinds"]["corner"] == sum(1 for e in evs if raw["passes"][e["event_id"]]["pass_type"] == "corner")
        xa = sum(round(float(raw["passes"][e["event_id"]]["xa"]) * 10_000) for e in evs)
        total += len(evs)
        xa_all += xa
        if evs:
            assert ch["xa_per"] == half_up3(xa, len(evs))
            lst = files[p_team(raw, pid)]["players"][pid]["chances"]
            assert sorted(r[0] for r in lst) == sorted(e["event_id"] for e in evs)
            for r in lst:
                s = assisted[r[0]]
                assert r[6] == _r(float(raw["passes"][r[0]]["xa"]), 2) == _r(float(s["xg"]), 2)
                assert r[7] == s["shot_result"]
    assert total == sum(1 for r in raw["passes"].values() if r["is_key_pass"] == "1")
    assert ui["profiles"]["league_chances"] == dict(total=total, xa_per=half_up3(xa_all, total))


def half_up3(total_1e4, n):
    """Mean of xa values (in ten-thousandths) to 3 decimals, half up, in integers."""
    return (total_1e4 * 2 + n * 10) // (n * 20) / 1000


def p_team(raw, pid):
    return raw["players"][pid]["team_id"][2:].upper()


def test_pass_map_lists_are_the_most_progressive_completed_forward_passes(raw, prof):
    """players-<code>.json passes: per player the 25 completed forward passes that gained the most
    ground (ties by event id), typed key pass, else progressive, else forward; recomputed from
    events.csv and passes.csv."""
    files = {p.stem[-3:].upper(): json.loads(p.read_text()) for p in (DATA / "matches").glob("players-[a-z][a-z][a-z].json")}
    for f in files.values():
        assert f["pass_types"] == ["forward", "progressive", "key_pass"]
    fwd = defaultdict(list)
    for e in raw["ev"]:
        if e["event_type"] == "pass" and e["outcome"] == "success" and e["player_id"]:
            pr = raw["passes"][e["event_id"]]
            if pr["is_forward"] == "1":
                fwd[e["player_id"]].append(e)
    seen = 0
    for pid in prof:
        got = files[p_team(raw, pid)]["players"].get(pid, {}).get("passes", [])
        want = sorted(fwd.get(pid, []), key=lambda e: (-(e["x_end"] - e["x_start"]), e["event_id"]))[:25]
        assert [r[0] for r in got] == [e["event_id"] for e in want], pid
        for r, e in zip(got, want):
            pr = raw["passes"][e["event_id"]]
            t = 2 if pr["is_key_pass"] == "1" else 1 if pr["is_progressive"] == "1" else 0
            assert r[1:] == [_r(e["x_start"], 1), _r(e["y_start"], 1), _r(e["x_end"], 1), _r(e["y_end"], 1), t]
        seen += len(got)
    assert seen > 0


def test_whole_minutes_are_the_minutes_rounded_half_up(prof):
    for p in prof.values():
        assert p["minutes_whole"] == math.floor(p["minutes"] + 0.5) and isinstance(p["minutes_whole"], int)


def test_defensive_points_count_every_action(raw, prof):
    files = {p.stem[-3:].upper(): json.loads(p.read_text()) for p in (DATA / "matches").glob("players-[a-z][a-z][a-z].json")}
    for pid, p in prof.items():
        if "defence" not in p:
            continue
        pts = files[p_team(raw, pid)]["players"].get(pid, {}).get("defence", [])
        d = p["defence"]
        assert Counter(t for *_, t in pts) == Counter({i: n for i, n in enumerate(
            (d["tackles"], d["interceptions"], d["blocks"], d["clearances"])) if n})


def test_match_lineups_are_the_starters_by_listed_position():
    lu = _csv("lineups.csv")
    players = {r["player_id"]: r for r in _csv("players.csv")}
    for p in sorted((DATA / "matches").glob("m_0*.json"))[:12]:
        f = json.loads(p.read_text())
        mid = f["match_id"]
        for side in ("home", "away"):
            x = f["lineups"][side]
            tid = "t_" + x["code"].lower()
            want = {r["player_id"] for r in lu if r["match_id"] == mid and r["team_id"] == tid and r["starter"] == "1"}
            assert {r[0] for r in x["xi"]} == want and len(x["xi"]) == 11
            for pid, shirt, pos, line, slot, of in x["xi"]:
                assert (shirt, pos) == (int(players[pid]["shirt"]), players[pid]["position"])
                assert pid in f["players"]
            assert len({(r[3], r[4]) for r in x["xi"]}) == 11
            count = Counter(r[2] for r in x["xi"])
            assert x["label"] == f"{count['DF']}-{count['MF']}-{count['FW']}"


def test_profiles_are_deterministic():
    from engine.tables import load
    s = load(SEASON)
    a = PP.profiles(s, PP.lineup_rows(SEASON))
    b = PP.profiles(s, PP.lineup_rows(SEASON))
    dump = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"))
    assert dump(a) == dump(b)
