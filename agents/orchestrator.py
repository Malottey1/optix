"""Orchestrator: streams a match's events through the agents.

    raw rows -> Ingest (dedup, flag) -> MatchState -> Analyst.on_event -> ClaimProposal
      -> Verifier -> published / published_with_context -> Narrative -> Published
                  -> blocked -> Analyst.revise (attempt + 1) -> Verifier ... or dropped

Each handoff is a typed message (agents/messages.py) and is logged (agents/log.py).
"""
from __future__ import annotations

from engine.tables import Dataset, baseline_of, match_events

from . import telemetry
from .analyst import AnalystAgent
from .ingest import IngestAgent
from .log import AgentLog
from .messages import Published
from .narrative import NarrativeAgent
from .state import MatchState
from .verifier_agent import VerifierAgent


class Orchestrator:
    def __init__(self, match_ds: Dataset, match_id: str, log: AgentLog | None = None,
                 languages: tuple = ("en",), on_published=None, phraser=None, audit=None):
        self.ds = match_ds
        self.season = baseline_of(match_ds)
        m = match_ds.matches[match_id]
        self.state = MatchState(match_id, m["home_team_id"], m["away_team_id"])
        self.log = log or AgentLog()
        self.ingest = IngestAgent(self.log, match_ds.passes, match_ds.shots)
        self.analyst = AnalystAgent(self.log, match_ds, self.season)
        self.verifier = VerifierAgent(self.log, match_ds, self.season)
        self.narrative = NarrativeAgent(self.log, languages, phraser)
        self.on_published = on_published        # callback(Published, trigger_event) for streaming
        self.audit = audit                      # agents.audit.AuditLog: one chained record per publication

    def prepare(self):
        """Pre-match work (season preview, season baselines); run() calls it if nobody did."""
        self.analyst.prepare(self.state)

    def feed(self, rows) -> list:
        """Ingest a batch of raw rows; return what got published because of them."""
        clean, _ = self.ingest.process(rows, self.state)
        out = []
        for e in clean:
            self._apply(e)
            for p in self.analyst.on_event(e, self.state):
                pub = self.handle(p)
                if pub is not None:
                    out.append(pub)
                    if self.on_published:
                        self.on_published(pub, e)
        return out

    def finish(self) -> list:
        out = []
        for p in self.analyst.on_finish(self.state):
            pub = self.handle(p)
            if pub is not None:
                out.append(pub)
                if self.on_published:
                    self.on_published(pub, self.state.events[-1])
        return out

    def _apply(self, e):
        """Add one clean event to the match state."""
        self.state.events.append(e)
        self.state.seen_ids.add(e["event_id"])
        self.state.clock = e["clock_sec"]
        self.state.score = (e["score_home"], e["score_away"])

    def _publish(self, res, text, history) -> Published:
        with telemetry.span("publish", claim_id=res.claim["claim_id"], status=res.status,
                            insight_type=res.proposal.insight_type):
            pub = Published(res, text, history)
            self.state.published.append(pub)
            self.log("orchestrator", "published", match_id=self.state.match_id, claim_id=res.claim["claim_id"],
                     status=res.status, attempt=res.claim["verification"]["attempt"],
                     clock_sec=res.proposal.trigger_clock)
            if self.audit is not None:
                self.audit.append("published", {
                    "match_id": self.state.match_id, "claim_id": res.claim["claim_id"], "status": res.status,
                    "attempts": [{"attempt": h.claim["verification"]["attempt"], "status": h.status,
                                  "rule_ids": h.claim["verification"]["rule_ids"]} for h in history],
                    "metric": res.claim["metric"], "value": res.claim["value"],
                    "evidence_event_ids": res.claim["evidence_event_ids"],
                    "rendered": text.rendered, "phraser": getattr(self.narrative.last_phrase, "phraser", None),
                    "guard_rejected": getattr(self.narrative.last_phrase, "guard_rejected", {})})
        return pub

    def handle(self, proposal) -> Published | None:
        """Verify, revise while blocked, narrate once published."""
        history = []
        while proposal is not None:
            with telemetry.span("analyst.propose", claim_id=proposal.claim["claim_id"], attempt=proposal.attempt,
                                insight_type=proposal.insight_type, strategy=proposal.strategy):
                pass
            res = self.verifier.check(proposal, self.state)
            history.append(res)
            if res.status in ("published", "published_with_context"):
                text = self.narrative.write(res.claim)
                if not text.number_guard_passed:
                    self.log("orchestrator", "dropped", claim_id=res.claim["claim_id"], reason="number_guard")
                    self.state.dropped.append((res.claim["claim_id"], "number_guard"))
                    return None
                return self._publish(res, text, history)
            proposal = self.analyst.revise(res, self.state)
        return None

    def run(self, rows=None) -> list:
        """Stream the whole match (default: its events from the dataset, in order)."""
        rows = rows if rows is not None else match_events(self.ds)[self.state.match_id]
        out = []
        for r in rows:
            out += self.feed([r])
        out += self.finish()
        self.log.flush()
        return out
