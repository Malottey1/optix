"""Season-level calibration targets for the synthetic league (realism v2).

Era: recent Premier League seasons (2022/23-2024/25). Every target is a RANGE, never a point. Each one
names its source: a public page (URL in SOURCES) or "approximate" (a wide football-knowledge range,
not a measurement). Targets are checked on plain aggregates of the generated tables (matches, events,
passes, shots, lineups), never on simulator internals, so they test what a consumer of the data sees.

Sampling allowance: a 40-match season cannot pin a share to a few points, so a measured value passes
when it lies inside [lo - a, hi + a] with a = 2 * sd / sqrt(n), where sd is the target's approximate
per-observation standard deviation and n the number of observations (matches, team-matches, shots,
passes or goals; see `per`). On the full league (380 matches) a is small. Season-shape targets
(table spread, correlations between teams, players used over 38 matches) need a full league and
are skipped below `min_teams`.

Deliberately NOT encoded: streaks, scoreline caps or anything else that only shows up in tiny samples.
"""
from __future__ import annotations

import math
import statistics as st
from collections import Counter, defaultdict

SOURCES = {
    "goals": "The Analyst: 2.85 (22/23), 3.28 (23/24) goals per match "
             "https://theanalyst.com/articles/numbers-behind-premier-league-goal-explosion ; 2024/25: 2.93 "
             "https://en.wikipedia.org/wiki/2024%E2%80%9325_Premier_League",
    "results": "home wins about 48% in 22/23 https://www.premierleague.com/news/2916832 ; 24/25 split "
               "40.8/24.5/34.7% https://www.fiso.co.uk/premier-league-scoring-trends-2024-25-season-vs-2025-26-gw25-whats-changed/",
    "fouls": "about 22-23 fouls awarded per match https://www.olbg.com/blogs/men-middle-premier-league-referee-performances",
    "cards": "The Analyst: 4.2 yellows per match in 23/24 (record), 5.1 early 24/25 "
             "https://theanalyst.com/articles/new-premier-league-records-on-the-cards",
    "penalties": "107 penalties in 23/24 (0.28 per match) https://premierleague.com/news/4029218 ; about 0.23 "
                 "part-way through 24/25 https://theanalyst.com/articles/who-has-won-the-most-penalties-premier-league",
    "set_pieces": "19.8% of goals from set pieces excluding penalties in 23/24 "
                  "https://www.fantasyfootballscout.co.uk/2025/10/18/just-how-important-are-set-pieces-in-fpl ; "
                  "penalties add roughly 7-9 points (approximate)",
    "added_time": "507 s (22/23) and 702 s (23/24) played beyond 90 minutes https://www.premierleague.com/news/3860720",
    "ball_in_play": "54:49 (22/23), 58:11 (23/24) https://theanalyst.com/articles/match-time-ball-in-play-referees-stats",
    "goal_timing": "26.3% of goals after minute 75 in one season https://premierleague.com/news/3871035 ; "
                   "the rest approximate",
    "approximate": "approximate, football knowledge (wide range, not a measurement)",
}

# name -> lo, hi (inclusive), unit, per (what n counts), sd (per observation), source, definition,
# min_teams (season-shape targets only)
_T = dict
TARGETS = {
    # --- results ---
    "goals_per_match": _T(lo=2.6, hi=3.3, unit="goals", per="matches", sd=1.7, source="goals",
                          definition="mean of home_score + away_score"),
    "home_win_share": _T(lo=0.40, hi=0.49, unit="share", per="matches", sd=0.49, source="results",
                         definition="matches won by the home team / matches"),
    "draw_share": _T(lo=0.20, hi=0.28, unit="share", per="matches", sd=0.43, source="results",
                     definition="drawn matches / matches"),
    "away_win_share": _T(lo=0.28, hi=0.36, unit="share", per="matches", sd=0.47, source="results",
                         definition="matches won by the away team / matches"),
    "home_goal_edge": _T(lo=0.15, hi=0.45, unit="goals", per="matches", sd=1.9, source="approximate",
                         definition="mean of home_score - away_score"),
    "goals_dispersion": _T(lo=0.95, hi=1.30, unit="ratio", per="team_matches", sd=1.0, source="approximate",
                           definition="variance / mean of goals per team per match"),
    "goals_first_15_share": _T(lo=0.08, hi=0.16, unit="share", per="goals", sd=0.33, source="goal_timing",
                               definition="goals in football minutes 0-14 / goals"),
    "goals_last_15_share": _T(lo=0.19, hi=0.30, unit="share", per="goals", sd=0.42, source="goal_timing",
                              definition="goals in football minute 75 or later of the second half (incl. added time) / goals"),
    # --- shooting ---
    "shots_per_team": _T(lo=11.0, hi=14.0, unit="shots", per="team_matches", sd=4.5, source="approximate",
                         definition="shots / team-matches"),
    "on_target_share": _T(lo=0.32, hi=0.37, unit="share", per="shots", sd=0.47, source="approximate",
                          definition="shots with result goal or saved / shots"),
    "blocked_share": _T(lo=0.20, hi=0.30, unit="share", per="shots", sd=0.43, source="approximate",
                        definition="shots with result blocked / shots"),
    "conversion": _T(lo=0.09, hi=0.12, unit="share", per="shots", sd=0.31, source="approximate",
                     definition="goals from shots / shots"),
    "xg_per_shot": _T(lo=0.09, hi=0.12, unit="xG", per="shots", sd=0.15, source="approximate",
                      definition="sum of xg / shots"),
    "goals_vs_xg": _T(lo=-0.10, hi=0.10, unit="relative", per="goals", sd=1.0, source="approximate",
                      definition="goals from shots / sum of xg - 1"),
    "inside_box_share": _T(lo=0.60, hi=0.72, unit="share", per="shots", sd=0.47, source="approximate",
                           definition="shots from inside the box (x >= 84, 22 <= y <= 78) / shots"),
    "header_share": _T(lo=0.11, hi=0.19, unit="share", per="shots", sd=0.36, source="approximate",
                       definition="shots with body_part head / shots"),
    "mean_shot_distance_m": _T(lo=15.5, hi=18.5, unit="m", per="shots", sd=7.0, source="approximate",
                               definition="mean shot_distance_m"),
    "penalties_per_match": _T(lo=0.20, hi=0.32, unit="penalties", per="matches", sd=0.5, source="penalties",
                              definition="shots with shot_type penalty / matches"),
    "set_piece_goal_share": _T(lo=0.20, hi=0.33, unit="share", per="goals", sd=0.43, source="set_pieces",
                               definition="goals whose shot event has play_pattern set_piece (corners, free kicks, "
                                          "penalties) / goals"),
    # --- set pieces and crossing ---
    "corners_per_team": _T(lo=4.5, hi=5.8, unit="corners", per="team_matches", sd=2.7, source="approximate",
                           definition="passes with pass_type corner / team-matches"),
    "crosses_per_team": _T(lo=10.0, hi=20.0, unit="crosses", per="team_matches", sd=6.0, source="approximate",
                           definition="passes with pass_type cross / team-matches"),
    "cross_completion": _T(lo=0.20, hi=0.30, unit="share", per="crosses", sd=0.43, source="approximate",
                           definition="completed crosses / crosses"),
    # --- passing ---
    "passes_per_team": _T(lo=400.0, hi=520.0, unit="passes", per="team_matches", sd=110.0, source="approximate",
                          definition="pass events excluding throw-ins / team-matches"),
    "pass_accuracy": _T(lo=0.79, hi=0.85, unit="share", per="team_matches", sd=0.05, source="approximate",
                        definition="completed / attempted passes excluding throw-ins"),
    "back_pass_share": _T(lo=0.10, hi=0.20, unit="share", per="team_matches", sd=0.04, source="approximate",
                          definition="passes (excl. throw-ins, goal kicks, corners) whose direction is more than "
                                     "135 degrees from straight at goal / those passes"),
    "final_third_pass_share": _T(lo=0.18, hi=0.30, unit="share", per="team_matches", sd=0.06, source="approximate",
                                 definition="passes (excl. throw-ins) starting at x >= 66.7 / passes"),
    # --- defending ---
    "tackles_per_team": _T(lo=14.0, hi=21.0, unit="tackles", per="team_matches", sd=5.0, source="approximate",
                           definition="tackle events / team-matches"),
    "interceptions_per_team": _T(lo=7.0, hi=12.0, unit="interceptions", per="team_matches", sd=4.0,
                                 source="approximate", definition="interception events / team-matches"),
    "clearances_per_team": _T(lo=14.0, hi=26.0, unit="clearances", per="team_matches", sd=8.0,
                              source="approximate", definition="clearance events / team-matches"),
    # --- discipline ---
    "fouls_per_team": _T(lo=9.5, hi=12.5, unit="fouls", per="team_matches", sd=3.5, source="fouls",
                         definition="foul events / team-matches"),
    "yellows_per_match": _T(lo=3.3, hi=4.6, unit="cards", per="matches", sd=1.8, source="cards",
                            definition="card events with outcome yellow or second_yellow / matches"),
    "reds_per_match": _T(lo=0.04, hi=0.15, unit="cards", per="matches", sd=0.3, source="approximate",
                         definition="card events with outcome second_yellow or red / matches"),
    "offsides_per_team": _T(lo=1.4, hi=2.6, unit="offsides", per="team_matches", sd=1.5, source="approximate",
                            definition="offside events / team-matches"),
    # --- time ---
    "added_time_min": _T(lo=7.0, hi=13.0, unit="minutes", per="matches", sd=2.5, source="added_time",
                         definition="first-half plus second-half added time, from the half_end events"),
    "added_time_first_half_min": _T(lo=1.0, hi=4.0, unit="minutes", per="matches", sd=1.0, source="approximate",
                                    definition="first-half added time"),
    "added_time_second_half_min": _T(lo=4.0, hi=10.0, unit="minutes", per="matches", sd=1.8, source="approximate",
                                     definition="second-half added time"),
    "ball_in_play_min": _T(lo=54.0, hi=60.0, unit="minutes", per="matches", sd=4.0, source="ball_in_play",
                           definition="matches.ball_in_play_sec / 60"),
    "subs_per_team": _T(lo=3.0, hi=5.0, unit="substitutions", per="team_matches", sd=1.0, source="approximate",
                        definition="substitution events / team-matches"),
    # --- season shape (full league only) ---
    "ppda_league": _T(lo=8.0, hi=16.0, unit="ratio", per="teams", sd=2.5, source="approximate", min_teams=20,
                      definition="mean over teams of (opponent passes in their own 60% / tackles, interceptions "
                                 "and fouls in the opponent's 60%)"),
    "possession_sd_pp": _T(lo=5.0, hi=8.5, unit="pp", per="none", sd=0.0, source="approximate", min_teams=20,
                           definition="SD across teams of season possession (share of match passes)"),
    "team_pass_spread": _T(lo=1.45, hi=2.4, unit="ratio", per="none", sd=0.0, source="approximate", min_teams=20,
                           definition="highest / lowest team mean passes per match"),
    "champion_points": _T(lo=78.0, hi=95.0, unit="points", per="none", sd=0.0, source="approximate", min_teams=20,
                          definition="points of the top team (38 matches)"),
    "bottom_points": _T(lo=15.0, hi=35.0, unit="points", per="none", sd=0.0, source="approximate", min_teams=20,
                        definition="points of the bottom team"),
    "players_used_per_team": _T(lo=20.0, hi=30.0, unit="players", per="none", sd=0.0, source="approximate",
                                min_teams=20, definition="players with minutes > 0 per team over the season"),
    "corr_possession_shots": _T(lo=0.30, hi=1.0, unit="r", per="none", sd=0.0, source="approximate", min_teams=20,
                                definition="Pearson r across teams: season possession vs shots per match"),
    "corr_possession_pass_accuracy": _T(lo=0.50, hi=1.0, unit="r", per="none", sd=0.0, source="approximate",
                                        min_teams=20, definition="Pearson r: possession vs pass accuracy"),
    "corr_ppda_possession": _T(lo=-1.0, hi=-0.20, unit="r", per="none", sd=0.0, source="approximate", min_teams=20,
                               definition="Pearson r: PPDA vs possession (pressing sides keep the ball more)"),
}

# Targets the generator does not meet yet. Realism v2 removes them stage by stage: the calibration
# tests allow failures only from this set (a new failure fails), and tests/test_realism.py requires
# it to be empty at the end of realism v2.
NOT_YET_MODELLED: set = {
    "goals_dispersion", "added_time_first_half_min", "added_time_min", "added_time_second_half_min", "back_pass_share",
    "ball_in_play_min", "clearances_per_team", "corr_possession_shots", "corr_ppda_possession",
    "final_third_pass_share", "fouls_per_team", "header_share", "inside_box_share",
    "interceptions_per_team", "offsides_per_team", "on_target_share", "pass_accuracy", "passes_per_team",
    "penalties_per_match", "players_used_per_team", "possession_sd_pp", "ppda_league", "reds_per_match",
    "set_piece_goal_share", "subs_per_team", "team_pass_spread", "yellows_per_match",
}


def _f(v):
    return float(v) if v not in ("", None) else None


def pearson(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def in_box(x, y):
    return x >= 84.0 and 22.0 <= y <= 78.0


def season_stats(t: dict) -> dict:
    """Every calibration metric, plus the sample sizes the allowance needs, from table rows (dicts,
    values may be str or numbers). `t` holds matches, events, passes, shots and optionally lineups."""
    matches, events, passes, shots = t["matches"], t["events"], t["passes"], t["shots"]
    passes = passes if isinstance(passes, dict) else {p["event_id"]: p for p in passes}
    shots_by = shots if isinstance(shots, dict) else {s["event_id"]: s for s in shots}
    shots = list(shots_by.values())
    nm = len(matches)
    ntm = 2 * nm
    hs = [int(m["home_score"]) for m in matches]
    as_ = [int(m["away_score"]) for m in matches]
    home = {m["match_id"]: m["home_team_id"] for m in matches}
    teams = sorted({m["home_team_id"] for m in matches} | {m["away_team_id"] for m in matches})
    out, n = {}, {}

    out["goals_per_match"] = (sum(hs) + sum(as_)) / nm
    out["home_win_share"] = sum(h > a for h, a in zip(hs, as_)) / nm
    out["draw_share"] = sum(h == a for h, a in zip(hs, as_)) / nm
    out["away_win_share"] = sum(h < a for h, a in zip(hs, as_)) / nm
    out["home_goal_edge"] = (sum(hs) - sum(as_)) / nm
    g = hs + as_
    out["goals_dispersion"] = st.pvariance(g) / st.mean(g) if st.mean(g) else 0.0

    ev_by_id = {e["event_id"]: e for e in events}
    cnt = Counter()                       # (team, key) counts
    tm = defaultdict(Counter)             # (match, team) -> counts for season shape
    first_ev = {}
    for e in events:
        typ, tid, mid = e["event_type"], e["team_id"], e["match_id"]
        first_ev.setdefault((mid, int(e["period"])), e)
        c = tm[(mid, tid)]
        if typ == "pass":
            p = passes[e["event_id"]]
            pt = p["pass_type"]
            if pt == "throw_in":
                continue
            ok = e["outcome"] == "success"
            c["passes"] += 1
            c["passes_ok"] += ok
            xs, ys, xe, ye = (_f(e[k]) for k in ("x_start", "y_start", "x_end", "y_end"))
            if xs >= 66.7:
                c["f3"] += 1
            if pt not in ("goal_kick", "corner"):
                c["dir_n"] += 1
                ang = abs(math.degrees(math.atan2((ye - ys) * 0.68, (xe - xs) * 1.05)))
                c["back"] += ang > 135
            if pt == "corner":
                c["corners"] += 1
            if pt == "cross":
                c["crosses"] += 1
                c["crosses_ok"] += ok
            if xs < 60:
                c["own60_passes"] += 1
        elif typ in ("tackle", "interception", "clearance", "foul", "offside", "substitution"):
            c[typ] += 1
            if typ in ("tackle", "interception", "foul") and _f(e["x_start"]) >= 40:
                c["def_high"] += 1
        elif typ == "card":
            c["yellow"] += e["outcome"] in ("yellow", "second_yellow")
            c["red"] += e["outcome"] in ("second_yellow", "red")
        elif typ == "shot":
            c["shots"] += 1
    for (mid, tid), c in tm.items():
        for k, v in c.items():
            cnt[k] += v

    out["passes_per_team"] = cnt["passes"] / ntm
    out["pass_accuracy"] = cnt["passes_ok"] / max(cnt["passes"], 1)
    out["back_pass_share"] = cnt["back"] / max(cnt["dir_n"], 1)
    out["final_third_pass_share"] = cnt["f3"] / max(cnt["passes"], 1)
    out["corners_per_team"] = cnt["corners"] / ntm
    out["crosses_per_team"] = cnt["crosses"] / ntm
    out["cross_completion"] = cnt["crosses_ok"] / max(cnt["crosses"], 1)
    out["tackles_per_team"] = cnt["tackle"] / ntm
    out["interceptions_per_team"] = cnt["interception"] / ntm
    out["clearances_per_team"] = cnt["clearance"] / ntm
    out["fouls_per_team"] = cnt["foul"] / ntm
    out["offsides_per_team"] = cnt["offside"] / ntm
    out["subs_per_team"] = cnt["substitution"] / ntm
    out["yellows_per_match"] = cnt["yellow"] / nm
    out["reds_per_match"] = cnt["red"] / nm
    n["crosses"] = cnt["crosses"]

    # shooting
    ns = len(shots)
    res = Counter(s["shot_result"] for s in shots)
    goals_from_shots = res["goal"]
    xg = sum(_f(s["xg"]) for s in shots)
    out["shots_per_team"] = ns / ntm
    out["on_target_share"] = (res["goal"] + res["saved"]) / ns
    out["blocked_share"] = res["blocked"] / ns
    out["conversion"] = goals_from_shots / ns
    out["xg_per_shot"] = xg / ns
    out["goals_vs_xg"] = goals_from_shots / xg - 1
    out["inside_box_share"] = sum(in_box(_f(ev_by_id[s["event_id"]]["x_start"]), _f(ev_by_id[s["event_id"]]["y_start"]))
                                  for s in shots) / ns
    out["header_share"] = sum(ev_by_id[s["event_id"]]["body_part"] == "head" for s in shots) / ns
    out["mean_shot_distance_m"] = sum(_f(s["shot_distance_m"]) for s in shots) / ns
    out["penalties_per_match"] = sum(s["shot_type"] == "penalty" for s in shots) / nm
    goal_ev = [ev_by_id[s["event_id"]] for s in shots if s["shot_result"] == "goal"]
    ng = max(len(goal_ev), 1)
    out["set_piece_goal_share"] = sum(e["play_pattern"] == "set_piece" for e in goal_ev) / ng
    out["goals_first_15_share"] = sum(int(e["period"]) == 1 and int(e["minute"]) < 15 for e in goal_ev) / ng
    out["goals_last_15_share"] = sum(int(e["period"]) == 2 and int(e["minute"]) >= 75 for e in goal_ev) / ng
    n.update(shots=ns, goals=len(goal_ev))

    # time: added time from half_end events; ball in play from the match table
    a1, a2 = [], []
    ends = defaultdict(dict)
    for e in events:
        if e["event_type"] == "half_end":
            ends[e["match_id"]][int(e["period"])] = _f(e["clock_sec"])
    for m in matches:
        d = ends.get(m["match_id"], {})
        h2 = first_ev.get((m["match_id"], 2))
        a1.append(((d[1] - 2700) / 60) if 1 in d else 0.0)
        a2.append(((d[2] - _f(h2["clock_sec"]) - 2700) / 60) if (2 in d and h2) else 0.0)
    out["added_time_first_half_min"] = st.mean(a1)
    out["added_time_second_half_min"] = st.mean(a2)
    out["added_time_min"] = st.mean(a1) + st.mean(a2)
    bip = [_f(m.get("ball_in_play_sec")) for m in matches]
    out["ball_in_play_min"] = st.mean(b / 60 if b is not None else 90.0 for b in bip)

    # season shape (team level)
    poss, shots_pm, acc, ppda, passes_pm = {}, {}, {}, {}, {}
    pts = Counter()
    for m in matches:
        h, a, x, y = m["home_team_id"], m["away_team_id"], int(m["home_score"]), int(m["away_score"])
        pts[h] += 3 if x > y else (1 if x == y else 0)
        pts[a] += 3 if y > x else (1 if x == y else 0)
    for tid in teams:
        pos, ps, sh, ok, pp = [], 0, 0, 0, []
        for m in matches:
            if tid not in (m["home_team_id"], m["away_team_id"]):
                continue
            mid = m["match_id"]
            oid = m["away_team_id"] if m["home_team_id"] == tid else m["home_team_id"]
            c, o = tm[(mid, tid)], tm[(mid, oid)]
            pos.append(c["passes"] / max(c["passes"] + o["passes"], 1))
            ps += c["passes"]
            sh += c["shots"]
            ok += c["passes_ok"]
            pp.append(o["own60_passes"] / max(c["def_high"], 1))
        k = len(pos)
        poss[tid], passes_pm[tid], shots_pm[tid] = st.mean(pos), ps / k, sh / k
        acc[tid], ppda[tid] = ok / max(ps, 1), st.mean(pp)
    out["ppda_league"] = st.mean(ppda.values())
    out["possession_sd_pp"] = st.pstdev(poss.values()) * 100
    out["team_pass_spread"] = max(passes_pm.values()) / max(min(passes_pm.values()), 1)
    out["champion_points"] = max(pts.values())
    out["bottom_points"] = min(pts.values())
    lu = t.get("lineups")
    if lu:
        used = defaultdict(set)
        for r in lu:
            if _f(r["minutes_played"]) and _f(r["minutes_played"]) > 0:
                used[r["team_id"]].add(r["player_id"])
        out["players_used_per_team"] = st.mean(len(v) for v in used.values())
    else:
        used = defaultdict(set)
        for e in events:
            if e["player_id"]:
                used[e["team_id"]].add(e["player_id"])
        out["players_used_per_team"] = st.mean(len(v) for v in used.values())
    ts = list(teams)
    out["corr_possession_shots"] = pearson([poss[x] for x in ts], [shots_pm[x] for x in ts])
    out["corr_possession_pass_accuracy"] = pearson([poss[x] for x in ts], [acc[x] for x in ts])
    out["corr_ppda_possession"] = pearson([ppda[x] for x in ts], [poss[x] for x in ts])
    n.update(matches=nm, team_matches=ntm, teams=len(teams), passes=cnt["passes"])
    out["_n"] = n
    return out


def check(stats: dict) -> dict:
    """Per-metric result: measured value, range, sampling allowance, applicability and pass/fail."""
    n = stats["_n"]
    res = {}
    for k, t in TARGETS.items():
        applicable = n["teams"] >= t.get("min_teams", 0)
        nn = n.get(t["per"], 0)
        allow = 2 * t["sd"] / math.sqrt(nn) if (t["sd"] and nn) else 0.0
        v = stats[k]
        res[k] = dict(measured=round(v, 4), lo=t["lo"], hi=t["hi"], allowance=round(allow, 4),
                      applicable=applicable, passed=bool(t["lo"] - allow <= v <= t["hi"] + allow))
    return res


def expected() -> dict:
    """The targets as recorded in ground_truth.json."""
    return {k: dict(tolerance=[t["lo"], t["hi"]], unit=t["unit"], per=t["per"], sd=t["sd"],
                    source=SOURCES[t["source"]], definition=t["definition"],
                    **({"min_teams": t["min_teams"]} if "min_teams" in t else {}))
            for k, t in TARGETS.items()}


def measured(stats: dict) -> dict:
    return {k: round(v, 4) for k, v in stats.items() if not k.startswith("_")}


def failing(stats: dict) -> set:
    """Applicable targets that the measured stats miss."""
    return {k for k, r in check(stats).items() if r["applicable"] and not r["passed"]}
