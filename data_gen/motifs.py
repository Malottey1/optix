"""Planted tactical motifs: scripted sequence behaviour that gives the pattern detectors
(engine/patterns) a known ground truth to recover.

Each motif runs at one of three existing decision points of MatchSim.run_sequence:
  * at_start: the first action of a possession that began in open play (after a turnover or a
    ball recovery), before the holder acts;
  * in_play:  the pass choice, when no restart is being taken;
  * at_shot:  a shot the simulator has already decided to take (the starved finisher re-routes it).
Motifs that add shots of their own lower the team's natural shot appetite (shot_factor), so shot
volume and goals stay in the calibrated ranges.
Scripts reuse the simulator's own construction functions (pick, emit, record_pass, pass_success,
take_shot, after_shot, foul, _won, tick, run_time), so every field (difficulty, speed, xG, xA,
clocks, teleport guard, under_pressure) is produced the usual way.

Randomness: every (motif, team) has its OWN random generator, seeded from (match seed, motif id,
team id). It is consulted only when that motif's propensity is above zero, and while a script runs
the simulator's generator is swapped for it. With every propensity at zero nothing here is called
and the main random stream is untouched (the byte-identity proof, docs/patterns.md).

Propensities live in data_gen/config.py (MOTIFS, PLAYER_MOTIFS); `scale` multiplies all of them
(0 = off, 0.5 = the detection-limit run). Strength varies with game state, so a pattern does not
fire identically in every match.
"""
from __future__ import annotations

import math
import random
from collections import Counter

from .config import MOTIF_RATES, MOTIF_SIDES, MOTIFS, PLAYER_MOTIFS, SHOT_COMP

BOX_X, BOX_Y = 84.0, (22.0, 78.0)


def _clip(v, lo, hi):
    return max(lo, min(hi, v))


def _dist_m(xs, ys, xe, ye):
    return math.hypot((xe - xs) * 1.05, (ye - ys) * 0.68)


def active(teams, scale: float = 1.0) -> dict | None:
    """team_id -> {motif: propensity} and ("player", team_id, role) -> {motif: propensity} for the
    teams of a match, keeping only propensities above zero; None when nothing is planted."""
    out = {}
    for t in teams:
        m = {k: v * scale for k, v in MOTIFS.get(t.code, {}).items() if v * scale > 0}
        if m:
            out[t.team_id] = m
            out[("side", t.team_id)] = {k: MOTIF_SIDES[(t.code, k)] for k in m if (t.code, k) in MOTIF_SIDES}
        for (code, role), pm in PLAYER_MOTIFS.items():
            if code == t.code:
                pm = {k: v * scale for k, v in pm.items() if v * scale > 0}
                if pm:
                    out[("player", t.team_id, role)] = pm
    return out or None


class Motifs:
    """Per-match motif state: the generators, the planted player ids and the log of instances."""

    def __init__(self, sim, config: dict, seed):
        self.sim, self.cfg, self.seed = sim, config, seed
        self._rngs: dict = {}
        self.log: Counter = Counter()          # (motif, team_id, player_id or "") -> completed instances
        self.started: Counter = Counter()
        self.players = {}                       # player_id -> (team_id, {motif: propensity})
        for key, pm in config.items():
            if isinstance(key, tuple) and key[0] == "player":
                _, tid, role = key
                slot = next((s for s in sim.on[tid] if s.role == role), None)
                if slot is not None:
                    self.players[slot.p.player_id] = (tid, pm)
        # a starved finisher sees less of the ball: his weight in pick() is scaled down
        self.usage = {pid: 0.15 for pid, (_, pm) in self.players.items() if "pat_starved_finisher" in pm}

    def rng(self, motif, tid):
        k = (motif, tid)
        if k not in self._rngs:
            self._rngs[k] = random.Random(f"{self.seed}:{motif}:{tid}")
        return self._rngs[k]

    def _p(self, tid, motif) -> float:
        return self.cfg.get(tid, {}).get(motif, 0.0)

    def _turnover(self, tid) -> bool:
        """The possession began with tid winning the ball in open play (its possession_change is the
        last event), so the other team has just lost it."""
        ev = self.sim.events
        return bool(ev) and ev[-1]["event_type"] == "possession_change" and ev[-1]["team_id"] == tid

    def _fire(self, tid, motif, mult=1.0) -> bool:
        p = self._p(tid, motif) * mult
        return p > 0 and self.rng(motif, tid).random() < MOTIF_RATES[motif] * p

    def _run(self, motif, tid, fn, *a):
        """Run a script with the simulator's generator swapped for the motif's own."""
        sim = self.sim
        saved = sim.rng
        sim.rng = self.rng(motif, tid)
        try:
            self.started[(motif, tid)] += 1
            return fn(*a)
        finally:
            sim.rng = saved

    def done(self, motif, tid, player_id=""):
        self.log[(motif, tid, player_id)] += 1

    # ---------- decision point 1: start of an open-play possession ----------

    def at_start(self, tid, x, y, holder, pattern, restart, idx):
        if restart is not None or idx:
            return None
        sim = self.sim
        o = sim.other(tid)
        lead = sim.score[tid] - sim.score[o]
        if x < 55 and pattern in ("open_play", "counter") and self._fire(tid, "pat_bait_switch", 0.5 if lead > 0 else 1.0):
            return self._run("pat_bait_switch", tid, self._bait_switch, tid, x, y, holder, idx)
        # the opponent's propensities act on this possession (o has just lost the ball)
        if o not in self.cfg or not self._turnover(tid):
            return None
        if x <= 33.0 and self._fire(o, "pat_counter_press", 0.6 if lead < 0 else 1.0):
            return self._run("pat_counter_press", o, self._counter_press, tid, o, x, y)
        if x < 50 and lead > 0 and self._fire(o, "pat_rest_defence"):
            return self._run("pat_rest_defence", o, self._counter_attack, tid, o, x, y, holder, idx)
        if 34.0 <= x <= 66.0 and self._fire(o, "pat_tactical_fouling"):
            return self._run("pat_tactical_fouling", o, self._foul_after_loss, tid, o, x, y, holder)
        return None

    # ---------- decision point 2: the pass choice ----------

    def in_play(self, tid, x, y, holder, pattern, last_pass, pressed, idx):
        sim = self.sim
        o = sim.other(tid)
        if x >= 72 and abs(y - 50) > 25 and self._fire(tid, "pat_cutback"):
            return self._run("pat_cutback", tid, self._cutback, tid, x, y, holder, pattern, idx)
        if 45 <= x <= 75 and (y < 15 or y > 85):
            strip_ok = self.cfg.get(("side", tid), {}).get("pat_flank_isolation") in (None, "left" if y < 15 else "right")
            if strip_ok and self._fire(tid, "pat_flank_isolation"):
                return self._run("pat_flank_isolation", tid, self._isolation, tid, x, y, holder, pattern, idx)
        if 68 <= x < 83 and abs(y - 50) < 25 and sim.score[o] > sim.score[tid] and self._fire(o, "pat_elastic_low_block"):
            return self._run("pat_elastic_low_block", o, self._range_shot, tid, o, x, y, holder, pattern, last_pass,
                             pressed, idx)
        return None

    # ---------- decision point 3: a shot the simulator has already decided to take ----------

    def at_shot(self, tid, x, y, holder, pattern, idx):
        """A starved finisher: the shot is re-routed to the planted forward (one pass into the box,
        his unpressured shot). It replaces a shot, so the team's shot volume is unchanged."""
        if x < 70:
            return None
        for pid, (ptid, pm) in self.players.items():
            if ptid == tid and pid != holder.player_id and any(s.p.player_id == pid for s in self.sim.on[tid]) \
                    and self._fire_player(pid, ptid, pm):
                return self._run("pat_starved_finisher", tid, self._feed, tid, pid, x, y, holder, pattern, idx)
        return None

    def shot_factor(self, tid) -> float:
        """Natural shot appetite left to a team while planted motifs add shots of their own, so its
        shot volume stays in the realistic range (SHOT_COMP in data_gen/config.py)."""
        sim = self.sim
        o = sim.other(tid)
        f = 1.0
        for motif in self.cfg.get(tid, {}):
            f *= SHOT_COMP.get(motif, 1.0) ** self._p(tid, motif)
        if self._p(o, "pat_rest_defence") and sim.score[o] < sim.score[tid]:
            f *= SHOT_COMP["opp:pat_rest_defence"] ** self._p(o, "pat_rest_defence")
        if self._p(o, "pat_tactical_fouling"):
            f *= SHOT_COMP["opp:pat_tactical_fouling"] ** self._p(o, "pat_tactical_fouling")
        if self._p(o, "pat_elastic_low_block") and sim.score[o] > sim.score[tid]:
            f *= SHOT_COMP["opp:pat_elastic_low_block"] ** self._p(o, "pat_elastic_low_block")
        return f

    def _fire_player(self, pid, tid, pm) -> bool:
        p = pm.get("pat_starved_finisher", 0.0)
        return p > 0 and self.rng("pat_starved_finisher", pid).random() < MOTIF_RATES["pat_starved_finisher"] * p

    # ---------- scripts ----------

    def _pass(self, tid, holder, x, y, xe, ye, ptype="short", pattern="open_play", idx=0, exclude=None, force_recv=None):
        """One completed pass with the simulator's own fields. Returns (eid, recv, xe, ye) or None when
        the receiver could not reach the point (the script then stops)."""
        sim = self.sim
        o = sim.teams[sim.other(tid)]
        if force_recv is not None:
            recv = force_recv
            xe, ye = sim.within_reach(tid, recv.player_id, xe, ye)
        else:
            recv, xe, ye = sim.pick(tid, xe, ye, x, exclude=holder, skip_gk=xe > 22)
        p_succ = sim.pass_success(tid, o, sim.deep(o.team_id), False, x, y, xe, ye, ptype == "long_ball", pattern)
        sim.tick(sim.teams[tid], 0.6 if pattern == "counter" else 1.0)
        sim.run_time(_dist_m(x, y, xe, ye) / 20)
        eid = sim.emit(tid, holder.player_id, "pass", x, y, xe, ye, pattern=pattern, idx=idx)
        sim.record_pass(eid, holder, recv, x, y, xe, ye, ptype, True, p_succ)
        return eid, recv, xe, ye

    def _bait_switch(self, tid, x, y, holder, idx):
        sim, r = self.sim, self.sim.rng
        left = r.random() < 0.75
        lo, hi = (6.0, 34.0) if left else (66.0, 94.0)
        n = r.randint(15, 18)
        last = None
        for _ in range(n):
            xe = _clip(x + r.uniform(-3.0, 4.5), 20.0, 62.0)
            ye = _clip(y + r.gauss(0, 7), lo, hi) if lo <= y <= hi else (lo + hi) / 2 + r.gauss(0, 4)
            if _dist_m(x, y, xe, ye) > 19.0:
                f = 19.0 / _dist_m(x, y, xe, ye)
                xe, ye = x + (xe - x) * f, y + (ye - y) * f
            eid, recv, xe2, ye2 = self._pass(tid, holder, x, y, xe, ye, idx=idx)
            idx += 1
            if _dist_m(x, y, xe2, ye2) > 20.0:
                return ("continue", xe2, ye2, recv, eid, idx, "open_play")
            x, y, holder, last = xe2, ye2, recv, eid
        # the switch: one long pass to the far side
        sx = _clip(x + r.uniform(4.0, 14.0), 30.0, 74.0)
        sy = r.uniform(80.0, 93.0) if left else r.uniform(7.0, 20.0)
        eid, recv, sx, sy = self._pass(tid, holder, x, y, sx, sy, ptype="long_ball", idx=idx)
        idx += 1
        far_ok = (sy >= 60 if left else sy < 40) and abs(sy - y) >= 40 and _dist_m(x, y, sx, sy) >= 25.0
        if not far_ok:
            return ("continue", sx, sy, recv, eid, idx, "open_play")
        # carry infield, then a pass into the box
        cx = _clip(sx + r.uniform(5.0, 10.0), 40.0, 82.0)
        cy = _clip(sy + (-1 if left else 1) * r.uniform(4.0, 10.0), 2.0, 98.0)
        sim.tick(sim.teams[tid], 0.5)
        sim.emit(tid, recv.player_id, "carry", sx, sy, cx, cy, idx=idx)
        bx, by = r.uniform(86.0, 93.0), r.uniform(36.0, 64.0)
        eid2, recv2, bx, by = self._pass(tid, recv, cx, cy, bx, by, idx=idx)
        idx += 1
        if bx >= BOX_X and BOX_Y[0] <= by <= BOX_Y[1]:
            self.done("pat_bait_switch", tid)
        return ("continue", bx, by, recv2, eid2, idx, "open_play")

    def _cutback(self, tid, x, y, holder, pattern, idx):
        sim, r = self.sim, self.sim.rng
        gx = r.uniform(94.5, 97.0)
        gy = r.uniform(8.0, 22.0) if y < 50 else r.uniform(78.0, 92.0)
        if gx - x <= 12:
            sim.tick(sim.teams[tid], 0.6)
            sim.emit(tid, holder.player_id, "carry", x, y, gx, gy, pattern=pattern, idx=idx)
            dl = holder
        else:
            _, dl, gx, gy = self._pass(tid, holder, x, y, gx, gy, pattern=pattern, idx=idx)
            idx += 1
        if not (gx >= 94 and (gy <= 25 or gy >= 75)):
            return ("continue", gx, gy, dl, None, idx, pattern)
        ax, ay = r.uniform(84.0, 90.0), r.uniform(42.0, 58.0)
        eid, recv, ax, ay = self._pass(tid, dl, gx, gy, ax, ay, pattern=pattern, idx=idx)
        idx += 1
        if not (82 <= ax <= 92 and 38 <= ay <= 62 and ax <= gx - 5):
            return ("continue", ax, ay, recv, eid, idx, pattern)
        sim.tick(sim.teams[tid], 0.4)
        res = sim.take_shot(tid, recv, ax, ay, False, pattern, eid, False, idx)
        self.done("pat_cutback", tid)
        return ("return", sim.after_shot(tid, res, ax, ay))

    def _isolation(self, tid, x, y, holder, pattern, idx):
        r = self.sim.rng
        left = y < 15
        n = r.randint(10, 13)
        inside = 0
        last = None
        for k in range(n):
            xe = _clip(x + r.uniform(-2.0, 4.0), 40.0, 86.0)
            ye = r.uniform(3.0, 13.0) if left else r.uniform(87.0, 97.0)
            eid, recv, xe, ye = self._pass(tid, holder, x, y, xe, ye, pattern=pattern, idx=idx)
            idx += 1
            if k < 10 and ((y < 15 and ye < 15) if left else (y > 85 and ye > 85)):
                inside += 1
            x, y, holder, last = xe, ye, recv, eid
        if inside >= 8:
            self.done("pat_flank_isolation", tid)
        return ("continue", x, y, holder, last, idx, pattern)

    def _feed(self, tid, pid, x, y, holder, pattern, idx):
        sim, r = self.sim, self.sim.rng
        striker = next(s.p for s in sim.on[tid] if s.p.player_id == pid)
        bx, by = r.uniform(87.0, 93.0), r.uniform(40.0, 60.0)
        eid, recv, bx, by = self._pass(tid, holder, x, y, bx, by, pattern=pattern, idx=idx, force_recv=striker)
        res = sim.take_shot(tid, striker, bx, by, False, pattern, eid, False, idx + 1)
        self.done("pat_starved_finisher", tid, pid)
        return ("return", sim.after_shot(tid, res, bx, by))

    def _range_shot(self, tid, o, x, y, holder, pattern, last_pass, pressed, idx):
        sim = self.sim
        sim.tick(sim.teams[tid], 0.4)
        res = sim.take_shot(tid, holder, x, y, False, pattern, last_pass, pressed, idx)
        self.done("pat_elastic_low_block", o)
        return ("return", sim.after_shot(tid, res, x, y))

    def _counter_press(self, tid, o, x, y):
        sim, r = self.sim, self.sim.rng
        ok = 0
        d = dx = dy = None
        for _ in range(2):
            sim.run_time(r.uniform(0.6, 1.1))
            d, dx, dy = sim.pick(o, 100 - x, 100 - y, 100 - x, scale=12, usage=False)
            sim.emit(o, d.player_id, "pressure", dx, dy, outcome="applied", idx=0)
            ok += dx >= 66.7
        sim.run_time(r.uniform(0.3, 0.8))
        sim.emit(o, d.player_id, "tackle", dx, dy, outcome="success", idx=0)
        if ok == 2:
            self.done("pat_counter_press", o)
        return ("return", sim._won(o, d, dx, dy))

    def _counter_attack(self, tid, o, x, y, holder, idx):
        sim, r = self.sim, self.sim.rng
        fx, fy = r.uniform(72.0, 82.0), _clip(50 + r.gauss(0, 10), 30, 70)
        eid, recv, fx, fy = self._pass(tid, holder, x, y, fx, fy, ptype="through_ball", pattern="counter", idx=idx)
        cx, cy = r.uniform(84.0, 90.0), _clip(fy + r.gauss(0, 5), 32, 68)
        sim.tick(sim.teams[tid], 0.5)
        sim.emit(tid, recv.player_id, "carry", fx, fy, cx, cy, pattern="counter", idx=idx + 1)
        sim.tick(sim.teams[tid], 0.4)
        res = sim.take_shot(tid, recv, cx, cy, False, "counter", eid, False, idx + 2)
        self.done("pat_rest_defence", o)
        return ("return", sim.after_shot(tid, res, cx, cy))

    def _foul_after_loss(self, tid, o, x, y, holder):
        sim, r = self.sim, self.sim.rng
        sim.run_time(r.uniform(1.0, 3.0))
        d, dx, dy = sim.pick(o, 100 - x, 100 - y, 100 - x, scale=12, usage=False)
        self.done("pat_tactical_fouling", o)
        return ("return", sim.foul(o, d, dx, dy, holder, x, y))
