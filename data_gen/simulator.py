"""Match simulator: possession sequences driven by each team's hidden style seed.

Traps are NOT patched in afterwards. They emerge from behaviour rules:
  * a team that leads drops deep on a share of its possessions set by `sit_deep`, cedes the final
    third and counters; a trailing team pushes harder as time runs out;
  * the chasing team circulates around the block and, if it has `shot_spam`, shoots from range;
  * a `wide_forward` player sends forward passes to his flank and rarely crosses;
  * a set-piece taker delivers every corner, so his "chances created" come from dead balls.

Coordinates: every event is in the acting team's attacking frame (see config.py).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .config import (FINAL_THIRD_X, FIRST, FORMATION, LANE_CENTERS, LANES, LAST,
                     PITCH_LEN_M, PITCH_WID_M, TEAM_BY_ID, TeamSpec, in_box, lane_of)

MATCH_SECONDS = 5400
HALF_SECONDS = 2700
# Behaviour parameters tuned against data_gen/calibration.py (season-level targets).
HOME_EDGE = 0.03         # added to the home side's `att` (crowd, familiarity): more completed passes
HOME_CHANCES = 1.08      # home side's chance-creation multiplier on top of attacking_output
CHASE_URGENCY = 0.8      # trailing side: extra shot appetite and box-entry success, ramps up late
SHOT_RATE_BOX = 0.066    # per-action chance of shooting from inside the box (others scale with it)
BLOCK_BOX = 0.45         # how much a deep block (x its sit_deep) cuts box-entry pass success


@dataclass
class Player:
    player_id: str
    team_id: str
    name: str
    shirt: int
    position: str
    role: str
    hx: float
    hy: float
    finishing: float = 1.0
    usage: float = 1.0
    cross_mult: float = 1.0
    wide_forward: bool = False
    set_piece_taker: bool = False
    trap_flag: str = ""


def build_players(rng: random.Random, team: TeamSpec, overrides: dict | None = None) -> list[Player]:
    """Eleven players for `team`. `overrides` (keyed like PLAYER_TRAITS) is applied last."""
    from .config import PLAYER_TRAITS
    used = set()
    out = []
    for pos, role, hx, hy, shirt in FORMATION:
        while True:
            nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            if nm not in used:
                used.add(nm)
                break
        p = Player(f"{team.code}_{shirt:02d}", team.team_id, nm, shirt, pos, role, hx, hy)
        traits = {**PLAYER_TRAITS.get((team.code, role), {}), **(overrides or {}).get((team.code, role), {})}
        for k, v in traits.items():
            setattr(p, k, v)
        out.append(p)
    return out


def goal_geometry(x: float, y: float) -> tuple[float, float]:
    """Distance (m) and visible goal angle (rad) from pitch point (x, y) in the 0-100 frame."""
    dx = max((100 - x) * PITCH_LEN_M / 100, 0.5)
    dy = (y - 50) * PITCH_WID_M / 100
    dist = math.hypot(dx, dy)
    angle = math.atan2(7.32 * dx, dx * dx + dy * dy - 3.66 ** 2)
    if angle < 0:
        angle += math.pi
    return dist, angle


def xg_model(x: float, y: float, header: bool, set_piece: bool) -> tuple[float, float, float]:
    dist, angle = goal_geometry(x, y)
    logit = 0.22 - 0.15 * dist + 0.67 * angle
    if header:
        logit -= 1.9
    if set_piece and not header:
        logit -= 0.3
    return dist, angle, 1 / (1 + math.exp(-logit))


class MatchSim:
    def __init__(self, rng: random.Random, match_id: str, home: TeamSpec, away: TeamSpec,
                 players: dict[str, list[Player]], force_goal: dict | None = None):
        self.rng, self.mid = rng, match_id
        self.teams = {home.team_id: home, away.team_id: away}
        self.home_id, self.away_id = home.team_id, away.team_id
        self.players = players
        self.score = {home.team_id: 0, away.team_id: 0}
        self.xg = {home.team_id: 0.0, away.team_id: 0.0}
        self.clock = 0.0
        self.events: list[dict] = []
        self.passes: dict[str, dict] = {}
        self.shots: list[dict] = []
        self.poss_id = 0
        self.seq_id = 0
        self.force_goal = dict(force_goal) if force_goal else None

    # ---------- helpers ----------
    def other(self, tid: str) -> str:
        return self.away_id if tid == self.home_id else self.home_id

    def att(self, tid: str) -> float:
        """Attacking strength used for pass/cross success: team `att` plus the home edge."""
        return self.teams[tid].att + (HOME_EDGE if tid == self.home_id else 0.0)

    def urgency(self, tid: str) -> float:
        """Game-state multiplier on shot appetite and box-entry success: a trailing side commits
        more as time runs out."""
        if self.score[tid] >= self.score[self.other(tid)]:
            return 1.0
        return 1.0 + CHASE_URGENCY * self.clock / MATCH_SECONDS

    def deep(self, tid: str) -> float:
        """How deep `tid` sits right now: only once it leads, and not in the first 10 minutes."""
        lead = self.score[tid] - self.score[self.other(tid)]
        return self.teams[tid].sit_deep if (lead >= 1 and self.clock >= 600) else 0.0

    def pick(self, tid: str, x: float, y: float, exclude: Player | None = None,
             skip_gk: bool = True, scale: float = 18.0) -> Player:
        cands, w = [], []
        for p in self.players[tid]:
            if p is exclude or (skip_gk and p.role == "goalkeeper"):
                continue
            d = math.hypot((p.hx - x) * 1.05, (p.hy - y) * 0.68)
            cands.append(p)
            w.append(math.exp(-d / scale) * p.usage)
        return self.rng.choices(cands, w)[0]

    def emit(self, tid, player_id, etype, xs, ys, xe=None, ye=None, outcome="success",
             body="foot", pattern="open_play", pressed=False, seq=None, idx=None) -> str:
        eid = f"{self.mid}_e{len(self.events) + 1:05d}"
        c = int(self.clock)
        self.events.append(dict(
            event_id=eid, match_id=self.mid, period=1 if c < HALF_SECONDS else 2,
            minute=c // 60, second=c % 60, clock_sec=c, team_id=tid, player_id=player_id,
            opponent_team_id=self.other(tid), event_type=etype,
            x_start=round(xs, 1), y_start=round(ys, 1),
            x_end=None if xe is None else round(xe, 1), y_end=None if ye is None else round(ye, 1),
            outcome=outcome, body_part=body, play_pattern=pattern, under_pressure=int(pressed),
            possession_id=self.poss_id, sequence_id=self.seq_id, sequence_index=idx,
            score_home=self.score[self.home_id], score_away=self.score[self.away_id]))
        return eid

    def tick(self, team: TeamSpec, factor: float = 1.0):
        self.clock += team.tempo * self.rng.uniform(0.7, 1.35) * factor

    # ---------- shots ----------
    def shot_prob(self, tid: str, x, y, opp_deep) -> float:
        """Chance of shooting from (x, y). Volume scales with `attacking_output`, the home side's
        chance edge and game state; it never depends on how deep the shooting team itself sits."""
        t = self.teams[tid]
        if x < 62:
            return 0.0
        if in_box(x, y):
            p = SHOT_RATE_BOX
        elif x >= 72:
            p = SHOT_RATE_BOX * 0.22
        else:
            p = SHOT_RATE_BOX * 0.067
        if not in_box(x, y):
            spam = 1 + 4 * t.shot_spam * (1.0 if opp_deep > 0 else 0.15)
            p *= spam
        if abs(y - 50) > 25:
            p *= 0.5
        p *= t.attacking_output * self.urgency(tid) * (HOME_CHANCES if tid == self.home_id else 1.0)
        return min(p, 0.45)

    def take_shot(self, tid, shooter: Player, x, y, header, pattern, assist_eid, pressed, seq_idx):
        o_id = self.other(tid)
        rng = self.rng
        dist, angle, xg = xg_model(x, y, header, pattern == "set_piece")
        odds = xg / (1 - xg) * shooter.finishing
        p_goal = odds / (1 + odds)
        opp_deep = self.deep(o_id)
        block_p = 0.16 + 0.26 * opp_deep + 0.003 * dist
        forced = (self.force_goal and tid == self.force_goal["team_id"]
                  and self.clock >= self.force_goal["after_sec"] and xg >= 0.08)
        if forced:
            result = "goal"
            self.force_goal = None
        elif rng.random() < p_goal:
            result = "goal"
        else:
            u = rng.random()
            if u < block_p:
                result = "blocked"
            elif u < block_p + 0.28 + 0.5 * xg:
                result = "saved"
            else:
                result = "off_target"
        speed = max(40.0, min(135.0, rng.gauss(102 - 0.6 * (dist - 15), 8) - (28 if header else 0)))
        eid = self.emit(tid, shooter.player_id, "shot", x, y, outcome=result,
                        body="head" if header else "foot", pattern=pattern, pressed=pressed,
                        seq=self.seq_id, idx=seq_idx)
        self.shots.append(dict(
            event_id=eid, match_id=self.mid, team_id=tid, player_id=shooter.player_id,
            shot_distance_m=round(dist, 1), shot_angle_rad=round(angle, 3),
            shot_type="header" if header else ("set_piece" if pattern == "set_piece" else "open_play"),
            assist_event_id=assist_eid or "", is_big_chance=int(xg >= 0.3),
            shot_result=result, xg=round(xg, 4), shot_speed_kmh=round(speed, 1)))
        self.xg[tid] += xg
        if assist_eid and assist_eid in self.passes:
            self.passes[assist_eid]["is_key_pass"] = 1
            self.passes[assist_eid]["xa"] = round(xg, 4)
        return result

    # ---------- possession handover ----------
    def turnover(self, gaining: str, ball_x_att_frame, ball_y_att_frame, winner_action, pressed):
        """Ball lost by the other team at (x, y) in ITS frame. Emits the winning action and the
        possession_change, returns the next possession dict in the gaining team's frame."""
        g = self.teams[gaining]
        gx, gy = 100 - ball_x_att_frame, 100 - ball_y_att_frame
        winner = self.pick(gaining, gx, gy, skip_gk=False, scale=14)
        self.poss_id += 1
        self.emit(gaining, winner.player_id, winner_action, gx, gy, pressed=False,
                  seq=self.seq_id, idx=None)
        self.emit(gaining, winner.player_id, "possession_change", gx, gy,
                  seq=self.seq_id, idx=None)
        pattern = "counter" if (gx < 55 and self.rng.random() < g.counter) else "open_play"
        return dict(team=gaining, x=gx, y=gy, pattern=pattern, holder=winner)

    # ---------- passes ----------
    def record_pass(self, eid, passer: Player, recv: Player | None, xs, ys, xe, ye, ptype,
                    ok, p_succ):
        dm = math.hypot((xe - xs) * PITCH_LEN_M / 100, (ye - ys) * PITCH_WID_M / 100)
        speed = max(18.0, min(95.0, self.rng.gauss(52 if ptype != "cross" else 62, 9)))
        self.passes[eid] = dict(
            event_id=eid, match_id=self.mid, passer_id=passer.player_id,
            recipient_player_id=recv.player_id if (recv and ok) else "",
            pass_distance_m=round(dm, 1),
            pass_angle_rad=round(math.atan2((ye - ys) * PITCH_WID_M / 100,
                                            (xe - xs) * PITCH_LEN_M / 100), 3),
            pass_type=ptype, pass_difficulty=round(1 - p_succ, 3), ball_speed_kmh=round(speed, 1),
            is_forward=int(xe - xs >= 8), is_progressive=int(xe - xs >= 10),
            is_key_pass=0, xa=0.0)

    def pass_success(self, tid, o, opp_deep, pressed, xs, ys, xe, ye, clearance=False, pattern="open_play"):
        dm = math.hypot((xe - xs) * PITCH_LEN_M / 100, (ye - ys) * PITCH_WID_M / 100)
        p = 0.96 - 0.006 * dm
        if clearance:
            p = 0.45
        if pattern == "counter":
            p -= 0.12
        if pressed:
            p -= 0.10
        p += 0.18 * (self.att(tid) - o.dfn)
        lane = lane_of(ye)
        if o.weak_lane and lane == o.weak_lane:
            p += 0.06 + (0.03 if xe >= FINAL_THIRD_X else 0)
        if in_box(xe, ye):
            p *= (1 - BLOCK_BOX * opp_deep) * self.urgency(tid) * self.teams[tid].attacking_output
        elif opp_deep > 0 and not pressed and xe >= FINAL_THIRD_X:
            p += 0.04
        return max(0.30, min(0.97, p))

    # ---------- one possession sequence ----------
    def run_sequence(self, st: dict) -> dict:
        rng = self.rng
        tid = st["team"]
        t, o_id = self.teams[tid], self.other(tid)
        o = self.teams[o_id]
        x, y, holder, pattern = st["x"], st["y"], st["holder"], st["pattern"]
        self.seq_id += 1
        if st["pattern"] != "kickoff":
            pass
        idx = 0
        n_steps = 0
        # A leader protects its lead on a share of its possessions set by `sit_deep`; on the rest it
        # plays normally.
        protect = rng.random() < self.deep(tid)
        while self.clock < MATCH_SECONDS and n_steps < 90:
            n_steps += 1
            opp_deep = self.deep(o_id)
            pressed = rng.random() < 0.6 * o.press * (1 - opp_deep) * (0.25 + 0.75 * (1 - x / 100))
            if pressed:
                d = self.pick(o_id, 100 - x, 100 - y, skip_gk=True, scale=14)
                self.emit(o_id, d.player_id, "pressure", 100 - x, 100 - y, outcome="applied",
                          seq=self.seq_id, idx=idx)
            # shot?
            if rng.random() < self.shot_prob(tid, x, y, opp_deep):
                self.tick(t, 0.5)
                res = self.take_shot(tid, holder, x, y, False, pattern, st.get("last_pass"),
                                     pressed, idx)
                return self.after_shot(tid, res, x, y)
            # choose action
            in_final = x >= FINAL_THIRD_X
            wide = abs(y - 50) > 30
            ptype, clearance = "short", False
            if pattern == "counter" and idx < 2:
                mode = "forward"; dx_lo, dx_hi = 14, 26; ptype = "long_ball" if x < 50 else "through_ball"
            elif protect and n_steps >= 4 and in_final:
                mode = "waste"           # leader runs the clock, gives the ball back
            elif protect and n_steps >= 4:
                mode = "forward"; dx_lo, dx_hi = 28, 45; clearance = True; ptype = "long_ball"
            elif in_final and wide and rng.random() < 0.22 * holder.cross_mult:
                mode = "cross"; dx_lo = dx_hi = 0
            else:
                fwd_p = t.directness * (1.25 if pressed else 1.0)
                if in_final and opp_deep > 0:
                    fwd_p *= (1 - 0.85 * opp_deep)
                if holder.wide_forward:
                    fwd_p = max(fwd_p, 0.8)      # the volume passer always plays it forward
                if protect:
                    fwd_p = max(fwd_p, 0.7)
                if opp_deep > 0.5 and 45 <= x < FINAL_THIRD_X:
                    fwd_p = max(fwd_p, 0.6)      # chasing a low block: push up
                back_p = 0.10 + (0.06 if pressed else 0)
                r = rng.random()
                mode = "forward" if r < fwd_p else ("back" if r < fwd_p + back_p * (1 - fwd_p) else "lateral")
                dx_lo, dx_hi = (7, 20)
            # destination
            if mode == "forward":
                xe = min(x + rng.uniform(dx_lo, dx_hi), 94.0)
                if holder.wide_forward and rng.random() < 0.9:
                    lane_i = 0 if holder.hy < 50 else 4
                else:
                    lane_i = rng.choices(range(5), t.lane_weights)[0]
                ye = max(2.0, min(98.0, LANE_CENTERS[lane_i] + rng.gauss(0, 6)))
                if holder.wide_forward:
                    xe = min(xe, 80.0)       # his forward balls go into the channel, not the box
            elif mode == "cross":
                xe, ye = rng.uniform(88, 94), 50 + rng.gauss(0, 9)
                ptype = "cross"
            elif mode == "waste":
                xe = max(3.0, min(94.0, x + rng.uniform(-3, 3))); ye = max(2.0, min(98.0, y + rng.gauss(0, 10)))
            elif mode == "back":
                xe = max(3.0, x - rng.uniform(5, 15)); ye = max(2.0, min(98.0, y + rng.gauss(0, 15)))
                ptype = "short"
            else:
                xe = max(3.0, min(98.0, x + rng.uniform(-2, 3)))
                ye = max(2.0, min(98.0, y + rng.gauss(0, 28)))
                if in_final and opp_deep > 0:
                    xe = min(xe, 82.0)
            recv = self.pick(tid, xe, ye, exclude=holder)
            p_succ = self.pass_success(tid, o, opp_deep, pressed, x, y, xe, ye, clearance, pattern)
            if mode == "waste":
                p_succ = 0.30
            if mode == "cross":
                p_succ = 0.28 + 0.10 * (o.weak_lane == lane_of(y)) + 0.18 * (self.att(tid) - o.dfn)
                p_succ *= (1 - 0.4 * opp_deep)
            self.tick(t, 0.6 if pattern == "counter" else 1.0)
            ok = rng.random() < p_succ
            eid = self.emit(tid, holder.player_id, "pass", x, y, xe, ye,
                            outcome="success" if ok else "fail", pattern=pattern,
                            pressed=pressed, seq=self.seq_id, idx=idx)
            self.record_pass(eid, holder, recv, x, y, xe, ye, ptype, ok, p_succ)
            idx += 1
            if ok:
                if mode == "cross" and rng.random() < 0.6:
                    self.tick(t, 0.4)
                    res = self.take_shot(tid, recv, xe, ye, True, pattern, eid, False, idx)
                    return self.after_shot(tid, res, xe, ye)
                x, y, holder = xe, ye, recv
                st["last_pass"] = eid
                pattern = "open_play" if pattern in ("kickoff",) else pattern
                if idx >= 3 and pattern == "counter":
                    pattern = "open_play"
                continue
            # failed pass
            st["last_pass"] = None
            if in_box(xe, ye) or mode == "cross":
                if rng.random() < (0.22 if mode == "cross" else 0.07):
                    return self.corner(tid)
            action = "tackle" if pressed and rng.random() < 0.6 else "interception"
            return self.turnover(o_id, xe, ye, action, pressed)
        # clock ran out
        return dict(team=o_id, x=50, y=50, pattern="open_play", holder=self.pick(o_id, 50, 50))

    def after_shot(self, tid, result, x, y) -> dict:
        o_id = self.other(tid)
        rng = self.rng
        if result == "goal":
            self.score[tid] += 1
            self.clock += 25
            return dict(team=o_id, x=50, y=50, pattern="kickoff", holder=self.pick(o_id, 50, 50))
        if result == "blocked":
            if rng.random() < (0.28 + 0.2 * self.deep(o_id)):
                return self.corner(tid)
            return self.turnover(o_id, x, y, "ball_recovery", False)
        if result == "saved":
            if rng.random() < 0.10:
                return self.corner(tid)
            self.clock += 4
            gk = next(p for p in self.players[o_id] if p.role == "goalkeeper")
            self.poss_id += 1
            self.emit(o_id, gk.player_id, "ball_recovery", 6, 50, seq=self.seq_id)
            self.emit(o_id, gk.player_id, "possession_change", 6, 50, seq=self.seq_id)
            return dict(team=o_id, x=6, y=50, pattern="open_play", holder=gk)
        # off target: goal kick
        self.clock += 10
        gk = next(p for p in self.players[o_id] if p.role == "goalkeeper")
        self.poss_id += 1
        self.emit(o_id, gk.player_id, "possession_change", 6, 50, pattern="set_piece", seq=self.seq_id)
        return dict(team=o_id, x=6, y=50, pattern="open_play", holder=gk)

    def corner(self, tid) -> dict:
        rng = self.rng
        t, o_id = self.teams[tid], self.other(tid)
        self.clock += 12
        self.poss_id += 1
        self.seq_id += 1
        taker = next((p for p in self.players[tid] if p.set_piece_taker), None) or \
            rng.choice([p for p in self.players[tid] if p.role in ("left_winger", "right_winger")])
        ys = 0.0 if rng.random() < 0.5 else 100.0
        xe, ye = rng.uniform(90, 95), 50 + rng.gauss(0, 8)
        recv = self.pick(tid, xe, ye, exclude=taker)
        p_succ = 0.42 + 0.15 * (taker.set_piece_taker) + 0.1 * (self.att(tid) - self.teams[o_id].dfn)
        ok = rng.random() < p_succ
        eid = self.emit(tid, taker.player_id, "pass", 100, ys, xe, ye,
                        outcome="success" if ok else "fail", pattern="set_piece", seq=self.seq_id, idx=0)
        self.record_pass(eid, taker, recv, 100, ys, xe, ye, "corner", ok, p_succ)
        if ok and rng.random() < 0.65:
            self.tick(t, 0.3)
            res = self.take_shot(tid, recv, xe, ye, True, "set_piece", eid, False, 1)
            return self.after_shot(tid, res, xe, ye)
        return self.turnover(o_id, xe, ye, "ball_recovery", False)

    # ---------- whole match ----------
    def run(self) -> None:
        st = dict(team=self.home_id, x=50.0, y=50.0, pattern="kickoff",
                  holder=self.pick(self.home_id, 50, 50))
        self.poss_id = 1
        second_half_started = False
        while self.clock < MATCH_SECONDS:
            if not second_half_started and self.clock >= HALF_SECONDS:
                second_half_started = True
                self.poss_id += 1
                st = dict(team=self.away_id, x=50.0, y=50.0, pattern="kickoff",
                          holder=self.pick(self.away_id, 50, 50))
            st = self.run_sequence(st)
