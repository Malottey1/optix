"""Squads, formations, lineups, rotation, suspensions and injuries.

Every team has a squad of 24 fictional players built around its formation: a first-choice XI (one
player per formation slot) plus 13 backups (2 goalkeepers and cover for every line). Names are
invented (common given names, surnames built from syllables) and unique across the league.

Before each match `SquadManager.matchday` picks the XI and a nine-player bench: first choices unless
suspended, injured or rested (rotation is light and more likely after a congested week); planted-trap
players are never rested or injured, so their traps stay visible. After the match `record` updates
suspensions (a red card bans the next match; a fifth yellow bans one match), injuries and fatigue.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

# slot role, home x, home y (own attacking frame), classic shirt number
FORMATIONS = {
    "4-3-3": [("goalkeeper", 5, 50, 1), ("left_back", 28, 12, 3), ("centre_back_l", 22, 38, 5),
              ("centre_back_r", 22, 62, 4), ("right_back", 28, 88, 2), ("defensive_mid", 40, 50, 6),
              ("central_mid_l", 52, 35, 8), ("central_mid_r", 52, 65, 10), ("left_winger", 72, 12, 11),
              ("right_winger", 72, 88, 7), ("striker", 85, 50, 9)],
    "4-2-3-1": [("goalkeeper", 5, 50, 1), ("left_back", 28, 12, 3), ("centre_back_l", 22, 38, 5),
                ("centre_back_r", 22, 62, 4), ("right_back", 28, 88, 2), ("defensive_mid_l", 40, 40, 6),
                ("defensive_mid_r", 40, 60, 8), ("attacking_mid", 65, 50, 10), ("left_winger", 70, 14, 11),
                ("right_winger", 70, 86, 7), ("striker", 85, 50, 9)],
    "4-4-2": [("goalkeeper", 5, 50, 1), ("left_back", 28, 12, 3), ("centre_back_l", 22, 38, 5),
              ("centre_back_r", 22, 62, 4), ("right_back", 28, 88, 2), ("left_mid", 56, 12, 11),
              ("central_mid_l", 48, 40, 8), ("central_mid_r", 48, 60, 6), ("right_mid", 56, 88, 7),
              ("striker_l", 82, 42, 10), ("striker_r", 82, 58, 9)],
    "3-5-2": [("goalkeeper", 5, 50, 1), ("centre_back_l", 22, 30, 5), ("centre_back", 18, 50, 4),
              ("centre_back_r", 22, 70, 6), ("left_wing_back", 50, 8, 3), ("right_wing_back", 50, 92, 2),
              ("defensive_mid", 40, 50, 14), ("central_mid_l", 52, 36, 8), ("central_mid_r", 52, 64, 10),
              ("striker_l", 82, 42, 11), ("striker_r", 82, 58, 9)],
    "4-1-4-1": [("goalkeeper", 5, 50, 1), ("left_back", 28, 12, 3), ("centre_back_l", 22, 38, 5),
                ("centre_back_r", 22, 62, 4), ("right_back", 28, 88, 2), ("defensive_mid", 38, 50, 6),
                ("left_mid", 60, 12, 11), ("central_mid_l", 55, 38, 8), ("central_mid_r", 55, 62, 10),
                ("right_mid", 60, 88, 7), ("striker", 85, 50, 9)],
}

DEFENDERS = {"left_back", "right_back", "centre_back_l", "centre_back_r", "centre_back", "left_wing_back",
             "right_wing_back"}
MIDFIELD = {"defensive_mid", "defensive_mid_l", "defensive_mid_r", "central_mid_l", "central_mid_r",
            "attacking_mid", "left_mid", "right_mid"}
FORWARDS = {"left_winger", "right_winger", "striker", "striker_l", "striker_r"}


def position_of(role: str) -> str:
    if role == "goalkeeper":
        return "GK"
    if role in DEFENDERS:
        return "DF"
    if role in MIDFIELD:
        return "MF"
    return "FW"


# Backups per line, beyond the XI (24 players in all).
BACKUPS = {"GK": 2, "DF": 4, "MF": 4, "FW": 3}

FIRST = ["Tomas", "Idris", "Lukas", "Kofi", "Mateo", "Jonas", "Ravi", "Emil", "Nico", "Sami", "Oskar",
         "Dario", "Felix", "Hugo", "Anders", "Kwame", "Luca", "Mika", "Theo", "Yusuf", "Arlo", "Bram",
         "Cyril", "Dev", "Eero", "Fabian", "Gael", "Hamid", "Ilan", "Jarek", "Kenji", "Lior", "Marek",
         "Nils", "Omar", "Pavel", "Quentin", "Rafael", "Soren", "Tariq", "Ugo", "Viktor", "Wim", "Xavi",
         "Yann", "Zoran", "Aiden", "Bastian", "Caio", "Dimitri", "Elias", "Florin", "Goran", "Henrik",
         "Ismael", "Joaquim", "Kai", "Leon", "Malik", "Noah", "Otto", "Pedro", "Rui", "Stellan", "Tiago",
         "Umar", "Vito", "Wes", "Yaro", "Zeki", "Ansel", "Bodhi", "Callum", "Darian", "Ennis", "Finn"]
_SYL_A = ["Var", "Kes", "Hol", "Dra", "Mer", "Tor", "Ash", "Bel", "Cor", "Dun", "Fen", "Gar", "Hart",
          "Lin", "Mor", "Nor", "Pell", "Quin", "Rav", "Sel", "Thal", "Ul", "Wen", "Yar", "Brek", "Cal",
          "Ost", "Rud", "Sten", "Vel"]
_SYL_B = ["holt", "row", "mere", "vik", "ard", "ley", "ston", "brook", "dal", "fen", "gard", "hurst",
          "ik", "mont", "nik", "ova", "ren", "sen", "tani", "uli", "wick", "zek", "elle", "ado", "esco",
          "ström", "ach", "ford", "lund", "oni"]


def name_pool(rng: random.Random):
    """Infinite generator of unique invented full names."""
    used = set()
    while True:
        nm = f"{rng.choice(FIRST)} {rng.choice(_SYL_A)}{rng.choice(_SYL_B)}"
        if nm not in used:
            used.add(nm)
            yield nm


@dataclass
class Player:
    player_id: str
    team_id: str
    name: str
    shirt: int
    position: str
    role: str                  # natural role (the formation slot a first choice holds, or covers)
    hx: float
    hy: float
    first_choice: bool = True
    finishing: float = 1.0
    usage: float = 1.0
    cross_mult: float = 1.0
    wide_forward: bool = False
    set_piece_taker: bool = False
    delivery: float = 1.0      # scales a set-piece taker's corner delivery bonus
    penalty_taker: bool = False
    aggression: float = 1.0    # foul propensity
    trap_flag: str = ""


def _role_traits(rng: random.Random, role: str) -> dict:
    pos = position_of(role)
    fin = {"GK": 0.4, "DF": rng.uniform(0.75, 0.9), "MF": rng.uniform(0.85, 1.0), "FW": rng.uniform(0.95, 1.1)}[pos]
    return dict(finishing=round(fin, 3), aggression=round(rng.uniform(0.7, 1.3) * (1.15 if pos == "DF" else 1.0), 3))


def build_squad(rng: random.Random, team, names, overrides: dict | None = None) -> list[Player]:
    """24 players: the XI of `team.formation` (classic shirt numbers) then backups (other numbers).
    PLAYER_TRAITS (and `overrides`, keyed the same way) apply to the first choice in that role."""
    from .config import PLAYER_TRAITS
    slots = FORMATIONS[team.formation]
    out, shirts = [], set()
    for role, hx, hy, shirt in slots:
        p = Player(f"{team.code}_{shirt:02d}", team.team_id, next(names), shirt, position_of(role), role, hx, hy,
                   **_role_traits(rng, role))
        traits = {**PLAYER_TRAITS.get((team.code, role), {}), **(overrides or {}).get((team.code, role), {})}
        for k, v in traits.items():
            setattr(p, k, v)
        if p.trap_flag:
            p.aggression = 0.5           # planted players should not lose matches to suspensions
        shirts.add(shirt)
        out.append(p)
    # penalty taker: the striker (or the most advanced player)
    max(out, key=lambda p: (p.position == "FW", p.hx)).penalty_taker = True
    free = [n for n in range(12, 46) if n not in shirts]
    rng.shuffle(free)
    by_pos = {}
    for role, hx, hy, _ in slots:
        by_pos.setdefault(position_of(role), []).append((role, hx, hy))
    for pos, n in BACKUPS.items():
        roles = by_pos[pos]
        for i in range(n):
            role, hx, hy = roles[(i * 2 + 1) % len(roles)] if pos != "GK" else roles[0]
            shirt = free.pop()
            p = Player(f"{team.code}_{shirt:02d}", team.team_id, next(names), shirt, pos, role, hx, hy,
                       first_choice=False, usage=round(rng.uniform(0.8, 1.0), 3), **_role_traits(rng, role))
            out.append(p)
    return out


@dataclass
class Lineup:
    xi: list                    # [(Player, role, hx, hy)] one per formation slot
    bench: list                 # [Player]


@dataclass
class SquadManager:
    """Availability across the season: suspensions, injuries, yellow accumulation and fatigue."""
    squads: dict                                  # team_id -> [Player]
    rng: random.Random
    banned: dict = field(default_factory=dict)    # player_id -> matches still to miss
    injured: dict = field(default_factory=dict)   # player_id -> matches still to miss
    yellows: dict = field(default_factory=dict)   # player_id -> season yellow count
    last_played: dict = field(default_factory=dict)   # team_id -> date of its previous match

    BENCH = 9
    REST_P = 0.03                # chance a first choice is rested in a normal week
    REST_P_CONGESTED = 0.12      # ... after a match within the last four days

    def matchday(self, team, d: date | None = None) -> Lineup:
        squad = self.squads[team.team_id]
        congested = (d is not None and team.team_id in self.last_played
                     and (d - self.last_played[team.team_id]).days <= 4)
        rest_p = self.REST_P_CONGESTED if congested else self.REST_P
        out = lambda p: self.banned.get(p.player_id, 0) > 0 or self.injured.get(p.player_id, 0) > 0
        used, xi = set(), []
        for role, hx, hy, _ in FORMATIONS[team.formation]:
            first = next(p for p in squad if p.first_choice and p.role == role)
            pick = first
            rested = (not first.trap_flag and first.role != "goalkeeper" and self.rng.random() < rest_p)
            if out(first) or rested:
                cover = [p for p in squad if not p.first_choice and not out(p) and p.player_id not in used]
                same = [p for p in cover if p.role == role] or [p for p in cover if p.position == position_of(role)]
                pick = same[0] if same else first
            used.add(pick.player_id)
            xi.append((pick, role, hx, hy))
        rest = [p for p in squad if p.player_id not in used and not out(p)]
        gk = [p for p in rest if p.position == "GK"][:1]
        others = sorted((p for p in rest if p.position != "GK"), key=lambda p: (not p.first_choice, p.shirt))
        bench = gk + others[: self.BENCH - len(gk)]
        return Lineup(xi, bench)

    def record(self, team_id: str, d: date | None, cards: list, injuries: list, played: set):
        """After a match: serve bans, add new ones, age injuries."""
        for pid in list(self.banned):
            if pid.startswith(self._code(team_id)):
                self.banned[pid] -= 1
                if self.banned[pid] <= 0:
                    del self.banned[pid]
        for pid in list(self.injured):
            if pid.startswith(self._code(team_id)):
                self.injured[pid] -= 1
                if self.injured[pid] <= 0:
                    del self.injured[pid]
        for pid, kind in cards:
            if kind in ("red", "second_yellow"):
                self.banned[pid] = self.banned.get(pid, 0) + 1
            if kind in ("yellow", "second_yellow"):
                self.yellows[pid] = self.yellows.get(pid, 0) + 1
                if self.yellows[pid] == 5:
                    self.banned[pid] = self.banned.get(pid, 0) + 1
        for pid, n in injuries:
            self.injured[pid] = n
        if d is not None:
            self.last_played[team_id] = d

    def _code(self, team_id: str) -> str:
        return self.squads[team_id][0].player_id.split("_")[0] + "_"
