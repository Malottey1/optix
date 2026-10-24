"""Pattern detectors on hand-built micro-sequences (positive, negative, near-threshold), each
checked against its independent recompute, plus anchor mutations the recompute must reject."""
import math

import pytest

from engine import patterns as P
from engine.patterns import (bait_switch, counter_press, cutback, direct_transition, elastic_low_block,
                             flank_isolation, helpers, press_resistant, pressed_presser, rest_defence,
                             set_piece_dependence, starved_finisher, tactical_fouling)
from engine.tables import Dataset

H, A = "t_h", "t_a"


class B:
    """Event rows with every field the detectors read; clock in seconds."""

    def __init__(self, mid="m_p"):
        self.mid, self.rows, self.passes, self.shots = mid, [], {}, {}
        self.clock = 0

    def add(self, etype, team, x, y, xe=None, ye=None, outcome="success", poss=1, dt=2, player=None,
            pressed=0, xg=0.1, ptype="short", assist="", pattern="open_play", stype="open_play"):
        self.clock += dt
        eid = f"{self.mid}_e{len(self.rows) + 1:04d}"
        self.rows.append(dict(event_id=eid, match_id=self.mid, team_id=team, opponent_team_id=A if team == H else H,
                              player_id=player or f"{team}_p", event_type=etype, x_start=x, y_start=y, x_end=xe,
                              y_end=ye, outcome=outcome, clock_sec=self.clock, period=1, possession_id=poss,
                              under_pressure=pressed, score_home=0, score_away=0, home_team_id=H,
                              play_pattern=pattern))
        if etype == "pass":
            self.passes[eid] = dict(pass_distance_m=round(math.hypot((xe - x) * 1.05, (ye - y) * 0.68), 1),
                                    pass_type=ptype, is_key_pass=0, xa=0.0)
        if etype == "shot":
            self.shots[eid] = dict(xg=xg, shot_type=stype, assist_event_id=assist)
        return eid

    def ds(self, position="FW"):
        players = {f"{t}_p": dict(player_id=f"{t}_p", team_id=t, name=t, shirt="9", position=position) for t in (H, A)}
        players.update({r["player_id"]: dict(player_id=r["player_id"], team_id=r["team_id"], name=r["player_id"],
                                             shirt="9", position=position) for r in self.rows})
        return Dataset({H: dict(team_id=H, code="HHH", name="H"), A: dict(team_id=A, code="AAA", name="A")}, players,
                       {self.mid: dict(match_id=self.mid, home_team_id=H, away_team_id=A)}, self.rows,
                       self.passes, self.shots)


def _recompute_matches(ds, f, scope=None):
    sc = scope if scope is not None else ds.events
    subj = {"kind": "player", "id": f.player_id} if f.player_id else {"kind": "team", "id": f.team_id}
    vals, bad = P.recompute(ds, f.family, ds.events[0]["match_id"], subj, f.evidence, sc, f.window)
    assert bad == [] and vals is not None
    for k, v in f.values.items():
        assert vals[k] == pytest.approx(v), k
    return vals


# ---------- P1 bait and switch ----------

def _build(b, n=15, y=20.0, poss=1, long_at=None):
    x = 30.0
    for i in range(n):
        dy = 3.0 if i % 2 else -3.0
        b.add("pass", H, x, y, x + 2, y + dy, poss=poss)
        x, y = x + 2, y + dy


def test_bait_switch_positive_and_recompute():
    b = B()
    _build(b)
    last = b.rows[-1]
    b.add("pass", H, last["x_end"], last["y_end"], last["x_end"] + 8, 85.0)        # switch, dy >= 40, >= 25 m
    b.add("carry", H, last["x_end"] + 8, 85.0, 80.0, 75.0)
    b.add("pass", H, 80.0, 75.0, 90.0, 65.0)                                         # box entry
    b.add("shot", H, 90.0, 65.0, xg=0.2)                                             # on the far side
    ds = b.ds()
    f = bait_switch.detect(ds.events, H, ds.passes, ds.shots)
    assert f and f.values["amount"] == 1 and f.values["shots"] == 1 and f.values["build_passes"] == 15
    assert f.values["finish_side_share"] == 100.0 and f.values["build_left"] == 1
    _recompute_matches(ds, f)


def test_bait_switch_negative_and_near_threshold():
    b = B()
    _build(b, n=14)                                                                   # one pass short of the build
    last = b.rows[-1]
    b.add("pass", H, last["x_end"], last["y_end"], last["x_end"] + 8, 85.0)
    b.add("pass", H, 70.0, 85.0, 90.0, 55.0)
    ds = b.ds()
    assert bait_switch.detect(ds.events, H, ds.passes, ds.shots) is None
    b2 = B()
    _build(b2)
    last = b2.rows[-1]
    b2.add("pass", H, last["x_end"], last["y_end"], last["x_end"] + 8, 58.0)        # ends central: no switch
    b2.add("pass", H, 70.0, 58.0, 90.0, 55.0)
    ds2 = b2.ds()
    assert bait_switch.detect(ds2.events, H, ds2.passes, ds2.shots) is None


def test_bait_switch_recompute_rejects_mutations():
    b = B()
    _build(b)
    last = b.rows[-1]
    b.add("pass", H, last["x_end"], last["y_end"], last["x_end"] + 8, 85.0)
    b.add("pass", H, 70.0, 85.0, 90.0, 55.0)
    ds = b.ds()
    f = bait_switch.detect(ds.events, H, ds.passes, ds.shots)
    ev = f.evidence
    swapped = ev[:2] + [ev[1]] + ev[3:]                                               # switch replaced by a build pass
    assert P.recompute(ds, f.family, "m_p", {"kind": "team", "id": H}, swapped, ds.events, None)[1]
    assert P.recompute(ds, f.family, "m_p", {"kind": "team", "id": H}, ev[:3], ds.events, None)[1]   # dropped anchor
    ds.events[-2]["y_end"] = 60.0                                                     # shift: switch ends central... box entry stays
    sw = next(e for e in ds.events if e["event_id"] == ev[2])
    sw["y_end"] = 50.0
    assert P.recompute(ds, f.family, "m_p", {"kind": "team", "id": H}, ev, ds.events, None)[1]


# ---------- P2 cut-back ----------

def test_cutback_positive_negative_and_mutation():
    b = B()
    b.add("pass", H, 80.0, 15.0, 95.0, 12.0)                                         # into the wide goal-line zone
    b.add("pass", H, 95.0, 12.0, 87.0, 50.0)                                         # back to the apex
    b.add("shot", H, 87.0, 50.0, xg=0.3)
    cross = b.add("pass", H, 75.0, 90.0, 90.0, 50.0, poss=2, ptype="cross")
    b.add("shot", H, 90.0, 50.0, poss=2, xg=0.1, assist=cross)
    ds = b.ds()
    f = cutback.detect(ds.events, H, ds.passes, ds.shots)
    assert f.values["amount"] == 1 and f.values["xg_per_shot"] == pytest.approx(0.3)
    assert f.values["cross_shots"] == 1 and f.values["cross_xg_per_shot"] == pytest.approx(0.1)
    _recompute_matches(ds, f)
    ds.events[1]["x_end"] = 93.0                                                      # cut-back ends outside the apex
    assert P.recompute(ds, f.family, "m_p", {"kind": "team", "id": H}, f.evidence, ds.events, None)[1]
    b2 = B()
    b2.add("pass", H, 80.0, 15.0, 93.5, 12.0)                                        # just short of the goal line
    b2.add("pass", H, 93.5, 12.0, 87.0, 50.0)
    b2.add("shot", H, 87.0, 50.0)
    d2 = b2.ds()
    assert cutback.detect(d2.events, H, d2.passes, d2.shots) is None


# ---------- P3 flank isolation ----------

def _strip(b, n, y=8.0, central_at=None):
    x = 50.0
    for i in range(n):
        ye = 50.0 if i == central_at else y + (1 if i % 2 else -1)
        b.add("pass", H, x, y, x + 2, ye)
        x, y = x + 2, ye


def test_flank_isolation_positive_negative():
    b = B()
    _strip(b, 11)
    b.add("shot", H, 80.0, 30.0, xg=0.05)
    ds = b.ds()
    f = flank_isolation.detect(ds.events, H, ds.passes, ds.shots)
    assert f.values["amount"] == 1 and f.values["shots"] == 1
    _recompute_matches(ds, f)
    b2 = B()
    _strip(b2, 10, central_at=5)                                                      # one pass ends central
    d2 = b2.ds()
    assert flank_isolation.detect(d2.events, H, d2.passes, d2.shots) is None
    b3 = B()
    _strip(b3, 9)                                                                     # nine passes: no window
    d3 = b3.ds()
    assert flank_isolation.detect(d3.events, H, d3.passes, d3.shots) is None


# ---------- P5 counter-press, P8 fouls after losses, P6 rest defence (league rates fixed) ----------

@pytest.fixture
def fixed_league(monkeypatch):
    for m in (counter_press, rest_defence, tactical_fouling):
        monkeypatch.setattr(m, "league", lambda ds, key, fn: 0.01)


def _loss_regain(b, poss, n_press=2, regain_dt=1):
    b.add("pass", H, 80.0, 50.0, 85.0, 50.0, outcome="fail", poss=poss)
    lo = b.add("possession_change", A, 18.0, 50.0, poss=poss + 1, dt=1)              # lost at x 82 (H frame)
    for _ in range(n_press):
        b.add("pressure", H, 80.0, 50.0, poss=poss + 1, dt=1)
    b.add("tackle", H, 80.0, 50.0, poss=poss + 1, dt=regain_dt)
    rg = b.add("possession_change", H, 80.0, 50.0, poss=poss + 2, dt=0)
    return lo, rg


def test_counter_press(fixed_league):
    b = B()
    _loss_regain(b, 1)
    _loss_regain(b, 4)
    _loss_regain(b, 7, n_press=1)                                                     # near: one pressure only
    ds = b.ds()
    f = counter_press.detect(ds, ds.events, H)
    assert f.values["amount"] == 2 and f.values["losses"] == 3
    _recompute_matches(ds, f)
    b2 = B()
    _loss_regain(b2, 1)
    _loss_regain(b2, 4, regain_dt=3)                                                  # regained after 5 s
    d2 = b2.ds()
    assert counter_press.detect(d2, d2.events, H) is None


def test_fouls_after_losses(fixed_league):
    b = B()
    for poss in (1, 3, 5):
        b.add("possession_change", A, 50.0, 50.0, poss=poss)                          # lost in midfield
        b.add("foul", H, 50.0, 50.0, poss=poss, dt=2)
    b.add("possession_change", A, 50.0, 50.0, poss=7)                                 # a loss without a foul
    ds = b.ds()
    f = tactical_fouling.detect(ds, ds.events, H)
    assert f.values["amount"] == 3 and f.values["losses"] == 4
    _recompute_matches(ds, f)
    b2 = B()
    for poss in (1, 3, 5):
        b2.add("possession_change", A, 50.0, 50.0, poss=poss)
        b2.add("foul", H, 50.0, 50.0, poss=poss, dt=6)                                # too late
    d2 = b2.ds()
    assert tactical_fouling.detect(d2, d2.events, H) is None


def test_rest_defence(fixed_league):
    b = B()
    for i in range(8):
        b.add("pass", H, 75.0, 50.0, 80.0, 50.0, poss=1)                               # H owns the final third
    for poss in (2, 4):
        b.add("possession_change", A, 30.0, 50.0, poss=poss)                          # A wins it in its own half
        b.add("shot", A, 85.0, 50.0, poss=poss, dt=5, xg=0.2)
    ds = b.ds()
    f = rest_defence.detect(ds, ds.events, H)
    assert f.values["amount"] == 2 and f.values["tilt"] == 100.0
    _recompute_matches(ds, f)
    ds.events[-1]["clock_sec"] += 20                                                  # the shot comes too late
    assert P.recompute(ds, f.family, "m_p", {"kind": "team", "id": H}, f.evidence, ds.events, None)[1]


# ---------- P7 starved finisher, P4 low block (league lines fixed) ----------

def test_starved_finisher(monkeypatch):
    monkeypatch.setattr(starved_finisher, "lines", lambda ds, c=None: {"FW": (25.0, 0.002)})
    b = B()
    for _ in range(8):
        b.add("pass", H, 60.0, 50.0, 62.0, 50.0, player="fw9")
    b.add("shot", H, 90.0, 50.0, player="fw9", xg=0.3)
    b.add("shot", H, 88.0, 45.0, player="fw9", xg=0.2)
    b.add("shot", H, 88.0, 45.0, player="fw9", xg=0.05, pressed=1)
    ds = b.ds()
    fs = starved_finisher.detect(ds, ds.events, H)
    assert len(fs) == 1 and fs[0].values["amount"] == 11 and fs[0].values["unpressured_shots"] == 2
    _recompute_matches(ds, fs[0])
    ds.events[-1]["under_pressure"] = 0                                               # now three unpressured shots
    assert P.recompute(ds, fs[0].family, "m_p", {"kind": "player", "id": "fw9"}, fs[0].evidence, ds.events, None)[1]


def test_low_block_window(monkeypatch):
    monkeypatch.setattr(elastic_low_block, "lines", lambda ds, c=None: {"median_xg": 0.08, "block_line": 3})
    monkeypatch.setattr(elastic_low_block, "_momentum", lambda ds, mid, a: [(t, 0.0) for t in range(0, 2000, 60)])
    b = B()
    for i in range(40):
        b.add("pass", A, 75.0, 50.0, 78.0, 50.0, poss=1, dt=25)                       # A's territory
        if i % 8 == 0:
            b.add("shot", A, 75.0, 50.0, poss=1, dt=5, xg=0.03)                        # from range
            b.add("block", H, 25.0, 50.0, poss=1, dt=1)
            b.add("clearance", H, 15.0, 50.0, 40.0, 50.0, poss=1, dt=1)
    ds = b.ds()
    f = elastic_low_block.detect(ds, "m_p", H)
    assert f is not None and f.values["opp_tilt"] == 100.0 and f.values["outside_share"] == 100.0
    vals, bad = P.recompute(ds, f.family, "m_p", {"kind": "team", "id": H}, f.evidence, ds.events, f.window)
    assert bad == [] and vals["amount"] == f.values["amount"]
    assert elastic_low_block.detect(ds, "m_p", A) is None                             # the attacker is not a low block


def test_helpers_zones():
    assert helpers.side_of(39.9) == "left" and helpers.side_of(60) == "right" and helpers.side_of(50) == "centre"
    assert helpers.outer_strip(14.9) == "left" and helpers.outer_strip(85.1) == "right" and helpers.outer_strip(50) is None
    assert helpers.in_apex(82, 38) and not helpers.in_apex(93, 50)
    assert helpers.in_goal_line_wide(94, 25) and not helpers.in_goal_line_wide(94, 30)
    assert set(P.FAMILIES) == set(P.MODULES) and len(P.FAMILIES) == 12      # Tier 1 (8) and P11, P15, P16, P17


# ---------- Tier 2: P15 set-piece dependence, P17 direct transition, P16 press-resistant, P11 pressed presser ----------

def _team(ds, f):
    return P.recompute(ds, f.family, "m_p", {"kind": "team", "id": f.team_id}, f.evidence, ds.events, None)


def test_set_piece_dependence(monkeypatch):
    monkeypatch.setattr(set_piece_dependence, "league", lambda ds, key, fn: 0.15)
    b = B()
    for _ in range(3):
        b.add("shot", H, 92.0, 50.0, xg=0.2, pattern="set_piece")
    b.add("shot", H, 80.0, 50.0, xg=0.1)
    b.add("shot", H, 89.0, 50.0, xg=0.76, pattern="set_piece", stype="penalty")      # left out of both sides
    ds = b.ds()
    f = set_piece_dependence.detect(ds, ds.events, H)
    assert f.values["amount"] == 3 and f.values["share"] == pytest.approx(600 / 7)
    assert f.values["npxg"] == pytest.approx(0.7)
    _recompute_matches(ds, f)
    assert _team(ds, f.__class__(f.family, H, f.instances[:2], f.values))[1]            # one set-piece shot left out
    b2 = B()
    for _ in range(3):
        b2.add("shot", H, 92.0, 50.0, xg=0.1, pattern="set_piece")
    b2.add("shot", H, 80.0, 50.0, xg=0.5)                                              # near: share 37.5% < 40%
    d2 = b2.ds()
    assert set_piece_dependence.detect(d2, d2.events, H) is None


def _regain_shot(b, x=30.0, dt=5, poss=1):
    g = b.add("possession_change", H, x, 50.0, poss=poss)
    b.add("pass", H, x, 50.0, 70.0, 50.0, poss=poss, dt=2)
    s = b.add("shot", H, 88.0, 50.0, poss=poss, dt=dt, xg=0.1)
    return g, s


def test_direct_transition(monkeypatch):
    monkeypatch.setattr(direct_transition, "league", lambda ds, key, fn: 0.05)
    b = B()
    for poss in range(1, 9, 2):
        _regain_shot(b, poss=poss)
    b.add("possession_change", H, 60.0, 50.0, poss=11)                                # in the opponent's half: not a regain
    b.add("shot", H, 88.0, 50.0, poss=11, dt=3)
    ds = b.ds()
    f = direct_transition.detect(ds, ds.events, H)
    assert f.values["amount"] == 4 and f.values["regains"] == 4 and f.values["team_shots"] == 5
    _recompute_matches(ds, f)
    ds.events[2]["clock_sec"] += 30                                                   # the first shot comes too late
    assert _team(ds, f)[1]
    b2 = B()
    for poss in range(1, 7, 2):
        _regain_shot(b2, poss=poss)                                                   # near: three such shots
    _regain_shot(b2, poss=9, dt=12)                                                   # outside ten seconds
    d2 = b2.ds()
    assert direct_transition.detect(d2, d2.events, H) is None


def test_press_resistant():
    b = B()
    for i in range(12):
        b.add("pass", H, 40.0, 50.0, 45.0, 50.0, player="dm6", pressed=1, outcome="fail" if i == 0 else "success")
    for i in range(10):
        b.add("pass", H, 40.0, 50.0, 45.0, 50.0, player="cb4", pressed=1, outcome="fail" if i % 2 else "success")
    ds = b.ds(position="MF")
    fs = press_resistant.detect(ds, ds.events, H)
    assert [f.player_id for f in fs] == ["dm6"]
    assert fs[0].values["amount"] == 11 and fs[0].values["team_completion"] == 50.0
    _recompute_matches(ds, fs[0])
    subj = {"kind": "player", "id": "dm6"}
    assert P.recompute(ds, fs[0].family, "m_p", subj, fs[0].evidence[1:], ds.events, None)[1]   # a pass left out
    ds.events[1]["outcome"] = "fail"                                                  # 10 of 12: under 85%
    assert P.recompute(ds, fs[0].family, "m_p", subj, fs[0].evidence, ds.events, None)[1]
    b2 = B()
    for i in range(11):                                                               # near: eleven passes
        b2.add("pass", H, 40.0, 50.0, 45.0, 50.0, player="dm6", pressed=1)
    for i in range(10):
        b2.add("pass", H, 40.0, 50.0, 45.0, 50.0, player="cb4", pressed=1, outcome="fail" if i % 2 else "success")
    d2 = b2.ds(position="MF")
    assert press_resistant.detect(d2, d2.events, H) == []


def test_pressed_presser(monkeypatch):
    monkeypatch.setattr(pressed_presser, "lines", lambda ds, c=None: (0.2, 0.6))
    b = B()
    for i in range(10):
        b.add("pass", A, 50.0, 50.0, 55.0, 50.0)
        b.add("pressure", H, 50.0, 50.0)
    for i in range(10):
        b.add("pass", H, 20.0, 50.0, 25.0, 50.0, pressed=1, outcome="fail" if i < 5 else "success")
    b.add("pass", H, 40.0, 50.0, 45.0, 50.0, pressed=1, outcome="fail")               # outside the zone
    ds = b.ds()
    f = pressed_presser.detect(ds, ds.events, H)
    assert f.values["amount"] == 5 and f.values["own_passes"] == 10 and f.values["own_completion"] == 50.0
    _recompute_matches(ds, f)
    assert _team(ds, f.__class__(f.family, H, [f.instances[0][1:]], f.values))[1]       # a pass left out
    ds.events[-2]["x_start"] = 35.0                                                    # one pass moves out: 9 left
    assert _team(ds, f)[1]
    b2 = B()
    for i in range(10):
        b2.add("pass", A, 50.0, 50.0, 55.0, 50.0)
        b2.add("pressure", H, 50.0, 50.0, outcome="success" if i < 1 else "fail")
    for i in range(10):
        b2.add("pass", H, 20.0, 50.0, 25.0, 50.0, pressed=1, outcome="fail" if i < 5 else "success")
    d2 = b2.ds()
    d2.events[:] = [e for e in d2.events if not (e["event_type"] == "pressure" and e["outcome"] == "fail")]
    assert pressed_presser.detect(d2, d2.events, H) is None                           # press 0.1 below the line
