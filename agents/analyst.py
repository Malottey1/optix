"""Analyst agent: decides WHEN to look and WHAT claim to propose, and revises blocked claims.

It never computes a number: every claim comes from engine.claims.build_claim (or
engine.matchup.matchup_claim) over the events ingested so far. Its own logic is only triggers
(checkpoints, thresholds on engine values, cooldowns) and revision strategies.

Triggers (deterministic, in match clock):
  * kickoff: season matchup preview for each direction (attacker lane vs defender completion),
    computed in prepare() before the first event;
  * every CHECKPOINT_SEC: each team's field tilt over the last TILT_WINDOW_SEC when >= MIN_TILT
    (once per team per TILT_COOLDOWN_SEC);
  * at half time and full time: each team's xG so far (>= MIN_SHOTS_FOR_XG shots), top chance
    creator (>= MIN_CHANCES), top forward passer (>= MIN_FORWARD), PPDA;
  * every 30 minutes: the rhythm wave (last 15 minutes);
  * every minute: momentum; a sign change with |momentum| >= MOMENTUM_SWING;
  * a completed pass adding >= THREAT_PASS_XT expected threat (one per team per cooldown);
  * a player's completed passes reaching a PASS_MILESTONES value.
First attempts are deliberately plain (the headline number only); the Verifier says what context
a sentence needs and revise() adds it.
"""
from __future__ import annotations

from engine import flow as F
from engine import metrics as M
from engine import threat as T
from engine.claims import build_claim
from engine.matchup import matchup_claim
from engine.tables import match_events

from .messages import ClaimProposal

CHECKPOINT_SEC = 900
TILT_WINDOW_SEC = 1800
MIN_TILT = 60.0
TILT_COOLDOWN_SEC = 1800
HALF_TIME_SEC = 2700
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

# rule -> (revised template, params the revision adds, extra compute params)
REVISIONS = {
    "field_tilt_with_lead": ("field_tilt.trailing_vs_deep_block", ("box_entries", "team_f3_passes"), {}),
    "shot_spam": ("xg.volume_vs_value", ("shots", "xg_per_shot"), {}),
    "small_sample_xg": ("xg.small_sample", ("shots",), {}),
    "set_piece_inflation": ("chances_created.split", ("open_play", "set_piece"), {}),
    "wide_forward_passes": ("forward_passes.wide_low_threat", ("pass_quality_ratio",), {}),
    "ppda_alone": ("ppda.with_press_intensity", ("press_intensity",), {"with_press_intensity": True}),
}
STRATEGY = {"field_tilt_with_lead": "add_game_state", "shot_spam": "add_shot_quality",
            "small_sample_xg": "add_sample_size", "set_piece_inflation": "split_open_play_set_piece",
            "wide_forward_passes": "add_pass_quality", "ppda_alone": "add_press_intensity"}
NOT_REVISABLE = {"causal_claim", "causal_red_card", "single_match_fatigue"}


class AnalystAgent:
    name = "analyst"

    def __init__(self, log, match_ds, season_ds):
        self.log, self.ds, self.season = log, match_ds, season_ds
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
            out += self._checkpoint(last, state, t, summaries=False)
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

    def _checkpoint(self, e, state, t, summaries=True):
        out = []
        view = state.view(self.ds)
        t0 = max(0, t - TILT_WINDOW_SEC)
        for tid in state.team_ids():
            evs = [x for x in match_events(view)[state.match_id] if t0 <= x["clock_sec"] <= t]
            tilt = M.field_tilt(evs, tid).value
            key = ("field_tilt", tid)
            if tilt is not None and 100 * tilt >= MIN_TILT and t - state.last_emit.get(key, -TILT_COOLDOWN_SEC) >= TILT_COOLDOWN_SEC:
                state.last_emit[key] = t
                subj, extra = self._team(tid)
                out.append(self._propose(self._spec("field_tilt", "window", subj, t0, t, "field_tilt.stat",
                                                    extra_params=extra, state=state), "recap_line", e, state))
        if summaries and not self._half_done and t >= HALF_TIME_SEC:
            self._half_done = True
            out += self._summaries(e, state, t, "ht")
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
        return out

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
