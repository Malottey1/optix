"""Match simulator (realism v2): possession sequences driven by each team's hidden style seed.

Traps are NOT patched in afterwards. They emerge from behaviour rules:
  * a team that leads drops deep on a share of its possessions set by `sit_deep`, cedes the final
    third and counters; a trailing team pushes harder as time runs out;
  * the chasing team circulates around the block and, if it has `shot_spam`, shoots from range;
  * a `wide_forward` player sends forward passes to his flank and rarely crosses;
  * a set-piece taker delivers every corner, so his "chances created" come from dead balls.

On top of those, v2 models the rest of a football match: carries and take-ons, a failed pass that
can be intercepted, blocked, lost in an aerial duel, cleared, recovered loose or go out of play
(throw-in, goal kick, corner); tackles, fouls, free kicks, penalties, cards (second yellows and
straight reds, with a 10-man side sitting deeper), offsides, goalkeeper saves and claims,
substitutions, injuries, stoppage time and a ball-in-play clock.

Clock: `clock_sec` is elapsed playing time and never goes backwards; the second half starts where
the first half ended (45:00 plus its added time). `minute`/`second` follow the football
convention: first-half added time is minute 45, 46, ...; the second half starts at minute 45.

Coordinates: every event is in the acting team's attacking frame (see config.py). Players have a
home position in a formation that shifts with the ball, and nobody is picked for an event that he
could not have reached since his previous one (the teleport guard).
"""
from __future__ import annotations

import math
import random

from .config import (FINAL_THIRD_X, LANE_CENTERS, LANES, PITCH_LEN_M, PITCH_WID_M, TeamSpec, in_box, lane_of)
from .motifs import Motifs
from .squads import FORMATIONS, Lineup, Player, build_squad, name_pool

HALF_SECONDS = 2700
MATCH_SECONDS = 5400             # regulation time; stoppage time comes on top

# ---- behaviour parameters, tuned against data_gen/calibration.py (season-level targets) ----
HOME_EDGE = 0.03          # added to the home side's `att` (crowd, familiarity): more completed passes
HOME_CHANCES = 1.24       # home side's chance-creation multiplier on top of attacking_output
CHASE_URGENCY = 0.5       # trailing side: extra shot appetite and box-entry success, ramps up late
SHOT_RATE_BOX = 0.14      # per-action chance of shooting from inside the box (others scale with it)
BLOCK_BOX = 0.65          # how much a deep block (x its sit_deep) cuts box-entry pass success
DFN_SHOTS = 2.0           # exponent: a strong defence (dfn > 1) cuts the opponent's shot volume
TEMPO_SCALE = 0.45        # team `tempo` is "seconds per action" in the style seed; v2 has more actions
PRESS_RATE = 0.62         # pressure events per opponent action, times the team's `press`
TACKLE_RATE = 0.16        # chance a pressed holder is challenged (tackle attempt)
TACKLE_WIN = 0.62         # chance a challenge wins the ball (before strength)
FOUL_RATE = 0.30          # chance a challenge is a foul (times the defender's aggression)
LOOSE_FOUL = 0.020        # extra foul chance per unpressed action (shirt pulls, late challenges)
BOX_FOUL = 0.0040         # chance per action in the box that the holder is fouled (a penalty)
YELLOW_P = 0.195          # chance a foul is booked
RED_P = 0.0018            # chance a foul is a straight red
DRIBBLE_RATE = 0.018      # chance per action of a take-on (wide forwards and the final third more)
CARRY_P = 0.42            # chance the receiver carries the ball before his next action
CROSS_RATE = 0.42         # per action in wide final-third areas, times the player's cross_mult
OFFSIDE_P = 0.025         # forward passes behind the line that are flagged
INJURY_P = 0.0012         # per action, a player goes down injured (forced sub)
DEAD = dict(throw_in=(9, 18), goal_kick=(18, 30), corner=(25, 38), free_kick=(18, 32), penalty=(60, 90),
            goal=(55, 80), offside=(16, 28), card=(15, 30), sub=(20, 35), injury=(45, 110), kickoff=(4, 8))
KX, KY = 0.45, 0.25       # how far a player's home position follows the ball
TARGET_WEAK = 0.25        # opponents aim more forward balls at a known soft side (per unit weak_strength)
WEAK_CREATE = 0.35        # shot appetite after getting in behind a soft side (per unit weak_strength)
RETENTION = 0.14          # pass security of patient (low-directness) sides vs direct ones
MAX_SPEED = 8.0           # teleport guard: a player covers at most 6 m + 8 m/s since his last event

ROLE_FREE_KICK = ("central_mid_r", "attacking_mid", "central_mid_l", "defensive_mid_r", "defensive_mid")


def build_players(rng: random.Random, team: TeamSpec, overrides: dict | None = None, names=None) -> list[Player]:
    """The squad of `team` (see squads.build_squad). `overrides` is keyed like PLAYER_TRAITS."""
    return build_squad(rng, team, names or name_pool(rng), overrides)


def default_lineup(team: TeamSpec, squad: list[Player]) -> Lineup:
    """First-choice XI in formation order and the next nine on the bench."""
    xi = []
    for role, hx, hy, _ in FORMATIONS[team.formation]:
        xi.append((next(p for p in squad if p.first_choice and p.role == role), role, hx, hy))
    used = {p.player_id for p, *_ in xi}
    rest = [p for p in squad if p.player_id not in used]
    gk = [p for p in rest if p.position == "GK"][:1]
    return Lineup(xi, gk + [p for p in rest if p.position != "GK"][:8])


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
    logit = 0.05 - 0.15 * dist + 0.67 * angle
    if header:
        logit -= 1.6
    if set_piece and not header:
        logit -= 0.3
    return dist, angle, 1 / (1 + math.exp(-logit))


PENALTY_XG = 0.78


def _clip(v, lo=0.5, hi=99.5):
    return lo if v < lo else hi if v > hi else v


class _Slot:
    __slots__ = ("p", "role", "hx", "hy")

    def __init__(self, p, role, hx, hy):
        self.p, self.role, self.hx, self.hy = p, role, hx, hy


class MatchSim:
    def __init__(self, rng: random.Random, match_id: str, home: TeamSpec, away: TeamSpec,
                 players: dict, force_goal: dict | None = None, motifs: dict | None = None, motif_seed=None):
        """`players`: team_id -> Lineup, or -> squad list (the first-choice XI then plays).
        `motifs`: planted motif propensities (data_gen/motifs.active), None = nothing planted;
        `motif_seed`: the match seed the motif generators derive from."""
        self.rng, self.mid = rng, match_id
        self.teams = {home.team_id: home, away.team_id: away}
        self.home_id, self.away_id = home.team_id, away.team_id
        self.lineups = {tid: (v if isinstance(v, Lineup) else default_lineup(self.teams[tid], v))
                        for tid, v in players.items() if tid in self.teams}
        self.on = {tid: [_Slot(*s) for s in lu.xi] for tid, lu in self.lineups.items()}
        self.bench = {tid: list(lu.bench) for tid, lu in self.lineups.items()}
        self.score = {home.team_id: 0, away.team_id: 0}
        self.xg = {home.team_id: 0.0, away.team_id: 0.0}
        self.men = {home.team_id: 11, away.team_id: 11}
        self.clock = 0.0
        self.bip = 0.0
        self.period = 1
        self.h_start = 0.0
        self.end_at = HALF_SECONDS + 600.0     # replaced by the announced added time at 45:00
        self.announced = False
        self.stoppage = dict(goals=0, subs=0, cards=0, injuries=0)
        self.events: list[dict] = []
        self.passes: dict[str, dict] = {}
        self.shots: list[dict] = []
        self.poss_id = 1
        self.seq_id = 0
        self.poss_team = home.team_id
        self.force_goal = dict(force_goal) if force_goal else None
        self.last = {}                          # player_id -> (clock, abs x, abs y)
        self.yellows = {}
        self.cards: list[tuple] = []            # (player_id, kind)
        self.injured: list[tuple] = []          # (player_id, matches out)
        self.minutes = {}                       # player_id -> [team_id, on_sec, off_sec, sent_off, starter]
        for tid, slots in self.on.items():
            for s in slots:
                self.minutes[s.p.player_id] = [tid, 0, None, 0, 1]
        self.subs_left = {tid: 5 for tid in self.teams}
        self.windows_left = {tid: 3 for tid in self.teams}
        self.sub_plan = {tid: self._plan_subs(tid) for tid in self.teams}
        self.form = {tid: rng.lognormvariate(0, 0.32) for tid in self.teams}
        self.motifs = Motifs(self, motifs, match_id if motif_seed is None else motif_seed) if motifs else None
        self.usage_mult = self.motifs.usage if self.motifs else {}

    # ---------- helpers ----------
    def other(self, tid: str) -> str:
        return self.away_id if tid == self.home_id else self.home_id

    def att(self, tid: str) -> float:
        """Attacking strength used for pass/cross success: team `att`, home edge, numbers."""
        a = self.teams[tid].att + (HOME_EDGE if tid == self.home_id else 0.0)
        return a + 0.04 * (self.men[tid] - self.men[self.other(tid)])

    def elapsed(self) -> float:
        """Regulation seconds played (0-5400), for game-state ramps."""
        return min(self.clock - self.h_start, HALF_SECONDS) + (HALF_SECONDS if self.period == 2 else 0)

    def urgency(self, tid: str) -> float:
        """Game-state multiplier on shot appetite and box-entry success: a trailing side commits
        more as time runs out."""
        if self.score[tid] >= self.score[self.other(tid)]:
            return 1.0
        return 1.0 + CHASE_URGENCY * self.elapsed() / MATCH_SECONDS

    def deep(self, tid: str) -> float:
        """How deep `tid` sits right now: once it leads (not in the first 10 minutes), and when
        it is a man down."""
        lead = self.score[tid] - self.score[self.other(tid)]
        d = self.teams[tid].sit_deep if (lead >= 1 and self.elapsed() >= 600) else 0.0
        if self.men[tid] < self.men[self.other(tid)]:
            d = max(d, 0.45)
        return d

    def intensity(self) -> float:
        """Chance creation rises through each half (tiring legs, more space late on)."""
        frac = min((self.clock - self.h_start) / HALF_SECONDS, 1.1)
        return 0.82 + 0.36 * frac

    def absxy(self, tid, x, y):
        return (x, y) if tid == self.home_id else (100 - x, 100 - y)

    def gk(self, tid) -> Player:
        return next((s.p for s in self.on[tid] if s.role == "goalkeeper"), self.on[tid][0].p)

    def pick(self, tid: str, x: float, y: float, bx: float, exclude: Player | None = None,
             skip_gk: bool = True, scale: float = 16.0, usage: bool = True):
        """A player of `tid` to act at (x, y) (tid's frame) while the ball is at bx (tid's frame).
        Weighted by distance from his ball-shifted home position (and usage). Players who could not
        have reached (x, y) since their previous event are excluded; if nobody can, the nearest
        feasible point toward the least-stretched player is returned instead of (x, y).
        Returns (player, x, y)."""
        cands, w = [], []
        x, y = _clip(x), _clip(y)
        ax, ay = self.absxy(tid, x, y)
        best, best_gap = None, None
        shift_x, shift_y = KX * (bx - 50), KY * (y - 50)
        for s in self.on[tid]:
            p = s.p
            if p is exclude or (skip_gk and s.role == "goalkeeper"):
                continue
            px = _clip(s.hx + shift_x, 3, 97)
            py = _clip(s.hy + shift_y, 3, 97)
            d = math.hypot((px - x) * 1.05, (py - y) * 0.68)
            lp = self.last.get(p.player_id)
            if lp is not None:
                dt = self.clock - lp[0]
                reach = 6.0 + MAX_SPEED * dt
                gap = math.hypot((ax - lp[1]) * 1.05, (ay - lp[2]) * 0.68) - reach
                if gap > 0:
                    if best_gap is None or gap < best_gap:
                        best, best_gap = (p, lp, reach), gap
                    continue
            cands.append(p)
            wt = math.exp(-d / scale) * (p.usage if usage else 1.0)
            if usage and self.usage_mult:
                wt *= self.usage_mult.get(p.player_id, 1.0)
            w.append(wt)
        if cands:
            return self.rng.choices(cands, w)[0], x, y
        p, lp, reach = best
        # move the action point toward where he was, to the edge of his reach
        lx, ly = self.absxy(tid, lp[1], lp[2])          # back into tid's frame (the map is its own inverse)
        dxm, dym = (x - lx) * 1.05, (y - ly) * 0.68
        d = math.hypot(dxm, dym) or 1.0
        f = max(0.0, (reach - 0.5) / d)
        return p, _clip(lx + (x - lx) * f), _clip(ly + (y - ly) * f)

    def within_reach(self, tid, player_id, x, y):
        """(x, y) in tid's frame, pulled toward the player's last position to the edge of his reach
        (the teleport guard) when he could not have got there. Uses no random numbers."""
        lp = self.last.get(player_id)
        if lp is None:
            return x, y
        reach = 6.0 + MAX_SPEED * (int(self.clock) - int(lp[0]))
        lx, ly = self.absxy(tid, lp[1], lp[2])
        d = math.hypot((x - lx) * 1.05, (y - ly) * 0.68)
        if d <= reach:
            return x, y
        f = max(0.0, (reach - 0.5) / d)
        return round(lx + (x - lx) * f, 1), round(ly + (y - ly) * f, 1)

    def emit(self, tid, player_id, etype, xs, ys, xe=None, ye=None, outcome="success",
             body="foot", pattern="open_play", pressed=False, idx=None, related="") -> str:
        eid = f"{self.mid}_e{len(self.events) + 1:05d}"
        if etype in ("save", "claim") and player_id:
            xs, ys = self.within_reach(tid, player_id, xs, ys)   # a keeper drawn off his line saves short of the spot
        c = int(self.clock)
        rel = c - int(self.h_start)
        minute = (rel // 60) + (45 if self.period == 2 else 0)
        self.events.append(dict(
            event_id=eid, match_id=self.mid, period=self.period,
            minute=minute, second=rel % 60, clock_sec=c, team_id=tid, player_id=player_id,
            opponent_team_id=self.other(tid), event_type=etype,
            x_start=round(xs, 1), y_start=round(ys, 1),
            x_end=None if xe is None else round(xe, 1), y_end=None if ye is None else round(ye, 1),
            outcome=outcome, body_part=body, play_pattern=pattern, under_pressure=int(pressed),
            possession_id=self.poss_id, sequence_id=self.seq_id, sequence_index=idx,
            score_home=self.score[self.home_id], score_away=self.score[self.away_id],
            related_player_id=related))
        if player_id and etype not in ("substitution", "card"):     # off-ball paperwork has no position
            fx, fy = (xe, ye) if (xe is not None and etype == "carry") else (xs, ys)
            ax, ay = self.absxy(tid, fx, fy)
            self.last[player_id] = (self.clock, ax, ay)
        return eid

    def tick(self, team: TeamSpec, factor: float = 1.0):
        dt = team.tempo * TEMPO_SCALE * self.rng.uniform(0.6, 1.4) * factor
        self.clock += dt
        self.bip += dt

    def run_time(self, dt: float):
        """In-play time that is not a team action (ball travelling, loose ball)."""
        self.clock += dt
        self.bip += dt

    def dead(self, kind: str):
        lo, hi = DEAD[kind]
        self.clock += self.rng.uniform(lo, hi)

    def gain(self, tid):
        """`tid` now has the ball: a new possession if it was the other team's."""
        if self.poss_team != tid:
            self.poss_team = tid
            self.poss_id += 1

    # ---------- shots ----------
    def shot_prob(self, tid: str, x, y, opp_deep) -> float:
        """Chance of shooting from (x, y). Volume scales with `attacking_output`, the opponent's
        defence, the home side's chance edge, game state and match time; it never depends on how
        deep the shooting team itself sits."""
        t = self.teams[tid]
        if x < 62:
            return 0.0
        if in_box(x, y):
            p = SHOT_RATE_BOX * (0.85 + (x - 84) / 30)
        elif x >= 75:
            p = SHOT_RATE_BOX * 0.24
        else:
            p = SHOT_RATE_BOX * 0.02
        if not in_box(x, y):
            p *= 1 + 4 * t.shot_spam * (1.0 if opp_deep > 0 else 0.15)
        if abs(y - 50) > 25:
            p *= 0.5
        o = self.teams[self.other(tid)]
        # a chasing opponent leaves space behind: its urgency opens the game for both sides
        open_ = 1 + 0.6 * (self.urgency(self.other(tid)) - 1)
        p *= (t.attacking_output * self.form[tid] * self.urgency(tid) * open_ * self.intensity()
              * (HOME_CHANCES if tid == self.home_id else 1.0) / o.dfn ** DFN_SHOTS)
        if self.men[tid] < self.men[self.other(tid)]:
            p *= 0.75
        elif self.men[tid] > self.men[self.other(tid)]:
            p *= 1.15
        return min(p, 0.45)

    def take_shot(self, tid, shooter: Player, x, y, header, pattern, assist_eid, pressed, idx,
                  shot_type=None):
        o_id = self.other(tid)
        rng = self.rng
        if shot_type == "penalty":
            dist, angle = goal_geometry(x, y)
            xg = PENALTY_XG
        else:
            dist, angle, xg = xg_model(x, y, header, pattern == "set_piece")
        odds = xg / (1 - xg) * shooter.finishing
        p_goal = odds / (1 + odds)
        opp_deep = self.deep(o_id)
        block_p = 0.0 if shot_type == "penalty" else (0.17 + 0.24 * opp_deep + 0.004 * dist) * (0.4 if header else 1.0)
        forced = (self.force_goal and tid == self.force_goal["team_id"]
                  and self.clock >= self.force_goal["after_sec"] and xg >= 0.08)
        if forced:
            result = "goal"
            self.force_goal = None
        elif rng.random() < p_goal:
            result = "goal"
        else:
            u = rng.random() * (1 - p_goal)
            if u < block_p:
                result = "blocked"
            elif u < block_p + (0.22 + 0.50 * xg) * (1 - p_goal):
                result = "saved"
            else:
                result = "off_target"
        speed = max(40.0, min(135.0, rng.gauss(102 - 0.6 * (dist - 15), 8) - (28 if header else 0)))
        if shot_type is None:
            shot_type = "header" if header else ("set_piece" if pattern == "set_piece" else "open_play")
        eid = self.emit(tid, shooter.player_id, "shot", x, y, outcome=result,
                        body="head" if header else "foot", pattern=pattern, pressed=pressed, idx=idx)
        self.shots.append(dict(
            event_id=eid, match_id=self.mid, team_id=tid, player_id=shooter.player_id,
            shot_distance_m=round(dist, 1), shot_angle_rad=round(angle, 3),
            shot_type=shot_type, assist_event_id=assist_eid or "", is_big_chance=int(xg >= 0.3),
            shot_result=result, xg=round(xg, 4), shot_speed_kmh=round(speed, 1)))
        self.xg[tid] += xg
        if assist_eid and assist_eid in self.passes:
            self.passes[assist_eid]["is_key_pass"] = 1
            self.passes[assist_eid]["xa"] = round(xg, 4)
        return result

    def after_shot(self, tid, result, x, y) -> dict:
        o_id = self.other(tid)
        rng = self.rng
        if result == "goal":
            self.score[tid] += 1
            self.stoppage["goals"] += 1
            self.dead("goal")
            return self.restart(o_id, "kickoff", 50, 50)
        if result == "blocked":
            b, bx, by = self.pick(o_id, 100 - x, 100 - y, 100 - x, scale=10)
            self.emit(o_id, b.player_id, "block", bx, by, outcome="success")
            self.run_time(1.0)
            u = rng.random()
            if u < 0.30 + 0.15 * self.deep(o_id):
                return self.restart(tid, "corner")
            if u < 0.62:
                return self.loose(tid, x - rng.uniform(3, 15), y + rng.gauss(0, 12), recover_own=0.55)
            return self.loose(tid, x - rng.uniform(2, 10), y + rng.gauss(0, 10), recover_own=0.35)
        if result == "saved":
            g = self.gk(o_id)
            self.run_time(0.5)
            u = rng.random()
            if u < 0.28:
                self.emit(o_id, g.player_id, "save", 4, 50, outcome="parried")
                return self.restart(tid, "corner")
            if u < 0.48:
                self.emit(o_id, g.player_id, "save", 4, 50, outcome="parried")
                return self.loose(tid, min(x, 92) - rng.uniform(0, 8), 50 + rng.gauss(0, 15), recover_own=0.4)
            self.emit(o_id, g.player_id, "save", 4, 50, outcome="held")
            sx, sy = self.events[-1]["x_start"], self.events[-1]["y_start"]     # where he actually held it
            self.gain(o_id)
            self.emit(o_id, g.player_id, "possession_change", sx, sy)
            self.run_time(rng.uniform(4, 9))
            return dict(team=o_id, x=sx + 4, y=sy, pattern="open_play", holder=g)
        # off target: goal kick
        self.dead("goal_kick")
        return self.restart(o_id, "goal_kick")

    # ---------- possession handover ----------
    def turnover(self, gaining: str, ball_x, ball_y, winner_action, pressed, winner=None) -> dict:
        """Ball lost by the other team at (x, y) in ITS frame. Emits the winning action and the
        possession_change, returns the next possession dict in the gaining team's frame."""
        g = self.teams[gaining]
        gx, gy = _clip(100 - ball_x), _clip(100 - ball_y)
        if winner is None:
            winner, gx, gy = self.pick(gaining, gx, gy, gx, skip_gk=gx > 18, scale=12, usage=False)
        self.gain(gaining)
        self.emit(gaining, winner.player_id, winner_action, gx, gy)
        self.emit(gaining, winner.player_id, "possession_change", gx, gy)
        pattern = "counter" if (gx < 55 and self.rng.random() < g.counter) else "open_play"
        return dict(team=gaining, x=gx, y=gy, pattern=pattern, holder=winner)

    def loose(self, last_tid, x, y, recover_own=0.4) -> dict:
        """A loose ball at (x, y) in last_tid's frame: a ball recovery by either side."""
        x, y = _clip(x, 2, 98), _clip(y, 2, 98)
        self.run_time(self.rng.uniform(1, 3))
        if self.rng.random() < recover_own:
            p, x, y = self.pick(last_tid, x, y, x, skip_gk=x > 18, scale=12, usage=False)
            self.emit(last_tid, p.player_id, "ball_recovery", x, y)
            self.gain(last_tid)
            return dict(team=last_tid, x=x, y=y, pattern="open_play", holder=p)
        return self.turnover(self.other(last_tid), x, y, "ball_recovery", False)

    def out_of_play(self, last_tid, xe, ye) -> dict:
        """The ball left the pitch off `last_tid` near (xe, ye) in its frame."""
        o_id = self.other(last_tid)
        if xe >= 99 or (xe >= 96 and abs(ye - 50) > 12):
            self.dead("goal_kick")
            return self.restart(o_id, "goal_kick")
        if xe <= 1:
            return self.restart(last_tid, "corner")
        side = 0.5 if ye < 50 else 99.5
        self.dead("throw_in")
        return self.restart(o_id, "throw_in", 100 - _clip(xe, 2, 98), 100 - side)

    # ---------- restarts ----------
    def restart(self, tid, kind, x=None, y=None, fouled=None) -> dict:
        """Dead-ball restart for `tid` (its frame). Substitutions are made at dead balls."""
        rng = self.rng
        self.seq_id += 1
        self.maybe_subs()
        if fouled is not None and not any(s.p is fouled for s in self.on[tid]):
            fouled = self.pick(tid, x, y, x)[0]        # he was just substituted at this dead ball
        if kind == "kickoff":
            self.dead("kickoff")
            self.gain(tid)
            p, _, _ = self.pick(tid, 50, 50, 50, usage=False)
            return dict(team=tid, x=50.0, y=50.0, pattern="kickoff", holder=p, restart="kickoff")
        if kind == "corner":
            return self.corner(tid)
        if kind == "goal_kick":
            self.gain(tid)
            return dict(team=tid, x=5.5, y=rng.choice((38.0, 62.0)), pattern="goal_kick",
                        holder=self.gk(tid), restart="goal_kick")
        if kind == "throw_in":
            self.gain(tid)
            p, x, y = self.pick(tid, x, y, x, scale=10, usage=False)
            return dict(team=tid, x=x, y=y, pattern="throw_in", holder=p, restart="throw_in")
        if kind == "free_kick":
            self.dead("free_kick")
            self.gain(tid)
            taker = fouled
            if x >= 70 or rng.random() < 0.6:
                taker = self.free_kick_taker(tid) or fouled
            return dict(team=tid, x=x, y=y, pattern="set_piece", holder=taker, restart="free_kick")
        raise ValueError(kind)

    def free_kick_taker(self, tid):
        for role in ROLE_FREE_KICK:
            for s in self.on[tid]:
                if s.role == role and not s.p.set_piece_taker:
                    return s.p
        return None

    def corner(self, tid) -> dict:
        rng = self.rng
        t, o_id = self.teams[tid], self.other(tid)
        self.dead("corner")
        self.gain(tid)
        self.seq_id += 1
        taker = next((s.p for s in self.on[tid] if s.p.set_piece_taker), None) or \
            next((s.p for s in self.on[tid] if s.role in ("left_winger", "right_winger", "left_mid", "right_mid",
                                                            "attacking_mid", "central_mid_r")), self.on[tid][-1].p)
        ys = 0.5 if rng.random() < 0.5 else 99.5
        self.last.pop(taker.player_id, None)
        if rng.random() < 0.12:                   # short corner
            xe, ye = rng.uniform(88, 95), ys + (8 if ys < 50 else -8)
            recv, xe, ye = self.pick(tid, xe, ye, 90, exclude=taker)
            eid = self.emit(tid, taker.player_id, "pass", 99.5, ys, xe, ye, pattern="set_piece", idx=0)
            self.record_pass(eid, taker, recv, 99.5, ys, xe, ye, "corner", True, 0.95)
            self.run_time(2)
            return dict(team=tid, x=xe, y=ye, pattern="set_piece", holder=recv, last_pass=eid, idx=1)
        xe, ye = rng.uniform(88, 95), 50 + rng.gauss(0, 9)
        recv, xe, ye = self.pick(tid, xe, ye, 90, exclude=taker)
        p_succ = 0.40 + 0.25 * taker.set_piece_taker * taker.delivery + 0.1 * (self.att(tid) - self.teams[o_id].dfn)
        ok = rng.random() < p_succ
        eid = self.emit(tid, taker.player_id, "pass", 99.5, ys, xe, ye,
                        outcome="success" if ok else "fail", pattern="set_piece", idx=0)
        self.record_pass(eid, taker, recv, 99.5, ys, xe, ye, "corner", ok, p_succ)
        self.run_time(1.5)
        if ok:
            self.emit(tid, recv.player_id, "duel", xe, ye, body="head", outcome="success", pattern="set_piece")
            u = rng.random()
            if u < 0.40:
                res = self.take_shot(tid, recv, xe, ye, True, "set_piece", eid, False, 1)
                return self.after_shot(tid, res, xe, ye)
            if u < 0.55:
                res = self.take_shot(tid, recv, xe, ye, False, "set_piece", eid, False, 1)
                return self.after_shot(tid, res, xe, ye)
            return self.loose(tid, xe - rng.uniform(4, 14), ye + rng.gauss(0, 12), recover_own=0.4)
        return self.defend_aerial(tid, xe, ye, pattern="set_piece", recv=recv)

    def defend_aerial(self, tid, xe, ye, pattern="open_play", recv=None) -> dict:
        """A failed delivery into the box: the keeper claims, or a defender heads it clear."""
        rng = self.rng
        o_id = self.other(tid)
        if rng.random() < 0.18:
            g = self.gk(o_id)
            self.emit(o_id, g.player_id, "claim", _clip(100 - xe, 2, 18), 100 - ye)
            self.gain(o_id)
            self.emit(o_id, g.player_id, "possession_change", _clip(100 - xe, 2, 18), 100 - ye)
            self.run_time(rng.uniform(4, 9))
            return dict(team=o_id, x=_clip(100 - xe, 2, 18), y=100 - ye, pattern="open_play", holder=g)
        d, dx, dy = self.pick(o_id, 100 - xe, 100 - ye, 100 - xe, scale=8, usage=False)
        if recv is not None:
            self.emit(tid, recv.player_id, "duel", xe, ye, body="head", outcome="fail", pattern=pattern)
        self.emit(o_id, d.player_id, "duel", dx, dy, body="head", outcome="success", pattern=pattern)
        return self.clearance(o_id, d, dx, dy)

    def clearance(self, tid, player, x, y, body="head") -> dict:
        """`tid` clears from (x, y) (its frame): out for a throw-in or corner, or a loose ball."""
        rng = self.rng
        self.emit(tid, player.player_id, "clearance", x, y, _clip(x + rng.uniform(20, 45), 2, 98),
                  _clip(y + rng.gauss(0, 25), 1, 99), body=body)
        self.run_time(rng.uniform(1.5, 3))
        u = rng.random()
        corner_p = 0.10 + 0.12 * self.deep(tid)        # a deep block hacks it behind more often
        if u < corner_p:
            return self.restart(self.other(tid), "corner")
        if u < corner_p + 0.22:
            self.dead("throw_in")
            return self.restart(self.other(tid), "throw_in", 100 - _clip(x + rng.uniform(15, 35), 2, 98),
                                rng.choice((0.5, 99.5)))
        return self.loose(tid, x + rng.uniform(25, 45), y + rng.gauss(0, 20), recover_own=0.42)

    # ---------- passes ----------
    def record_pass(self, eid, passer: Player, recv: Player | None, xs, ys, xe, ye, ptype,
                    ok, p_succ):
        dm = math.hypot((xe - xs) * PITCH_LEN_M / 100, (ye - ys) * PITCH_WID_M / 100)
        speed = max(18.0, min(95.0, self.rng.gauss(40 + 0.6 * dm if ptype != "cross" else 62, 8)))
        self.passes[eid] = dict(
            event_id=eid, match_id=self.mid, passer_id=passer.player_id,
            recipient_player_id=recv.player_id if (recv and ok) else "",
            pass_distance_m=round(dm, 1),
            pass_angle_rad=round(math.atan2((ye - ys) * PITCH_WID_M / 100,
                                            (xe - xs) * PITCH_LEN_M / 100), 3),
            pass_type=ptype, pass_difficulty=round(1 - p_succ, 3), ball_speed_kmh=round(speed, 1),
            is_forward=int(xe - xs >= 8), is_progressive=int(xe - xs >= 10),
            is_key_pass=0, xa=0.0)

    def pass_success(self, tid, o, opp_deep, pressed, xs, ys, xe, ye, long=False, pattern="open_play"):
        dm = math.hypot((xe - xs) * PITCH_LEN_M / 100, (ye - ys) * PITCH_WID_M / 100)
        p = 0.99 - 0.005 * dm + (0.04 if xs < 50 else 0.0)     # little pressure on the ball at the back
        if long:
            p = 0.62 - 0.004 * max(dm - 30, 0)
        if pattern == "counter":
            p -= 0.10
        if pressed:
            p -= 0.10
        if xe >= FINAL_THIRD_X:
            p -= 0.08 + 0.12 * (xe - FINAL_THIRD_X) / 33
            if xs >= FINAL_THIRD_X and not in_box(xe, ye) and opp_deep == 0:
                p -= 0.05                       # crowded: circulation around the box breaks down
                                                # (a deep block leaves the edge of the box free)
        p += 0.18 * (self.att(tid) - o.dfn)
        p += RETENTION * (0.5 - self.teams[tid].directness)    # patient sides pick safer options
        lane = lane_of(ye)
        if o.weak_lane and lane == o.weak_lane:
            p += (0.06 + (0.03 if xe >= FINAL_THIRD_X else 0)) * o.weak_strength
        if in_box(xe, ye):
            p *= (1 - BLOCK_BOX * opp_deep) * self.urgency(tid) * self.teams[tid].attacking_output
        elif opp_deep > 0 and not pressed and xe >= FINAL_THIRD_X:
            p += 0.04
        return max(0.30, min(0.97, p))

    def destination(self, tid, holder, x, y, mode, ptype, opp_deep=0.0):
        """End point of a pass of `mode` from (x, y). Against a deep block the ball is worked
        around the edge of the box instead of recycled to the back line."""
        rng = self.rng
        t = self.teams[tid]
        if mode == "forward":
            if holder.wide_forward and rng.random() < 0.95:
                lane_i = 0 if holder.hy < 50 else 4
            else:
                o = self.teams[self.other(tid)]
                w = [lw * math.exp(-abs(c - y) / 60)
                     * (1 + TARGET_WEAK * o.weak_strength * (lane == o.weak_lane and abs(c - y) <= 40))
                     for lw, c, lane in zip(t.lane_weights, LANE_CENTERS, LANES)]
                lane_i = rng.choices(range(5), w)[0]
            ye = _clip(LANE_CENTERS[lane_i] + rng.gauss(0, 6), 2, 98)
            if ptype == "long_ball":
                xe = x + rng.uniform(26, 48)
            elif ptype == "through_ball":
                xe = x + rng.uniform(14, 26)
            else:
                xe = x + rng.uniform(9, 20)
            xe = min(xe, 91.0 if ptype == "through_ball" else (85.0 if ptype == "long_ball" else 88.0))
            if holder.wide_forward:
                xe = min(xe, 80.0)       # his forward balls go into the channel, not the box
            return xe, ye
        if mode == "cross":
            return rng.uniform(86, 95), 50 + rng.gauss(0, 9)
        if mode == "back":
            ang = math.radians(rng.uniform(140, 220))
            if x >= FINAL_THIRD_X and rng.random() < 0.7 * (1 - 0.9 * opp_deep):
                dm = rng.uniform(26, 38)               # recycle to the back line
            else:
                dm = rng.lognormvariate(math.log(9 if x < 33 else (15 if x < FINAL_THIRD_X else 18)), 0.4)
        elif mode == "lateral":
            side = 1 if rng.random() < (0.5 + (50 - y) / 110) else -1
            ang = math.radians(side * (rng.uniform(65, 125) if x < 33 else rng.uniform(40, 125)))
            dm = rng.lognormvariate(math.log(14), 0.45)
        else:                                       # "short": a short pass in any forward-ish direction
            ang = math.radians(rng.uniform(-80, 80) if x < FINAL_THIRD_X else rng.uniform(-110, 110))
            dm = rng.lognormvariate(math.log(9), 0.35)
        xe = x + dm * math.cos(ang) * 100 / PITCH_LEN_M
        ye = y + dm * math.sin(ang) * 100 / PITCH_WID_M
        if ye < 2 or ye > 98:
            ye = y - (ye - y) * 0.6
        return _clip(xe, 1.5, 96), _clip(ye, 2, 98)

    # ---------- discipline ----------
    def foul(self, def_tid, fouler: Player, x, y, fouled: Player, x_att, y_att) -> dict:
        """`fouler` (def_tid) fouls `fouled` at (x, y) in def_tid's frame. Free kick or penalty."""
        rng = self.rng
        att_tid = self.other(def_tid)
        pen = in_box(x_att, y_att)
        self.emit(def_tid, fouler.player_id, "foul", x, y, outcome="penalty" if pen else "free_kick",
                  related=fouled.player_id)
        u = rng.random()
        agg = fouler.aggression
        if u < RED_P * agg:
            self.card(def_tid, fouler, x, y, "red")
        elif u < (RED_P + YELLOW_P * (1.6 if pen else 1.0) * (0.45 if self.yellows.get(fouler.player_id) else 1.0)) * agg:
            kind = "second_yellow" if self.yellows.get(fouler.player_id) else "yellow"
            self.card(def_tid, fouler, x, y, kind)
        if rng.random() < 0.035:
            self.injury(att_tid, fouled)
        if pen:
            self.dead("penalty")
            self.seq_id += 1
            self.gain(att_tid)
            taker = next((s.p for s in self.on[att_tid] if s.p.penalty_taker), None) or \
                max((s.p for s in self.on[att_tid]), key=lambda p: p.finishing)
            res = self.take_shot(att_tid, taker, 89.5, 50.0, False, "set_piece", None, False, 0, shot_type="penalty")
            return self.after_shot(att_tid, res, 89.5, 50.0)
        return self.restart(att_tid, "free_kick", x_att, y_att, fouled=fouled)

    def care(self, p: Player) -> float:
        """Foul propensity: the player's aggression, much lower once he is booked."""
        return p.aggression * (0.35 if self.yellows.get(p.player_id) else 1.0)

    def card(self, tid, p: Player, x, y, kind):
        self.dead("card")
        self.emit(tid, p.player_id, "card", x, y, outcome=kind)
        self.cards.append((p.player_id, kind))
        self.stoppage["cards"] += 1
        self.yellows[p.player_id] = self.yellows.get(p.player_id, 0) + (kind != "red")
        if kind in ("red", "second_yellow"):
            self.send_off(tid, p)

    def send_off(self, tid, p: Player):
        slots = self.on[tid]
        i = next(i for i, s in enumerate(slots) if s.p is p)
        role = slots[i].role
        del slots[i]
        self.men[tid] -= 1
        self.minutes[p.player_id][2] = int(self.clock)
        self.minutes[p.player_id][3] = 1
        if role == "goalkeeper":
            # an outfielder (the most advanced) goes off for the reserve keeper if a sub is left
            gk = next((b for b in self.bench[tid] if b.position == "GK"), None)
            out = max(slots, key=lambda s: s.hx)
            if gk and self.subs_left[tid] > 0:
                self.substitute(tid, out, gk, "tactical", role="goalkeeper", hx=5, hy=50)
            else:
                out.role, out.hx, out.hy = "goalkeeper", 5, 50
        # bring subs forward: a side down to ten reacts sooner
        self.sub_plan[tid] = [max(self.clock + 300, t) if t > self.clock else t for t in self.sub_plan[tid]]

    def injury(self, tid, p: Player):
        if p.trap_flag or not any(s.p is p for s in self.on[tid]):
            return
        lp = self.last.get(p.player_id)              # where he went down: his last position
        ix, iy = self.absxy(tid, lp[1], lp[2]) if lp else (50, 50)
        self.emit(tid, p.player_id, "injury", ix, iy, outcome="off")
        self.dead("injury")
        self.stoppage["injuries"] += 1
        self.injured.append((p.player_id, self.rng.choice((1, 1, 1, 2, 2, 3, 4))))
        slot = next(s for s in self.on[tid] if s.p is p)
        on = self.bench_pick(tid, slot)
        if on is not None and self.subs_left[tid] > 0:
            self.substitute(tid, slot, on, "injury")
        else:
            self.on[tid].remove(slot)
            self.men[tid] -= 1
            self.minutes[p.player_id][2] = int(self.clock)

    # ---------- substitutions ----------
    def _plan_subs(self, tid) -> list:
        """Planned substitution times (seconds of regulation clock): 2-5 subs from about minute
        55, in up to three windows."""
        rng = self.rng
        n = rng.choices((2, 3, 4, 5), (0.08, 0.22, 0.35, 0.35))[0]
        first = rng.uniform(54, 70) * 60
        times = sorted([first] + [rng.uniform(first, 88 * 60) for _ in range(n - 1)])
        # group into at most three windows
        win = sorted(set(times[i] for i in (0, len(times) // 2, len(times) - 1)))
        return [min(win, key=lambda w: abs(w - t) if w <= t else 1e9) for t in times]

    def bench_pick(self, tid, slot: _Slot):
        pos = slot.p.position if slot.role != "goalkeeper" else "GK"
        same = [b for b in self.bench[tid] if b.position == pos]
        if pos != "GK":
            same = same or [b for b in self.bench[tid] if b.position != "GK"]
        return same[0] if same else None

    def substitute(self, tid, slot: _Slot, on: Player, reason, role=None, hx=None, hy=None):
        off = slot.p
        self.emit(tid, off.player_id, "substitution", 50, 0.5, outcome=reason, related=on.player_id)
        self.minutes[off.player_id][2] = int(self.clock)
        self.minutes[on.player_id] = [tid, int(self.clock), None, 0, 0]
        self.bench[tid].remove(on)
        slot.p = on
        if role:
            slot.role, slot.hx, slot.hy = role, hx, hy
        self.subs_left[tid] -= 1
        self.stoppage["subs"] += 1
        self.last.pop(on.player_id, None)

    def maybe_subs(self):
        """At a dead ball: make the substitutions that are due (one window per team)."""
        el = self.elapsed() if self.period == 2 else 0
        if self.period == 1:
            return
        for tid in (self.home_id, self.away_id):
            plan = self.sub_plan[tid]
            due = [t for t in plan if t <= el]
            if not due or self.subs_left[tid] <= 0 or self.windows_left[tid] <= 0:
                continue
            trailing = self.score[tid] < self.score[self.other(tid)]
            n = min(len(due), self.subs_left[tid])
            self.sub_plan[tid] = plan[n:]
            self.windows_left[tid] -= 1
            for _ in range(n):
                slot = self.sub_off(tid, trailing)
                if slot is None:
                    break
                on = self.bench_pick(tid, slot)
                if on is None:
                    break
                tired = (self.clock - self.minutes[slot.p.player_id][1]) > 3600
                self.substitute(tid, slot, on, "fatigue" if tired and not trailing else "tactical")
            self.dead("sub")

    def sub_off(self, tid, trailing):
        """Who comes off: outfield starters, more often booked players, attackers when chasing...
        Planted-trap players and keepers stay on."""
        rng = self.rng
        cands, w = [], []
        for s in self.on[tid]:
            p = s.p
            if s.role == "goalkeeper" or p.trap_flag or self.minutes[p.player_id][4] == 0:
                continue
            wt = 1.0 + 1.5 * bool(self.yellows.get(p.player_id))
            if trailing and p.position == "DF":
                wt *= 0.5
            if p.position == "FW" or p.position == "MF":
                wt *= 1.4
            cands.append(s)
            w.append(wt)
        return rng.choices(cands, w)[0] if cands else None

    # ---------- one possession sequence ----------
    def run_sequence(self, st: dict) -> dict:
        rng = self.rng
        tid = st["team"]
        t, o_id = self.teams[tid], self.other(tid)
        o = self.teams[o_id]
        x, y, holder, pattern = st["x"], st["y"], st["holder"], st["pattern"]
        restart = st.get("restart")
        idx = st.get("idx", 0)
        if not st.get("idx"):
            self.seq_id += 1
        n_steps = 0
        # A leader protects its lead on a share of its possessions set by `sit_deep`; on the rest it
        # plays normally.
        protect = rng.random() < self.deep(tid)
        protect_from = round(3 * (1 - t.sit_deep))     # a real low-block side clears its lines at once
        last_pass = st.get("last_pass")
        via_weak = False
        if self.motifs is not None:
            m = self.motifs.at_start(tid, x, y, holder, pattern, restart, idx)
            if m is not None:
                if m[0] == "return":
                    return m[1]
                _, x, y, holder, last_pass, idx, pattern = m
        while self.clock < self.end_at and n_steps < 90:
            n_steps += 1
            opp_deep = self.deep(o_id)
            pressed = False
            if restart is None:
                if rng.random() < INJURY_P:
                    self.injury(tid, holder)
                    if not any(s.p is holder for s in self.on[tid]):
                        return self.restart(tid, "free_kick", x, y, fouled=self.pick(tid, x, y, x)[0])
                pp = PRESS_RATE * o.press * (1 - opp_deep) * (0.25 + 0.75 * (1 - x / 100))
                if self.men[o_id] < self.men[tid]:
                    pp *= 0.8
                pressed = rng.random() < pp
                if pressed:
                    d, dx, dy = self.pick(o_id, 100 - x, 100 - y, 100 - x, scale=12, usage=False)
                    self.emit(o_id, d.player_id, "pressure", dx, dy, outcome="applied", idx=idx)
                    # challenge
                    if rng.random() < TACKLE_RATE:
                        if rng.random() < FOUL_RATE * self.care(d) * (0.08 if in_box(x, y) else 1.0):
                            return self.foul(o_id, d, dx, dy, holder, x, y)
                        win = TACKLE_WIN + 0.15 * (o.dfn - self.att(tid))
                        if rng.random() < win:
                            self.emit(o_id, d.player_id, "tackle", dx, dy, outcome="success", idx=idx)
                            if rng.random() < 0.25:
                                return self.loose(o_id, dx, dy, recover_own=0.55)
                            return self._won(o_id, d, dx, dy)
                        self.emit(o_id, d.player_id, "tackle", dx, dy, outcome="fail", idx=idx)
                        self.run_time(1.0)
                elif not in_box(x, y) and rng.random() < LOOSE_FOUL:
                    d, dx, dy = self.pick(o_id, 100 - x, 100 - y, 100 - x, scale=12, usage=False)
                    if rng.random() < self.care(d):
                        return self.foul(o_id, d, dx, dy, holder, x, y)
                if in_box(x, y) and rng.random() < BOX_FOUL * t.attacking_output:
                    d, dx, dy = self.pick(o_id, 100 - x, 100 - y, 100 - x, scale=10, usage=False)
                    return self.foul(o_id, d, dx, dy, holder, x, y)
                # shot?
                sp = self.shot_prob(tid, x, y, opp_deep) * (1 + WEAK_CREATE * o.weak_strength * via_weak)
                if self.motifs is not None:
                    sp *= self.motifs.shot_factor(tid)
                if rng.random() < sp:
                    self.tick(t, 0.4)
                    if self.motifs is not None:
                        m = self.motifs.at_shot(tid, x, y, holder, pattern, idx)
                        if m is not None:
                            return m[1]
                    res = self.take_shot(tid, holder, x, y, False, pattern, last_pass, pressed, idx)
                    return self.after_shot(tid, res, x, y)
                # take-on?
                drib = DRIBBLE_RATE * (2.5 if holder.position == "FW" else 1.0) * (1.6 if x >= FINAL_THIRD_X else 0.6)
                if not protect and rng.random() < drib:
                    d, dx, dy = self.pick(o_id, 100 - x, 100 - y, 100 - x, scale=10, usage=False)
                    ok = rng.random() < 0.52 + 0.2 * (self.att(tid) - o.dfn)
                    self.emit(tid, holder.player_id, "dribble", x, y, outcome="success" if ok else "fail",
                              pattern=pattern, idx=idx)
                    if not ok:
                        self.emit(o_id, d.player_id, "tackle", dx, dy, outcome="success", pattern=pattern, idx=idx)
                        return self._won(o_id, d, dx, dy)
                    nx, ny = _clip(x + rng.uniform(4, 10), 2, 97), _clip(y + rng.gauss(0, 6), 2, 98)
                    self.tick(t, 0.6)
                    self.emit(tid, holder.player_id, "carry", x, y, nx, ny, pattern=pattern, idx=idx)
                    x, y = nx, ny
                    continue
            # ---- planted motifs (data_gen/motifs.py), only when a propensity is above zero ----
            if self.motifs is not None and restart is None:
                m = self.motifs.in_play(tid, x, y, holder, pattern, last_pass, pressed, idx)
                if m is not None:
                    if m[0] == "return":
                        return m[1]
                    _, x, y, holder, last_pass, idx, pattern = m
                    continue
            # ---- choose the pass ----
            in_final = x >= FINAL_THIRD_X
            wide = abs(y - 50) > 30
            ptype, long = "short", False
            if restart == "goal_kick":
                ptype = "goal_kick"
                if rng.random() < 0.35 + 0.5 * t.directness:
                    mode, long = "forward", True
                else:
                    mode = "lateral"
            elif restart == "throw_in":
                ptype = "throw_in"
                mode = rng.choices(("forward", "lateral", "back"), (0.4, 0.35, 0.25))[0]
            elif restart == "free_kick":
                ptype = "free_kick"
                if x >= 72 and abs(y - 50) < 22 and rng.random() < 0.35:
                    self.tick(t, 0.3)
                    res = self.take_shot(tid, holder, x, y, False, "set_piece", None, False, idx, shot_type="free_kick")
                    return self.after_shot(tid, res, x, y)
                if x >= 62 and rng.random() < 0.65:
                    mode = "cross"
                elif x < 45 and rng.random() < 0.3 + 0.4 * t.directness:
                    mode, long = "forward", True
                else:
                    mode = rng.choice(("short", "lateral", "back"))
            elif pattern == "counter" and idx < (1 if protect else 2):
                mode = "forward"
                ptype = "long_ball" if x < 45 else "through_ball"
                long = ptype == "long_ball"
            elif protect and n_steps > protect_from and in_final:
                mode = "waste"           # leader runs the clock, gives the ball back
            elif protect and n_steps > protect_from:
                mode, ptype, long = "forward", "long_ball", True
            elif in_final and wide and x >= 72 and rng.random() < CROSS_RATE * holder.cross_mult:
                mode = "cross"
            else:
                fwd_p = (0.12 + 0.55 * t.directness) * (1.2 if pressed else 1.0)
                if in_final:
                    fwd_p *= 0.5 if opp_deep == 0 else 0.45
                elif x < 33:
                    fwd_p *= 0.55 + 0.5 * t.directness     # patient sides circulate at the back
                if in_final and opp_deep > 0:
                    fwd_p *= (1 - 0.85 * opp_deep)
                if holder.wide_forward:
                    fwd_p = max(fwd_p, 0.8)      # the volume passer always plays it forward
                if protect:
                    fwd_p = max(fwd_p, 0.7)
                if opp_deep > 0.5 and 45 <= x < FINAL_THIRD_X:
                    fwd_p = max(fwd_p, 0.6)      # chasing a low block: push up
                if holder.position == "GK":
                    fwd_p = max(fwd_p, 0.3 + 0.6 * t.directness)
                back_p = 0.25 - 0.08 * t.directness + (0.05 if 33 <= x < FINAL_THIRD_X else 0) + (0.08 if pressed else 0) + (0.16 if in_final else 0) + (0.08 if x >= 84 else 0)
                if in_final and opp_deep > 0:
                    back_p *= 1 - 0.6 * opp_deep       # keep it around the box against a low block
                r = rng.random()
                if r < fwd_p:
                    mode = "forward"
                    if x < 55 and rng.random() < (0.05 + 0.40 * t.directness) * (1.6 if holder.position in ("GK", "DF") else 0.6):
                        ptype, long = "long_ball", True
                    elif x >= 45 and rng.random() < 0.12:
                        ptype = "through_ball"
                elif r < fwd_p + back_p * (1 - fwd_p) and x > 12:
                    mode = "back"
                else:
                    mode = "lateral" if rng.random() < 0.6 else "short"
            # destination
            if mode == "waste":
                xe = _clip(x + rng.uniform(-3, 3), 3, 94)
                ye = _clip(y + rng.gauss(0, 10), 2, 98)
            else:
                xe, ye = self.destination(tid, holder, x, y, mode, ptype if ptype in ("long_ball", "through_ball") else "",
                                          opp_deep)
            if mode == "cross":
                ptype = "cross" if ptype == "short" else ptype
            if mode == "lateral" and in_final and opp_deep > 0:
                xe = min(xe, 82.0)
            recv, xe, ye = self.pick(tid, xe, ye, x, exclude=holder, skip_gk=xe > 22)
            if mode == "cross":
                p_succ = 0.25 + 0.10 * o.weak_strength * (o.weak_lane == lane_of(y)) + 0.18 * (self.att(tid) - o.dfn)
                p_succ *= (1 - 0.4 * opp_deep)
                if ptype == "free_kick":
                    p_succ += 0.08
            elif ptype == "throw_in":
                p_succ = 0.80 if mode != "forward" else 0.62
            else:
                p_succ = self.pass_success(tid, o, opp_deep, pressed, x, y, xe, ye, long, pattern)
                if via_weak and x >= FINAL_THIRD_X and in_box(xe, ye):
                    p_succ = min(0.97, p_succ + 0.06 * o.weak_strength)
            if mode == "waste":
                p_succ = 0.30
            dm = math.hypot((xe - x) * 1.05, (ye - y) * 0.68)
            self.tick(t, (0.6 if pattern == "counter" else 1.0) * (0.7 if restart else 1.0))
            self.run_time(dm / 20)
            ok = rng.random() < p_succ
            offside = (not ok and ptype in ("through_ball", "long_ball", "short", "free_kick") and mode == "forward"
                       and xe >= 70 and restart != "throw_in" and rng.random() < OFFSIDE_P / (1 - min(p_succ, 0.9)))
            sp_pattern = pattern
            eid = self.emit(tid, holder.player_id, "pass", x, y, xe, ye,
                            outcome="success" if ok else ("offside" if offside else "fail"), pattern=sp_pattern,
                            pressed=pressed, idx=idx)
            self.record_pass(eid, holder, recv, x, y, xe, ye, ptype, ok, p_succ)
            idx += 1
            restart = None
            if ok:
                if mode == "cross":
                    u = rng.random()
                    if u < 0.30:
                        self.emit(tid, recv.player_id, "duel", xe, ye, body="head", outcome="success", pattern=pattern)
                        self.tick(t, 0.3)
                        res = self.take_shot(tid, recv, xe, ye, True, pattern, eid, False, idx)
                        return self.after_shot(tid, res, xe, ye)
                    if u < 0.44:
                        self.tick(t, 0.3)
                        res = self.take_shot(tid, recv, xe, ye, False, pattern, eid, False, idx)
                        return self.after_shot(tid, res, xe, ye)
                if long:
                    self.emit(tid, recv.player_id, "duel", xe, ye, body="head", outcome="success", pattern=pattern)
                    dd, ddx, ddy = self.pick(o_id, 100 - xe, 100 - ye, 100 - xe, scale=8, usage=False)
                    self.emit(o_id, dd.player_id, "duel", ddx, ddy, body="head", outcome="fail", pattern=pattern)
                if o.weak_lane and x < FINAL_THIRD_X <= xe and lane_of(ye) == o.weak_lane:
                    via_weak = True              # in behind the soft side: space to create from
                x, y, holder = xe, ye, recv
                last_pass = eid
                if pattern in ("kickoff", "throw_in", "goal_kick") or (pattern == "set_piece" and idx >= 3) \
                        or (pattern == "counter" and idx >= 3):
                    pattern = "open_play"
                if rng.random() < CARRY_P:
                    gainx = (rng.uniform(-2, 8) if x < FINAL_THIRD_X else rng.uniform(-4, 4)) \
                        + (6 if pattern == "counter" else 0)
                    nx, ny = _clip(x + gainx, 2, 96), _clip(y + rng.gauss(0, 5), 2, 98)
                    self.tick(t, 0.5)
                    self.emit(tid, holder.player_id, "carry", x, y, nx, ny, pattern=pattern, idx=idx)
                    x, y = nx, ny
                continue
            # ---- failed pass ----
            if offside:
                self.emit(tid, recv.player_id, "offside", xe, ye, outcome="offside")
                self.dead("offside")
                fx, fy = 100 - xe, 100 - ye
                return self.restart(o_id, "free_kick", fx, fy, fouled=self.pick(o_id, fx, fy, fx, usage=False)[0])
            if mode == "cross" or (ptype == "free_kick" and mode == "cross"):
                u = rng.random()
                if u < 0.12:
                    return self.restart(tid, "corner")
                if u < 0.20:
                    self.dead("goal_kick")
                    return self.restart(o_id, "goal_kick")
                if u < 0.32:
                    b, bx, by = self.pick(o_id, 100 - x - 3, 100 - y, 100 - x, scale=8, usage=False)
                    self.emit(o_id, b.player_id, "block", bx, by, outcome="success")
                    return self.restart(tid, "corner") if rng.random() < 0.4 else self.loose(tid, x - 5, y, 0.45)
                return self.defend_aerial(tid, xe, ye, pattern, recv)
            if long:
                self.emit(tid, recv.player_id, "duel", xe, ye, body="head", outcome="fail", pattern=pattern)
                d, dx, dy = self.pick(o_id, 100 - xe, 100 - ye, 100 - xe, scale=8, usage=False)
                self.emit(o_id, d.player_id, "duel", dx, dy, body="head", outcome="success", pattern=pattern)
                if dx < 30 and rng.random() < 0.55:
                    return self.clearance(o_id, d, dx, dy)
                if rng.random() < 0.12:
                    return self.out_of_play(tid, xe + rng.uniform(5, 20), ye + rng.gauss(0, 30))
                return self.loose(tid, xe + rng.gauss(0, 6), ye + rng.gauss(0, 8), recover_own=0.4)
            if mode == "waste":
                # a hopeful ball: the chasing side picks it up and goes again, no stoppage
                return self.loose(tid, xe + rng.uniform(0, 10), ye, recover_own=0.1)
            u = rng.random()
            if u < 0.19:
                d, dx, dy = self.pick(o_id, 100 - xe, 100 - ye, 100 - xe, scale=10, usage=False)
                self.emit(o_id, d.player_id, "interception", dx, dy, idx=idx)
                return self._won(o_id, d, dx, dy, emit=False)
            if u < 0.47:
                return self.out_of_play(tid, xe + (rng.uniform(4, 12) if mode == "forward" else 0),
                                        ye + rng.choice((-1, 1)) * rng.uniform(15, 50))
            if u < 0.55:
                d, dx, dy = self.pick(o_id, 100 - (x + xe) / 2, 100 - (y + ye) / 2, 100 - x, scale=8, usage=False)
                self.emit(o_id, d.player_id, "block", dx, dy, outcome="success", idx=idx)
                return self.loose(tid, (x + xe) / 2, (y + ye) / 2, recover_own=0.45)
            if u < 0.66:
                # receiver reached it and was tackled at once
                d, dx, dy = self.pick(o_id, 100 - xe, 100 - ye, 100 - xe, scale=10, usage=False)
                self.emit(o_id, d.player_id, "tackle", dx, dy, outcome="success", idx=idx)
                return self._won(o_id, d, dx, dy, emit=False)
            if 100 - xe < 30 and rng.random() < 0.45:
                d, dx, dy = self.pick(o_id, 100 - xe, 100 - ye, 100 - xe, scale=10, usage=False)
                return self.clearance(o_id, d, dx, dy, body="foot")
            return self.loose(tid, xe, ye, recover_own=0.30)
        # half over
        return None

    def _won(self, tid, player, x, y, emit=True) -> dict:
        """`tid` won the ball at (x, y) (its frame) by `player`'s action (already emitted)."""
        self.gain(tid)
        self.emit(tid, player.player_id, "possession_change", x, y)
        pattern = "counter" if (x < 55 and self.rng.random() < self.teams[tid].counter) else "open_play"
        return dict(team=tid, x=x, y=y, pattern=pattern, holder=player)

    # ---------- whole match ----------
    def announce(self):
        """Added time, shown at 45:00 / 90:00, from the stoppages of the half."""
        s, rng = self.stoppage, self.rng
        if self.period == 1:
            mins = 0.5 + 0.45 * s["goals"] + 0.25 * s["cards"] + 1.0 * s["injuries"] + rng.uniform(0, 1.6)
        else:
            mins = 2.4 + 0.6 * s["goals"] + 0.28 * s["subs"] + 0.25 * s["cards"] + 1.0 * s["injuries"] + rng.uniform(0, 2.2)
        mins = max(1, round(mins))
        self.end_at = self.h_start + HALF_SECONDS + mins * 60 + rng.uniform(0, 40)
        self.announced = True

    def play_half(self, kick_tid):
        st = self.restart(kick_tid, "kickoff")
        while True:
            if not self.announced and self.clock - self.h_start >= HALF_SECONDS:
                self.announce()
            if self.clock >= self.end_at:
                break
            nxt = self.run_sequence(st)
            if nxt is None:
                if not self.announced:
                    self.end_at = self.h_start + HALF_SECONDS
                    self.announce()
                    nxt = st if self.clock < self.end_at else None
                if nxt is None:
                    break
                # play on from where the ball is
                nxt = dict(team=st["team"], x=50, y=50, pattern="open_play",
                           holder=self.pick(st["team"], 50, 50, 50, usage=False)[0])
            st = nxt
        self.emit(self.home_id, "", "half_end", 50, 50, outcome="end")

    def run(self) -> None:
        self.play_half(self.home_id)
        self.period = 2
        self.h_start = float(int(self.clock))
        self.clock = self.h_start
        self.end_at = self.h_start + HALF_SECONDS + 600
        self.announced = False
        self.stoppage = dict(goals=0, subs=0, cards=0, injuries=0)
        self.last.clear()
        self.play_half(self.away_id)
        end = int(self.clock)
        for pid, m in self.minutes.items():
            if m[2] is None:
                m[2] = end

    def lineup_rows(self) -> list[dict]:
        rows = []
        h2 = self.h_start
        def mins(a, b):
            # match minutes: stoppage time counts, the half-time break does not exist on this clock
            return round((b - a) / 60, 1)
        for tid, lu in self.lineups.items():
            for p, role, *_ in lu.xi:
                m = self.minutes[p.player_id]
                rows.append(dict(match_id=self.mid, team_id=tid, player_id=p.player_id, role=role, starter=1,
                                 on_sec=m[1], off_sec=m[2], minutes_played=mins(m[1], m[2]), sent_off=m[3]))
            for p in lu.bench:
                m = self.minutes.get(p.player_id)
                rows.append(dict(match_id=self.mid, team_id=tid, player_id=p.player_id, role="bench", starter=0,
                                 on_sec="" if m is None else m[1], off_sec="" if m is None else m[2],
                                 minutes_played=0.0 if m is None else mins(m[1], m[2]),
                                 sent_off=0 if m is None else m[3]))
        return rows
