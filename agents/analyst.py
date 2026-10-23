"""Analyst agent: decides WHEN to look and WHAT claim to propose, and revises blocked claims.

It never computes a number: every claim comes from engine.claims.build_claim (or
engine.matchup.matchup_claim) over the events ingested so far. Its own logic is only triggers
(checkpoints, thresholds on engine values, cooldowns) and revision strategies.

Triggers (deterministic, in match clock):
  * kickoff: season matchup preview for each direction (attacker lane vs defender completion),
    computed in prepare() before the first event;
  * every CHECKPOINT_SEC: each team's field tilt over the last TILT_WINDOW_SEC when >= MIN_TILT
    (once per team per TILT_COOLDOWN_SEC; FT_TILT_COOLDOWN_SEC at full time);
  * at half time and full time: each team's xG so far (>= MIN_SHOTS_FOR_XG shots), top chance
    creator (>= MIN_CHANCES), top forward passer (>= MIN_FORWARD), PPDA;
  * every 30 minutes: the rhythm wave (last 15 minutes);
  * every minute: momentum; a sign change with |momentum| >= MOMENTUM_SWING;
  * a completed pass adding >= THREAT_PASS_XT expected threat (one per team per cooldown);
  * a player's completed passes reaching a PASS_MILESTONES value;
  * at half time and full time, the tactical patterns (engine/patterns) found so far and the naive
    claims those patterns can make misleading (lane share, crosses, final-third volume and losses,
    fouls, a forward's touches); they are ranked (novelty against the team's previous two matches,
    when a history is given) and capped per family (rank_candidates).
First attempts are plain (the headline number only); the Verifier says what context a sentence
needs and revise() adds it.
"""
from __future__ import annotations

from engine import flow as F
from engine import metrics as M
from engine import patterns as PAT
from engine import threat as T
from engine.claims import SIDE_LANES, build_claim, build_pattern_claim
from engine.matchup import matchup_claim
from engine.rules import PATTERN_RULES
from engine.tables import match_events

from .messages import ClaimProposal

CHECKPOINT_SEC = 900
TILT_WINDOW_SEC = 1800
MIN_TILT = 60.0
TILT_COOLDOWN_SEC = 1800
# at the final whistle the cooldown drops to one checkpoint, so the closing spell (often a
# trailing side's push in stoppage time) gets its own window instead of falling in the gap
FT_TILT_COOLDOWN_SEC = 900
MIN_SHOTS_FOR_XG = 5
MIN_CHANCES = 3
MIN_FORWARD = 15
RHYTHM_EVERY_SEC = 1800
MOMENTUM_STEP_SEC = 60
MOMENTUM_SWING = 40.0
MOMENTUM_WINDOW_SEC = 600
MOMENTUM_COOLDOWN_SEC = 900
THREAT_PASS_XT = 0.025
THREAT_COOLDOWN_SEC = 900
PASS_MILESTONES = (50, 75)
MAX_ATTEMPTS = 3
# naive claims (the raw statistic a pattern can show to be misleading)
MIN_SIDE_SHARE = 55.0          # attack_side_share: share of entries on one side
MIN_SIDE_ENTRIES = 10
MIN_CROSSES = 10
MIN_F3_PASSES = 40
MIN_F3_LOSSES = 10
MIN_FOULS = 10
MAX_QUIET_TOUCHES = 25         # a forward with this many touches or fewer "had a quiet game"
# ranking and caps of pattern and naive candidates (docs/patterns.md, "Novelty and repetition")
FAMILY_CAP = 3                 # surfaced claims per family per match
PER_SUMMARY = 6                # candidates surfaced at each half-time / full-time summary
NOVELTY_WEIGHT = 0.5           # a family+team shown in the team's previous two matches ...
NOVELTY_CHANGE = 0.25          # ... unless its magnitude changed by at least this much
NOVELTY_MIN_STEP = 2.0         # ... and by at least this much in absolute terms (a count of 1 -> 2 is noise)
SURFACE_MIN_SCORE = 0.6       # below this (a down-weighted repeat) a candidate is held back
MIN_ISOLATION_F3_SHARE = 10.0  # % of final-third passes in touchline spells to publish P3
PATTERN_TEMPLATES = {f: "pattern." + f[4:] for f in PAT.FAMILIES}
PATTERN_PARAMS = {
    "pat_bait_switch": ("amount", "build_passes", "shots", "xg"),
    "pat_cutback": ("amount", "xg_per_shot", "cross_xg_per_shot"),
    "pat_flank_isolation": ("amount", "f3_share", "shots"),
    "pat_elastic_low_block": ("opp_tilt", "minutes", "outside_share", "opp_shots", "amount"),
    "pat_counter_press": ("amount", "losses", "median_regain_sec"),
    "pat_rest_defence": ("amount", "xg", "tilt"),
    "pat_starved_finisher": ("amount", "touch_line", "unpressured_shots", "xg"),
    "pat_tactical_fouling": ("amount", "losses", "rate", "league_rate"),
}

# a family whose finding can have zero of some count is phrased without it: (value, suffix, params dropped)
PATTERN_ZERO_VARIANTS = {"pat_cutback": ("cross_shots", ".no_cross", ("cross_xg_per_shot",)),
                         "pat_bait_switch": ("shots", ".no_shot", ("shots", "xg")),
                         "pat_flank_isolation": ("shots", ".no_shot", ("shots",))}


def pattern_template(f) -> tuple:
    """(template key, param names) for a finding: '0 shots, 0 xG' is never written."""
    key, keys = PATTERN_TEMPLATES[f.family], PATTERN_PARAMS[f.family]
    z = PATTERN_ZERO_VARIANTS.get(f.family)
    if z and not f.values[z[0]]:
        key, keys = key + z[1], tuple(k for k in keys if k not in z[2])
    return key, keys


# rule -> (revised template, params the revision adds, extra compute params)
REVISIONS = {
    "field_tilt_with_lead": ("field_tilt.trailing_vs_deep_block", ("box_entries", "team_f3_passes"), {}),
    "shot_spam": ("xg.volume_vs_value", ("shots", "xg_per_shot"), {}),
    "small_sample_xg": ("xg.small_sample", ("shots",), {}),
    "set_piece_inflation": ("chances_created.split", ("open_play", "set_piece"), {}),
    "wide_forward_passes": ("forward_passes.wide_low_threat", ("pass_quality_ratio",), {}),
    "ppda_alone": ("ppda.with_press_intensity", ("press_intensity",), {"with_press_intensity": True}),
    # pattern trap rules (engine/rules/ctx_*.py)
    "ctx_attack_side_vs_finish_side": ("attack_side.finished_other_side", ("team_shots", "opposite_shot_share"),
                                       {"with_finish": True}),
    "ctx_crosses_vs_cutbacks": ("crosses.with_cutbacks", ("cutbacks", "cutback_xg_per_shot", "cross_xg_per_shot"),
                                {"with_cutbacks": True}),
    "ctx_volume_without_central_access": ("f3_volume.touchline_spells",
                                          ("isolation_spells", "isolation_share", "box_entries"),
                                          {"with_isolation": True}),
    "ctx_tilt_without_access": ("field_tilt.low_block_outside_box",
                                ("team_shots", "outside_shot_share", "team_xg_per_shot"), {"with_access": True}),
    "ctx_losses_vs_immediate_regain": ("f3_losses.won_back", ("regains_4s", "regain_share"), {"with_regains": True}),
    "ctx_dominance_with_transition_exposure": ("field_tilt.counters_conceded",
                                               ("counter_shots_conceded", "counter_xg_conceded"),
                                               {"with_transition": True}),
    "ctx_fouls_clustered_after_losses": ("fouls.after_losses", ("fouls_after_losses", "after_loss_share"),
                                         {"with_after_losses": True}),
}
# two rules firing together on one claim: the template that says both (else the claim is dropped,
# never phrased with a template missing one rule's numbers)
COMBINED_REVISIONS = {frozenset({"ctx_tilt_without_access", "ctx_dominance_with_transition_exposure"}):
                      "field_tilt.low_block_and_counters"}
STRATEGY = {"field_tilt_with_lead": "add_game_state", "shot_spam": "add_shot_quality",
            "small_sample_xg": "add_sample_size", "set_piece_inflation": "split_open_play_set_piece",
            "wide_forward_passes": "add_pass_quality", "ppda_alone": "add_press_intensity",
            "ctx_attack_side_vs_finish_side": "add_finish_side", "ctx_crosses_vs_cutbacks": "add_cutbacks",
            "ctx_volume_without_central_access": "add_touchline_spells", "ctx_tilt_without_access": "add_shot_origin",
            "ctx_losses_vs_immediate_regain": "add_regains", "ctx_dominance_with_transition_exposure": "add_counters",
            "ctx_fouls_clustered_after_losses": "add_fouls_after_losses"}
NOT_REVISABLE = {"causal_claim", "causal_red_card", "single_match_fatigue", "ctx_low_volume_high_quality"}


def family_of(spec: dict) -> str:
    """The claim family of a pattern or naive candidate: its metric (pat_* or the naive metric)."""
    return spec["metric"]


def _changed(new: float, old) -> bool:
    return bool(old) and abs(new - old) / abs(old) >= NOVELTY_CHANGE and abs(new - old) >= NOVELTY_MIN_STEP


def rank_candidates(cands: list, history: dict | None, counts: dict, cap: int = FAMILY_CAP,
                    per_summary: int = PER_SUMMARY, shown: dict | None = None) -> list:
    """Order and cap pattern and naive candidates. cands: dicts with family, team_id, magnitude,
    score. A family+team shown in either of the team's previous two matches (history: team_id ->
    list of {family: magnitude}, oldest first) has its score multiplied by NOVELTY_WEIGHT unless the
    magnitude changed by >= NOVELTY_CHANGE; a candidate whose score ends below SURFACE_MIN_SCORE is
    held back (so an unchanged repeat is not shown again). Then the best candidate of each family comes before
    the second-best of any family, at most `cap` per family over the match (counts is updated) and
    `per_summary` in all. shown: (family, team_id, key) -> magnitude already surfaced earlier in
    this match (updated); such a candidate is left out unless its magnitude changed by >=
    NOVELTY_CHANGE, so the full-time summary does not repeat the half-time one. Ranking only:
    nothing here changes a claim."""
    shown = {} if shown is None else shown
    cands = [c for c in cands if (c["family"], c["team_id"], c.get("key", "")) not in shown
             or _changed(c["magnitude"], shown[(c["family"], c["team_id"], c.get("key", ""))])]
    for c in cands:
        w = 1.0
        for prev in (history or {}).get(c["team_id"], [])[-2:]:
            if c["family"] in prev:
                old = prev[c["family"]]
                if not _changed(c["magnitude"], old):
                    w = NOVELTY_WEIGHT
        c["rank_score"] = c["score"] * w
    # a repeat with an unchanged magnitude ends below the floor: it is held back, not shown again
    cands = [c for c in cands if c["rank_score"] >= SURFACE_MIN_SCORE]
    by_fam: dict = {}
    for c in sorted(cands, key=lambda c: (-c["rank_score"], c["family"], c["team_id"], c.get("key", ""))):
        by_fam.setdefault(c["family"], []).append(c)
    out, rnd_ = [], 0
    while len(out) < per_summary and any(len(v) > rnd_ for v in by_fam.values()):
        tier = sorted((v[rnd_] for v in by_fam.values() if len(v) > rnd_),
                      key=lambda c: (-c["rank_score"], c["family"], c["team_id"], c.get("key", "")))
        for c in tier:
            if len(out) >= per_summary:
                break
            if counts.get(c["family"], 0) < cap:
                counts[c["family"]] = counts.get(c["family"], 0) + 1
                shown[(c["family"], c["team_id"], c.get("key", ""))] = c["magnitude"]
                out.append(c)
        rnd_ += 1
    return out


class AnalystAgent:
    name = "analyst"

    def __init__(self, log, match_ds, season_ds, history: dict | None = None):
        """history: team_id -> the families (with magnitudes) surfaced in its previous matches, oldest
        first, for novelty ranking; None for a standalone match (no adjustment)."""
        self.log, self.ds, self.season, self.history = log, match_ds, season_ds, history
        self.family_counts: dict = {}
        self.shown: dict = {}                  # (family, team_id, key) -> magnitude surfaced this match
        self.grid = T.xt_grid(match_ds)
        self._next_checkpoint = CHECKPOINT_SEC
        self._next_momentum = MOMENTUM_STEP_SEC
        self._next_rhythm = RHYTHM_EVERY_SEC
        self._half_done = False
        self._kicked_off = False
        self._pre_match: list | None = None

    def prepare(self, state) -> None:
        """Pre-match work, before the first event: the season preview claims and the season
        baselines every later claim reuses (xT grid, league pass-quality share)."""
        T.league_forward_share(self.ds)
        self._pre_match = self._preview({"event_id": "", "clock_sec": 0}, state)

    # ---------- triggers ----------

    def on_event(self, e: dict, state) -> list:
        """Update rolling counters for one ingested event and return new proposals."""
        out = []
        t = e["clock_sec"]
        if not self._kicked_off:
            self._kicked_off = True
            if self._pre_match is None:
                self.prepare(state)
            for p in self._pre_match:          # published at kickoff, triggered by the first event
                p.trigger_event_id, p.trigger_clock = e["event_id"], e["clock_sec"]
            out += self._pre_match
        if e["event_type"] == "half_end" and str(e["period"]) == "1" and not self._half_done:
            self._half_done = True                 # half-time summaries at the whistle, after stoppage time
            out += self._summaries(e, state, t, "ht")
        if e["event_type"] == "shot":
            state.shots[e["team_id"]] += 1
        if e["event_type"] == "pass" and e["outcome"] == "success":
            state.completed_passes[e["player_id"]] += 1
            out += self._threat_pass(e, state)
            if state.completed_passes[e["player_id"]] in PASS_MILESTONES:
                out.append(self._milestone(e, state))
        while t >= self._next_momentum:
            out += self._momentum(e, state, self._next_momentum)
            self._next_momentum += MOMENTUM_STEP_SEC
        while t >= self._next_checkpoint:
            out += self._checkpoint(e, state, self._next_checkpoint)
            self._next_checkpoint += CHECKPOINT_SEC
        while t >= self._next_rhythm:
            out += self._rhythm(e, state, self._next_rhythm)
            self._next_rhythm += RHYTHM_EVERY_SEC
        return [p for p in out if p is not None]

    def on_finish(self, state) -> list:
        """Full time: the last checkpoint and the full-time summaries."""
        if not state.events:
            return []
        last = state.events[-1]
        t = last["clock_sec"]
        out = []
        if t > self._next_checkpoint - CHECKPOINT_SEC:
            out += self._checkpoint(last, state, t, FT_TILT_COOLDOWN_SEC)
        out += self._summaries(last, state, t, "ft")
        return [p for p in out if p is not None]

    # ---------- proposal builders ----------

    def _spec(self, metric, scope, subject, t0=None, t1=None, template_key=None, param_values=("amount",),
              extra_params=None, params=None, claim_type="stat", state=None):
        return dict(metric=metric, scope=scope, subject=subject, match_id=state.match_id if scope != "season" else None,
                    window=(t0, t1) if scope == "window" else None, template_key=template_key,
                    param_values=tuple(param_values), extra_params=dict(extra_params or {}),
                    params=dict(params or {}), claim_type=claim_type)

    def _propose(self, spec, insight_type, trigger, state, attempt=1, strategy=None, revision_of=None, meta=None):
        view = state.view(self.ds)
        cid = (f"clm_{state.match_id}_{spec['metric']}_{spec['subject']['id']}"
               + (f"_{spec['window'][0]}_{spec['window'][1]}" if spec["window"] else "") + f"_a{attempt}")
        claim = build_claim(view, spec["metric"], spec["scope"], spec["subject"], claim_type=spec["claim_type"],
                            template_key=spec["template_key"], params=spec["params"], match_id=spec["match_id"],
                            window=spec["window"], param_values=spec["param_values"],
                            extra_params=spec["extra_params"], claim_id=cid, attempt=attempt)
        if not claim["evidence_event_ids"]:
            return None
        p = ClaimProposal(claim, insight_type, trigger["event_id"], trigger["clock_sec"], strategy=strategy,
                          revision_of=revision_of, meta=dict(meta or {}, spec=spec))
        self.log(self.name, "proposed", match_id=state.match_id, clock_sec=trigger["clock_sec"],
                 claim_id=cid, metric=spec["metric"], template_key=spec["template_key"], attempt=attempt,
                 strategy=strategy)
        return p

    def _team(self, tid):
        return {"kind": "team", "id": tid}, {"team": self.ds.code(tid)}

    def _player(self, pid):
        p = self.ds.players[pid]
        return {"kind": "player", "id": pid}, {"player": p["name"], "team": self.ds.code(p["team_id"])}

    def _preview(self, e, state):
        out = []
        for att in state.team_ids():
            dfn = state.opponent(att)
            c = matchup_claim(self.season, att, dfn)
            if c is None:
                continue
            c["claim_id"] = f"clm_{state.match_id}_preview_{self.ds.code(att)}_{self.ds.code(dfn)}_a1"
            out.append(ClaimProposal(c, "matchup_mismatch", e["event_id"], e["clock_sec"], dataset="season",
                                     meta={"lane": c["params"]["lane"], "attacker_id": att, "defender_id": dfn}))
            self.log(self.name, "proposed", match_id=state.match_id, clock_sec=e["clock_sec"], claim_id=c["claim_id"],
                     metric="zone_mismatch", template_key=c["template_key"], attempt=1, strategy=None)
        return out

    def _checkpoint(self, e, state, t, cooldown=TILT_COOLDOWN_SEC):
        out = []
        view = state.view(self.ds)
        t0 = max(0, t - TILT_WINDOW_SEC)
        for tid in state.team_ids():
            evs = [x for x in match_events(view)[state.match_id] if t0 <= x["clock_sec"] <= t]
            tilt = M.field_tilt(evs, tid).value
            key = ("field_tilt", tid)
            if tilt is not None and 100 * tilt >= MIN_TILT and t - state.last_emit.get(key, -cooldown) >= cooldown:
                state.last_emit[key] = t
                subj, extra = self._team(tid)
                out.append(self._propose(self._spec("field_tilt", "window", subj, t0, t, "field_tilt.stat",
                                                    extra_params=extra, state=state), "recap_line", e, state))
        return out

    def _summaries(self, e, state, t, tag):
        out = []
        view = state.view(self.ds)
        evs = match_events(view)[state.match_id]
        for tid in state.team_ids():
            subj, extra = self._team(tid)
            if state.shots[tid] >= MIN_SHOTS_FOR_XG:
                out.append(self._propose(self._spec("xg", "window", subj, 0, t, "xg.stat", extra_params=extra,
                                                    state=state), "volume_vs_value", e, state))
            out.append(self._propose(self._spec("ppda", "window", subj, 0, t, "ppda.stat", extra_params=extra,
                                                state=state), "recap_line", e, state))
            cc = M.chances_by_player(evs, view.passes, tid).value
            top = cc[0] if cc else None
            if top and top[1] >= MIN_CHANCES:
                ps, pe = self._player(top[0])
                out.append(self._propose(self._spec("chances_created", "window", ps, 0, t, "chances_created.stat",
                                                    extra_params=pe, state=state), "player_focus", e, state))
            fw = M.forward_passes_by_player(evs, tid).value
            if fw and fw[0][1] >= MIN_FORWARD:
                ps, pe = self._player(fw[0][0])
                out.append(self._propose(self._spec("forward_passes", "window", ps, 0, t, "forward_passes.stat",
                                                    extra_params=pe, state=state), "player_focus", e, state))
        out += self._patterns(e, state, t, tag)
        return out

    # ---------- tactical patterns and the naive claims they test ----------

    def _patterns(self, e, state, t, tag):
        view = state.view(self.ds)
        evs = match_events(view)[state.match_id]
        cands = []
        # touch-count lines are full-match lines: those families wait for full time
        families = None if tag == "ft" else [f for f in PAT.FAMILIES if PAT.enabled(f) and f not in PAT.FULL_MATCH_ONLY]
        for tid in state.team_ids():
            for f in PAT.detect_team(view, state.match_id, tid, upto=t, families=families):
                if f.family == "pat_flank_isolation" and f.values["f3_share"] < MIN_ISOLATION_F3_SHARE:
                    continue                   # touchline spells away from the final third: nothing to say
                cands.append(dict(kind="pattern", family=f.family, team_id=tid, finding=f,
                                  magnitude=float(f.values["amount"]), score=1.0,
                                  key=f.player_id or ""))
            cands += self._naive(evs, view, state, tid, t, tag)
        out = []
        for c in rank_candidates(cands, self.history, self.family_counts, shown=self.shown):
            if c["kind"] == "pattern":
                out.append(self._propose_pattern(c["finding"], e, state, t))
            else:
                out.append(self._propose(c["spec"], c["insight_type"], e, state))
        return out

    def _naive(self, evs, view, state, tid, t, tag):
        """The plain statistics the Analyst would say first; the Verifier's pattern rules decide
        whether they mislead."""
        subj, extra = self._team(tid)
        out = []

        def add(metric, template, magnitude, insight_type="recap_line", params=None, ex=None, subject=None, key=""):
            spec = self._spec(metric, "window", subject or subj, 0, t, template, extra_params=dict(ex or extra),
                              params=params, state=state)
            out.append(dict(kind="naive", family=metric, team_id=tid, spec=spec, insight_type=insight_type,
                            magnitude=float(magnitude), score=0.9, key=key))
        ent = M.final_third_entries(evs, tid)
        if ent.value >= MIN_SIDE_ENTRIES:
            for side, lanes in SIDE_LANES.items():
                share = 100 * sum(ent.detail["lanes"][l] for l in lanes) / ent.value
                if share >= MIN_SIDE_SHARE:
                    add("attack_side_share", "attack_side.stat", share, params={"side": side},
                        ex=dict(extra, side=side))
        crosses = sum(1 for x in evs if x["event_type"] == "pass" and x["team_id"] == tid
                      and view.passes[x["event_id"]]["pass_type"] == "cross")
        if crosses >= MIN_CROSSES:
            add("crosses", "crosses.stat", crosses)
        f3 = M.final_third_passes(evs, tid).value
        if f3 >= MIN_F3_PASSES and (M.field_tilt(evs, tid).value or 0) >= 0.5:
            add("final_third_passes", "f3_volume.stat", f3)
        losses = sum(1 for x in evs if x["event_type"] == "possession_change" and x["opponent_team_id"] == tid
                     and 100 - x["x_start"] >= M.FINAL_THIRD_X)
        if losses >= MIN_F3_LOSSES:
            add("final_third_losses", "f3_losses.stat", losses)
        if tag == "ft":
            fouls = sum(1 for x in evs if x["event_type"] == "foul" and x["team_id"] == tid)
            if fouls >= MIN_FOULS:
                add("fouls", "fouls.stat", fouls)
            touches: dict = {}
            for x in evs:
                if x["team_id"] == tid and x["event_type"] in ("pass", "carry", "dribble", "shot", "duel") \
                        and x["player_id"]:
                    touches[x["player_id"]] = touches.get(x["player_id"], 0) + 1
            for pid, n in sorted(touches.items()):
                if view.players[pid]["position"] == "FW" and n <= MAX_QUIET_TOUCHES:
                    ps, pe = self._player(pid)
                    add("player_touches", "touches.quiet", n, insight_type="player_focus", ex=pe, subject=ps, key=pid)
        return out

    def _propose_pattern(self, f, trigger, state, t, attempt=1):
        view = state.view(self.ds)
        subj_id = f.player_id or f.team_id
        w = f.window or (0, t)
        cid = f"clm_{state.match_id}_{f.family}_{subj_id}_{w[0]}_{w[1]}_a{attempt}"
        extra = {"team": self.ds.code(f.team_id)}
        if f.player_id:
            extra["player"] = self.ds.players[f.player_id]["name"]
        opp = state.opponent(f.team_id)
        extra["opponent"] = self.ds.code(opp)
        if f.family == "pat_bait_switch":
            extra["side"] = "left" if f.values["build_left"] * 2 >= f.values["amount"] else "right"
        template, keys = pattern_template(f)
        claim = build_pattern_claim(view, f, state.match_id, t, template_key=template, param_values=keys,
                                    extra_params=extra, claim_id=cid, attempt=attempt)
        p = ClaimProposal(claim, "tactical_pattern", trigger["event_id"], trigger["clock_sec"],
                          meta={"family": f.family})
        self.log(self.name, "proposed", match_id=state.match_id, clock_sec=trigger["clock_sec"], claim_id=cid,
                 metric=f.family, template_key=template, attempt=attempt, strategy=None)
        return p

    def _rhythm(self, e, state, t):
        subj, extra = self._team(state.home_id)
        return [self._propose(self._spec("rhythm_index", "window", subj, max(0, t - 900), t, "rhythm.wave",
                                         param_values=("amount", "minutes"), state=state), "rhythm_wave", e, state)]

    def _momentum(self, e, state, t):
        view = state.view(self.ds)
        evs = match_events(view)[state.match_id]
        series = F.momentum(evs, view.shots, self.grid, state.home_id, state.away_id).value
        m = series[-1][1] if series else 0.0
        sign = (m > 0) - (m < 0)
        swing = abs(m) >= MOMENTUM_SWING and sign != state.momentum_sign
        if sign and abs(m) >= MOMENTUM_SWING:
            state.momentum_sign = sign
        last = state.last_emit.get("momentum", -MOMENTUM_COOLDOWN_SEC)
        if not swing or t - last < MOMENTUM_COOLDOWN_SEC or t < MOMENTUM_WINDOW_SEC:
            return []
        state.last_emit["momentum"] = t
        tid = state.home_id if sign > 0 else state.away_id
        subj, extra = self._team(tid)
        return [self._propose(self._spec("momentum", "window", subj, t - MOMENTUM_WINDOW_SEC, t, "momentum.shift",
                                         param_values=("amount", "momentum_before"), extra_params=extra,
                                         state=state), "momentum_shift", e, state)]

    def _threat_pass(self, e, state):
        added = T.value_at(self.grid, e["x_end"], e["y_end"]) - T.value_at(self.grid, e["x_start"], e["y_start"])
        key = ("threat", e["team_id"])
        if added < THREAT_PASS_XT or e["clock_sec"] - state.last_emit.get(key, -THREAT_COOLDOWN_SEC) < THREAT_COOLDOWN_SEC:
            return []
        state.last_emit[key] = e["clock_sec"]
        subj, extra = self._player(e["player_id"])
        return [self._propose(self._spec("xt_added", "window", subj, 0, e["clock_sec"], "xt_added.threat_pass",
                                         params={"pass_event_id": e["event_id"]}, extra_params=extra, state=state),
                              "threat_pass", e, state, meta={"pass_event_id": e["event_id"]})]

    def _milestone(self, e, state):
        subj, extra = self._player(e["player_id"])
        return self._propose(self._spec("milestone_count", "window", subj, 0, e["clock_sec"], "milestone.pass_count",
                                        extra_params=extra, claim_type="milestone", state=state), "milestone", e, state)

    # ---------- revision ----------

    def revise(self, result, state):
        """A blocked VerificationResult -> a revised ClaimProposal (attempt + 1), or None to drop."""
        p, v = result.proposal, result.verdict
        attempt = p.attempt + 1
        why = list(v.rule_ids)
        if attempt > MAX_ATTEMPTS or "spec" not in p.meta:
            return self._drop(result, state, "max_attempts" if attempt > MAX_ATTEMPTS else "not_revisable")
        if set(why) & NOT_REVISABLE:
            return self._drop(result, state, "blocking_rule:" + ",".join(sorted(set(why) & NOT_REVISABLE)))
        spec = dict(p.meta["spec"])
        if v.fact_check == "fail":
            # the event log does not back the claim: rebuild it from the tables once, then give up
            if p.strategy == "recompute":
                return self._drop(result, state, "fact_check_failed_twice")
            strategy = "recompute"
        elif v.revision_hint:
            rules = [r for r in v.rule_ids if r in v.revision_hint]
            if any(r not in REVISIONS for r in rules):
                return self._drop(result, state, "no_revision_for:" + ",".join(rules))
            template, add, params = REVISIONS[rules[0]]
            if len(set(rules)) > 1 and set(rules) & set(PATTERN_RULES):
                template = COMBINED_REVISIONS.get(frozenset(rules))
                if template is None:
                    return self._drop(result, state, "no_revision_for:" + ",".join(sorted(set(rules))))
            pv = list(spec["param_values"])
            for r in rules:
                for k in REVISIONS[r][1]:
                    if k not in pv:
                        pv.append(k)
                params = {**params, **REVISIONS[r][2]}
            spec.update(template_key=template, param_values=tuple(pv), params={**spec["params"], **params})
            strategy = STRATEGY[rules[0]]
        else:
            return self._drop(result, state, "blocked_without_hint")
        new = self._propose(spec, p.insight_type, {"event_id": p.trigger_event_id, "clock_sec": p.trigger_clock},
                            state, attempt=attempt, strategy=strategy, revision_of=p.claim["claim_id"],
                            meta={k: x for k, x in p.meta.items() if k != "spec"})
        if new is None:
            return self._drop(result, state, "no_evidence_after_revision")
        self.log(self.name, "revised", match_id=state.match_id, claim_id=new.claim["claim_id"],
                 revision_of=p.claim["claim_id"], strategy=strategy, attempt=attempt, rule_ids=why)
        return new

    def _drop(self, result, state, reason):
        state.dropped.append((result.claim["claim_id"], reason))
        self.log(self.name, "dropped", match_id=state.match_id, claim_id=result.claim["claim_id"],
                 attempt=result.proposal.attempt, reason=reason, rule_ids=list(result.verdict.rule_ids))
        return None
