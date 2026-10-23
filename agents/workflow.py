"""The agent pipeline as a Microsoft Agent Framework workflow (package agent-framework-core).

    EventBatch / Finish
          |
       Analyst ──Attempt──> Verifier ──Checked (approved)──> Phraser ──Phrased──> Publisher
          ^                    |                                                     |
          └── Checked (blocked, conditional edge: revise or drop) ───────────────────┘
          └──────────────────────────── Next (release the next proposal) ────────────┘

Every executor wraps the same deterministic agent the direct pipeline (agents/orchestrator.py)
uses, so verdicts stay code: the Verifier executor calls VerifierAgent.check (engine.verifier),
and a blocked claim goes back to the Analyst over a conditional edge for a revision (attempt + 1)
or is dropped. Two function tools (`recompute_metric`, `fetch_evidence`, agent_framework.tool) are
called by the Verifier executor itself and recorded in the log; they are never handed to a model.
The Phraser executor is the guarded phrasing layer (agents/phraser.py; the template by default).

One workflow run per ingested batch. The Analyst queues that batch's proposals and releases them
one at a time (the Publisher, or a drop, sends `Next`), so claims are verified and published in
exactly the direct pipeline's order; with the template phraser the stream is identical
(tests/test_workflow.py). The direct pipeline stays as the fallback and for the slow suites.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler, tool

from engine import claims as C

from . import telemetry
from .messages import ClaimProposal, Published, RenderedText, VerificationResult
from .orchestrator import Orchestrator

APPROVED = ("published", "published_with_context")


# ---- typed messages -------------------------------------------------------------------------
@dataclass
class EventBatch:
    """Workflow input: raw rows for the Analyst (ingested first)."""
    rows: list


@dataclass
class Finish:
    """Workflow input: full time; the Analyst's end-of-match proposals."""


@dataclass
class Attempt:
    """Analyst -> Verifier: one proposal with the verification history of its claim so far."""
    proposal: ClaimProposal
    history: list = field(default_factory=list)


@dataclass
class Checked:
    """Verifier -> Phraser (approved) or Analyst (blocked)."""
    result: VerificationResult
    history: list

    @property
    def approved(self) -> bool:
        return self.result.status in APPROVED


@dataclass
class Phrased:
    """Phraser -> Publisher."""
    result: VerificationResult
    text: RenderedText
    history: list


@dataclass
class Next:
    """Publisher / Phraser / Analyst -> Analyst: release the next queued proposal."""


# ---- function tools (deterministic, called by the Verifier executor) --------------------------
def make_tools(orc: Orchestrator):
    @tool(name="recompute_metric", description="Recompute a claim's metric from the events ingested so far.")
    def recompute_metric(claim: dict) -> dict:
        ds = orc.season if claim["scope"] == "season" else orc.state.view(orc.ds)
        vals, _ = C.compute(ds, claim["metric"], claim["scope"], claim["subject"], claim.get("params"),
                            claim.get("match_id"), claim.get("window"))
        return vals

    @tool(name="fetch_evidence", description="Fetch the evidence events of a claim by id.")
    def fetch_evidence(event_ids: list[str], season: bool = False) -> list:
        ds = orc.season if season else orc.state.view(orc.ds)
        want = set(event_ids)
        return [e for e in ds.events if e["event_id"] in want]

    return recompute_metric, fetch_evidence


async def _call(t, **arguments):
    return await t.invoke(arguments=arguments, skip_parsing=True)


# ---- executors ------------------------------------------------------------------------------
class AnalystExecutor(Executor):
    def __init__(self, orc: Orchestrator):
        super().__init__("analyst")
        self.orc, self.queue, self.trigger = orc, [], None

    @handler
    async def on_events(self, msg: EventBatch, ctx: WorkflowContext[Attempt]) -> None:
        o = self.orc
        clean, _ = o.ingest.process(msg.rows, o.state)
        for e in clean:
            o._apply(e)
            self.queue += [(p, e) for p in o.analyst.on_event(e, o.state)]
        await self._release_pair(ctx)

    @handler
    async def on_finish(self, msg: Finish, ctx: WorkflowContext[Attempt]) -> None:
        o = self.orc
        last = o.state.events[-1] if o.state.events else None
        self.queue += [(p, last) for p in o.analyst.on_finish(o.state)]
        await self._release_pair(ctx)

    async def _release_pair(self, ctx):
        if self.queue:
            p, self.trigger = self.queue.pop(0)
            with telemetry.span("analyst.propose", claim_id=p.claim["claim_id"], attempt=p.attempt,
                                insight_type=p.insight_type, strategy=p.strategy):
                await ctx.send_message(Attempt(p))

    @handler
    async def on_next(self, msg: Next, ctx: WorkflowContext[Attempt]) -> None:
        await self._release_pair(ctx)

    @handler
    async def on_blocked(self, msg: Checked, ctx: WorkflowContext[Attempt]) -> None:
        """Block-and-revise: a revised proposal goes back to the Verifier, or the claim is dropped."""
        p = self.orc.analyst.revise(msg.result, self.orc.state)
        if p is None:
            await self._release_pair(ctx)
            return
        with telemetry.span("analyst.propose", claim_id=p.claim["claim_id"], attempt=p.attempt,
                            insight_type=p.insight_type, strategy=p.strategy):
            await ctx.send_message(Attempt(p, msg.history))


class VerifierExecutor(Executor):
    def __init__(self, orc: Orchestrator):
        super().__init__("verifier")
        self.orc = orc
        self.recompute_metric, self.fetch_evidence = make_tools(orc)

    @handler
    async def check(self, msg: Attempt, ctx: WorkflowContext[Checked]) -> None:
        p = msg.proposal
        claim = p.claim
        # the function tools: the evidence the claim cites and the metric recomputed on the same data
        found = await _call(self.fetch_evidence, event_ids=list(claim.get("evidence_event_ids") or []),
                            season=p.dataset == "season")
        try:
            vals = await _call(self.recompute_metric, claim=claim)
            recomputed = vals.get("amount") if isinstance(vals, dict) else None
        except (KeyError, TypeError, ValueError):
            recomputed = None
        self.orc.log("verifier", "tools", claim_id=claim["claim_id"], evidence_found=len(found),
                     evidence_cited=len(claim.get("evidence_event_ids") or []), recomputed_amount=recomputed)
        res = self.orc.verifier.check(p, self.orc.state)        # the verdict: deterministic code
        await ctx.send_message(Checked(res, msg.history + [res]))


class PhraserExecutor(Executor):
    def __init__(self, orc: Orchestrator):
        super().__init__("phraser")
        self.orc = orc

    @handler
    async def phrase(self, msg: Checked, ctx: WorkflowContext[Phrased | Next]) -> None:
        claim = msg.result.claim
        text = self.orc.narrative.write(claim)
        if not text.number_guard_passed:
            self.orc.log("orchestrator", "dropped", claim_id=claim["claim_id"], reason="number_guard")
            self.orc.state.dropped.append((claim["claim_id"], "number_guard"))
            await ctx.send_message(Next())
            return
        await ctx.send_message(Phrased(msg.result, text, msg.history))


class PublisherExecutor(Executor):
    def __init__(self, orc: Orchestrator, analyst: AnalystExecutor):
        super().__init__("publisher")
        self.orc, self.analyst = orc, analyst

    @handler
    async def publish(self, msg: Phrased, ctx: WorkflowContext[Next, Published]) -> None:
        pub = self.orc._publish(msg.result, msg.text, msg.history)
        if self.orc.on_published:
            self.orc.on_published(pub, self.analyst.trigger)
        await ctx.yield_output(pub)
        await ctx.send_message(Next())


def build_workflow(orc: Orchestrator):
    analyst = AnalystExecutor(orc)
    verifier = VerifierExecutor(orc)
    phraser = PhraserExecutor(orc)
    publisher = PublisherExecutor(orc, analyst)
    wf = (WorkflowBuilder(start_executor=analyst, max_iterations=100_000, name="optix-insights",
                          output_from=[publisher])
          .add_edge(analyst, verifier)
          .add_edge(verifier, phraser, condition=lambda m: isinstance(m, Checked) and m.approved)
          .add_edge(verifier, analyst, condition=lambda m: isinstance(m, Checked) and not m.approved)
          .add_edge(phraser, publisher, condition=lambda m: isinstance(m, Phrased))
          .add_edge(phraser, analyst, condition=lambda m: isinstance(m, Next))
          .add_edge(publisher, analyst)
          .build())
    return wf


class WorkflowOrchestrator(Orchestrator):
    """Orchestrator with the same interface whose feed/finish run the Agent Framework workflow."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.workflow = build_workflow(self)
        self._loop = asyncio.new_event_loop()

    def _run(self, msg) -> list:
        res = self._loop.run_until_complete(self.workflow.run(msg))
        return [o for o in res.get_outputs() if isinstance(o, Published)]

    def feed(self, rows) -> list:
        return self._run(EventBatch(list(rows)))

    def finish(self) -> list:
        return self._run(Finish())

    def close(self):
        self._loop.close()
