"""Every engine metric on tiny hand-built event lists with answers worked out by hand, plus the
planted-trap checks for the Step 4 metrics on the generated season."""
import pytest

from engine import flow as F
from engine import metrics as M
from engine import threat as T

H, A = "t_h", "t_a"


class Builder:
    """Builds event rows with every field the engine reads. Clock in seconds; home = H."""

    def __init__(self, match_id="m_x"):
        self.mid, self.rows, self.passes, self.shots = match_id, [], {}, {}

    def add(self, etype, team, clock, x, y, xe=None, ye=None, outcome="success", player=None,
            pattern="open_play", poss=1, seq=1, score=(0, 0), **pass_kw):
        eid = f"{self.mid}_e{len(self.rows) + 1:04d}"
        self.rows.append(dict(
            event_id=eid, match_id=self.mid, team_id=team, opponent_team_id=A if team == H else H,
            player_id=player or f"{team}_p", event_type=etype, x_start=x, y_start=y, x_end=xe, y_end=ye,
            outcome=outcome, clock_sec=clock, minute=clock // 60, possession_id=poss, sequence_id=seq,
            play_pattern=pattern, score_home=score[0], score_away=score[1], home_team_id=H,
            under_pressure=0, period=1 if clock < 2700 else 2))
        if etype == "pass":
            self.passes[eid] = dict(pass_type=pass_kw.get("pass_type", "short"),
                                    is_key_pass=pass_kw.get("key", 0), xa=pass_kw.get("xa", 0.0))
        if etype == "shot":
            self.shots[eid] = dict(xg=pass_kw.get("xg", 0.1), shot_type=pass_kw.get("shot_type", "open_play"))
        return eid


# ---------- metrics.py ----------

def test_territory_metrics():
    b = Builder()
    b.add("pass", H, 10, 70, 50, 75, 50)              # f3 pass, not an entry
    b.add("pass", H, 12, 60, 10, 70, 10)              # entry, left_flank
    b.add("pass", H, 14, 70, 50, 90, 50)              # f3 pass + box entry
    b.add("pass", H, 16, 60, 50, 70, 90, outcome="fail")  # failed entry, right_flank
    b.add("pass", A, 20, 80, 50, 82, 50)              # opponent f3 pass
    ev = b.rows
    assert M.final_third_passes(ev, H).value == 2
    ent = M.final_third_entries(ev, H)
    assert ent.value == 1 and ent.detail["lanes"]["left_flank"] == 1
    assert M.box_entries(ev, H).value == 1
    tilt = M.field_tilt(ev, H)
    assert tilt.value == pytest.approx(2 / 3) and tilt.sample_size == 3
    comp = M.entry_completion_by_lane(ev, A)           # entries conceded by A = made by H
    assert comp.detail["lanes"]["left_flank"] == dict(attempted=1, completed=1, rate=1.0)
    assert comp.detail["lanes"]["right_flank"] == dict(attempted=1, completed=0, rate=0.0)
    assert comp.value == 0.5
    assert M.field_tilt(ev, H, window=(0, 11)).value == 1.0
    assert M.field_tilt(ev, H, state="leading").sample_size == 0


def test_shooting_metrics():
    b = Builder()
    b.add("shot", H, 10, 90, 50, xg=0.04)
    b.add("shot", H, 20, 90, 50, xg=0.30)
    b.add("shot", H, 30, 95, 50, xg=0.76, shot_type="penalty")
    b.add("shot", A, 40, 90, 50, xg=0.5)
    assert M.xg_sum(b.rows, b.shots, H).value == pytest.approx(1.10)
    assert M.npxg_sum(b.rows, b.shots, H).value == pytest.approx(0.34)
    bands = M.shots_by_xg_band(b.rows, b.shots, H).value
    assert bands == {"0.00-0.05": 1, "0.05-0.10": 0, "0.10-0.20": 0, "0.20-0.40": 1, "0.40-1.00": 1}


def test_passing_metrics():
    b = Builder()
    b.add("pass", H, 10, 40, 50, 50, 10, player="p1")          # forward, wide
    b.add("pass", H, 12, 40, 50, 50, 50, player="p1")          # forward, central
    b.add("pass", H, 14, 40, 50, 42, 50, player="p1")          # not forward
    b.add("pass", H, 16, 70, 90, 92, 50, player="p2", key=1, xa=0.2)
    b.add("pass", H, 18, 100, 0, 92, 50, player="p2", key=1, xa=0.1, pass_type="corner", pattern="set_piece")
    fw = M.forward_passes_wide_share(b.rows, H, "p1")
    assert fw.value == 2 and fw.detail["wide_share"] == 0.5
    assert M.forward_passes_by_player(b.rows, H).value[0] == ("p1", 2)
    cc = M.chances_created(b.rows, b.passes, H, "p2")
    assert (cc.value, cc.detail["open_play"], cc.detail["set_piece"]) == (2, 1, 1)
    assert M.chances_by_player(b.rows, b.passes, H).value == [("p2", 2)]
    # directness excludes the set piece: 3 forward of 4 open-play passes
    assert M.directness(b.rows, H).value == pytest.approx(3 / 4)


def test_style_metrics():
    b = Builder()
    b.add("pass", H, 10, 30, 50, 35, 50, seq=1)
    b.add("pass", H, 14, 35, 50, 40, 50, seq=1)
    b.add("pass", H, 20, 40, 50, 45, 50, seq=1)       # seq 1: 3 passes, gaps 4 and 6
    b.add("pass", H, 30, 30, 50, 60, 50, seq=2, pattern="counter")   # seq 2: 1 pass, counter
    b.add("tackle", H, 40, 60, 50)
    b.add("interception", H, 41, 20, 50)
    b.add("pressure", H, 42, 70, 50)
    b.add("pass", A, 43, 30, 50, 35, 50, seq=3)       # opponent passes in own 60%
    b.add("pass", A, 44, 30, 50, 35, 50, seq=3)
    ev = b.rows
    assert M.tempo(ev, H).value == 5.0
    assert M.passes_per_sequence(ev, H).value == 2.0
    assert M.counter_share(ev, H).value == 0.5
    assert M.ball_won_height(ev, H).value == 40.0
    assert M.press_intensity(ev, H).value == 0.5        # 1 pressure / 2 opponent passes
    assert M.ppda(ev, H).value == 2.0                   # 2 passes / 1 action at x >= 40


def test_chances_conceded_by_lane():
    b = Builder()
    b.add("pass", A, 10, 60, 10, 70, 10, seq=5)        # A enters down its left
    b.add("shot", A, 12, 90, 50, seq=5)
    b.add("shot", A, 30, 90, 50, seq=6)                # no entry in that sequence
    r = M.chances_conceded_by_lane(b.rows, H)
    assert r.detail["lanes"]["left_flank"] == 1 and r.detail["no_entry"] == 1


def test_intervals_and_confidence():
    lo, hi = M.wilson_interval(0, 10)
    assert lo == 0.0 and 0.25 < hi < 0.35
    lo, hi = M.wilson_interval(50, 100)
    assert lo == pytest.approx(0.404, abs=0.002) and hi == pytest.approx(0.596, abs=0.002)
    assert M.share_confidence(300, 1000, 0.20) == "high"
    assert M.share_confidence(30, 100, 0.20) == "medium"
    assert M.share_confidence(22, 100, 0.20) == "low"
    assert M.min_confidence("high", "low", "medium") == "low"


# ---------- threat.py ----------

def test_fit_grid_and_xt_added(monkeypatch):
    monkeypatch.setattr(T, "MIN_CELL_N", 1)
    b = Builder()
    b.add("pass", H, 10, 95, 50, 96, 52, poss=1)       # cell (11, 4)
    b.add("shot", H, 11, 96, 52, poss=1, xg=0.4)       # cell (11, 4): possession xG 0.4
    b.add("pass", H, 20, 5, 50, 10, 50, poss=2)        # cell (0, 4): possession with no shot
    g = T.fit_grid(b.rows, b.shots)
    assert g[11][4] == pytest.approx(0.4) and g[0][4] == 0.0
    grid = [[0.0] * T.NY for _ in range(T.NX)]
    grid[11][4], grid[6][4] = 0.3, 0.1
    c = Builder()
    c.add("pass", H, 10, 50, 50, 95, 50)               # (6,4) -> (11,4): +0.2
    c.add("pass", H, 20, 95, 50, 50, 50)               # (11,4) -> (6,4): -0.2
    c.add("pass", H, 30, 50, 50, 95, 50, outcome="fail")   # failed: 0
    r = T.xt_added(c.rows, grid, H)
    assert r.value == pytest.approx(0.0) and r.sample_size == 2
    assert r.detail["per_pass"][r.evidence_event_ids[0]] == pytest.approx(0.2)


def test_pass_quality_ratio():
    grid = [[0.0] * T.NY for _ in range(T.NX)]
    for i in (10, 11):
        for j in (3, 4):
            grid[i][j] = 1.0
    hot = T.high_threat_cells(grid)
    assert (11, 4) in hot and (11, 0) not in hot
    b = Builder()
    b.add("pass", H, 10, 70, 50, 90, 50, player="me")  # into hot central cell
    b.add("pass", H, 11, 70, 10, 85, 5, player="me")   # wide, cold
    for k in range(4):                                  # league: 1 of 5 forward passes hot
        b.add("pass", H, 20 + k, 40, 50, 60, 50, player="other")
    r = T.pass_quality_ratio(b.rows, grid, "me")
    assert r.detail["player_share"] == 0.5 and r.detail["league_share"] == pytest.approx(1 / 6)
    assert r.value == pytest.approx(3.0)


# ---------- flow.py ----------

def test_xa_split():
    b = Builder()
    b.add("pass", H, 10, 70, 50, 90, 50, player="p", key=1, xa=0.25)
    b.add("pass", H, 20, 100, 0, 92, 50, player="p", key=1, xa=0.05, pass_type="corner", pattern="set_piece")
    b.add("pass", H, 30, 70, 50, 80, 50, player="p")
    r = F.xa_split(b.rows, b.passes, player_id="p")
    assert r.value == pytest.approx(0.30)
    assert r.detail["open_play_xa"] == pytest.approx(0.25) and r.detail["set_piece_xa"] == pytest.approx(0.05)


def test_territorial_stress():
    b = Builder()
    b.add("pass", H, 100, 55, 50, 60, 50)
    b.add("pressure", A, 101, 40, 50)                  # pressure does not break the spell
    b.add("pass", H, 130, 60, 50, 70, 50)
    b.add("pass", H, 160, 70, 50, 72, 50)              # spell 1: 100 -> 160 = 60 s
    b.add("pass", A, 170, 20, 50, 30, 50)              # opponent on the ball: break
    b.add("pass", H, 200, 55, 50, 60, 50)
    b.add("pass", H, 210, 45, 50, 60, 50)              # own half: break; spell 2 = 0 s
    r = F.territorial_stress(b.rows, H)
    assert r.value == 60 and len(r.evidence_event_ids) == 3
    assert r.detail["spells"][0]["start_sec"] == 100


def test_shot_clusters():
    b = Builder()
    for t, xg in ((100, 0.1), (150, 0.2), (260, 0.05), (1000, 0.3)):
        b.add("shot", H, t, 90, 50, xg=xg)
    r = F.shot_clusters(b.rows, b.shots, H)
    assert r.value == 3 and r.detail["clusters"][0]["xg"] == pytest.approx(0.35)


def test_rhythm_series():
    b = Builder()
    for t in (60, 70, 130, 180, 190, 200):
        b.add("possession_change", H, t, 50, 50)
    r = F.rhythm(b.rows, end_minute=3, length=4)
    assert r.value == [0.0, 2.0, 1.0, 3.0] and r.detail["minutes"] == [0, 1, 2, 3]
    assert len(F.rhythm(b.rows, end_minute=20).value) == 15


def test_momentum():
    grid = [[0.0] * T.NY for _ in range(T.NX)]
    b = Builder()
    b.add("shot", H, 60, 90, 50, xg=0.5)
    b.add("shot", A, 360, 90, 50, xg=0.5)              # exactly one half-life later
    r = F.momentum(b.rows, b.shots, grid, H, A, half_life_sec=300)
    by_t = dict(r.value)
    assert by_t[0] == 0.0 and by_t[60] == pytest.approx(100.0)
    # at 360: home 0.25 (one half-life of decay), away 0.5 -> 100 * (0.25 - 0.5) / 0.75
    assert by_t[360] == pytest.approx(-100 / 3, abs=1e-6)


def test_milestones():
    b = Builder()
    b.add("shot", H, 10, 90, 50, outcome="goal", player="s")
    b.add("shot", H, 20, 90, 50, outcome="goal", player="s")    # not a second "first goal"
    for k in range(25):
        b.add("pass", H, 30 + k, 40, 50, 45, 50, player="q")
    r = F.milestones(b.rows)
    kinds = [(m["kind"], m["player_id"], m["count"]) for m in r.detail["milestones"]]
    assert kinds == [("first_goal", "s", 1), ("pass_count", "q", 25)]


# ---------- planted traps (generated season) ----------

@pytest.fixture(scope="module")
def season(tmp_path_factory):
    from data_gen.generate import main
    from engine.tables import load
    root = tmp_path_factory.mktemp("fx")
    gt = main(2026, root / "season", root / "showcase")
    return load(root / "season"), gt


def test_volume_passer_pass_quality_far_below_league(season):
    from engine.tables import team_events
    ds, gt = season
    pid = next(k for k, v in gt["planted_players"].items() if v["trap"] == "volume_passer")
    team = ds.players[pid]["team_id"]
    r = T.pass_quality_ratio(team_events(ds, team), T.xt_grid(ds), pid, ds.events, team)
    assert r.value < 0.35 and r.sample_size >= 200


def test_corner_specialist_open_play_xa_low_vs_chances(season):
    from collections import Counter
    ds, gt = season
    pid = next(k for k, v in gt["planted_players"].items() if v["trap"] == "corner_specialist")
    cc = Counter(e["player_id"] for e in ds.events if e["event_type"] == "pass" and ds.passes[e["event_id"]]["is_key_pass"])
    per_chance = {p: F.xa_split(ds.events, ds.passes, player_id=p).detail["open_play_xa"] / n
                  for p, n in cc.items() if n >= 15}
    median = sorted(per_chance.values())[len(per_chance) // 2]
    mine = F.xa_split(ds.events, ds.passes, player_id=pid)
    assert per_chance[pid] < 0.6 * median
    assert mine.detail["open_play_xa"] < mine.detail["set_piece_xa"]
