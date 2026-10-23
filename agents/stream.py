"""Timed insight stream: feeds a match event by event and emits insights as they are verified.

Latency = wall time from receiving the triggering event to the insight being built. The work per
event is bounded: the Analyst updates rolling counters in MatchState, the xT grid and league
baselines are precomputed on the season, and claims are recomputed only when a trigger fires.
"""
from __future__ import annotations

import time

from .insights import build_insight
from .orchestrator import Orchestrator


class InsightStream:
    def __init__(self, match_ds, match_id, log=None, languages=("en",), phraser=None, engine="direct", audit=None):
        """engine: "direct" (agents/orchestrator.py, the default and fallback) or "workflow" (the
        same agents as a Microsoft Agent Framework workflow, agents/workflow.py)."""
        self.match_id = match_id
        if engine == "workflow":
            from .workflow import WorkflowOrchestrator as cls
        elif engine == "direct":
            cls = Orchestrator
        else:
            raise ValueError(f"unknown engine {engine!r}")
        self.orc = cls(match_ds, match_id, log=log, languages=languages, on_published=self._emit,
                       phraser=phraser, audit=audit)
        self.ds = match_ds
        self.insights: list = []
        self.received: dict = {}           # event_id -> perf_counter when it arrived
        self.event_ms: list = []           # processing time per fed row
        self.orc.prepare()                 # pre-match: not part of any event's latency

    def _emit(self, pub, trigger_event):
        t0 = self.received.get(trigger_event["event_id"], time.perf_counter())
        ins = build_insight(pub, self.orc.state.view(self.ds), self.match_id, len(self.insights) + 1, None)
        ins["clock"]["emitted_latency_ms"] = int(round((time.perf_counter() - t0) * 1000))
        self.insights.append(ins)
        self.orc.log("stream", "insight", match_id=self.match_id, insight_id=ins["insight_id"],
                     insight_type=ins["insight_type"], claim_id=ins["claim_id"],
                     clock_sec=ins["clock"]["start_sec"], latency_ms=ins["clock"]["emitted_latency_ms"])

    def feed(self, row):
        t0 = time.perf_counter()
        self.received[row["event_id"]] = t0
        self.orc.feed([row])
        self.event_ms.append((time.perf_counter() - t0) * 1000)

    def finish(self):
        last = self.orc.state.events[-1] if self.orc.state.events else None
        if last is not None:
            self.received[last["event_id"]] = time.perf_counter()
        self.orc.finish()
        self.orc.log.flush()

    def run(self, rows=None):
        from engine.tables import match_events
        for r in rows if rows is not None else match_events(self.ds)[self.match_id]:
            self.feed(r)
        self.finish()
        return self.insights

    def attempts(self) -> list:
        """Every verification attempt of every published claim (for the evidence drawer and the
        blocked-then-rewritten view), in publication order."""
        out = []
        for pub in self.orc.state.published:
            for h in pub.history:
                out.append({"claim": h.claim, "strategy": h.proposal.strategy, "revision_of": h.proposal.revision_of,
                            "trigger_clock": h.proposal.trigger_clock})
        return out
