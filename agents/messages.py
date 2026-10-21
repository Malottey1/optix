"""Typed messages passed between agents (see docs/ARCHITECTURE.md, "Handoffs")."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IngestReport:
    """Ingest -> Orchestrator, per batch of raw rows."""
    accepted: int
    duplicates: tuple = ()               # event_ids seen before (dropped)
    missing_fields: dict = field(default_factory=dict)   # event_id -> missing field names (dropped)


@dataclass
class ClaimProposal:
    """Analyst -> Verifier. `claim` is a pending claim object (contracts/claim.schema.json)."""
    claim: dict
    insight_type: str                    # semantic type the insight will carry if published
    trigger_event_id: str                # the event that caused the Analyst to look
    trigger_clock: int
    dataset: str = "match"               # "match" (ingested events so far) or "season" (baseline)
    strategy: str | None = None          # how this attempt was revised (None on attempt 1)
    revision_of: str | None = None       # claim_id of the blocked attempt it revises
    meta: dict = field(default_factory=dict)   # Analyst's own notes for the insight builder (e.g. lane)

    @property
    def attempt(self) -> int:
        return self.claim["verification"]["attempt"]


@dataclass
class VerificationResult:
    """Verifier -> Orchestrator/Analyst. `claim` carries the filled `verification` block."""
    proposal: ClaimProposal
    claim: dict
    verdict: object                      # engine.verifier.Verdict

    @property
    def status(self) -> str:
        return self.claim["verification"]["status"]


@dataclass(frozen=True)
class RenderedText:
    """Narrative -> insight builder: the contract's text object."""
    template_key: str
    params: dict
    rendered: dict                       # language -> tone -> text
    number_guard_passed: bool

    def as_contract(self) -> dict:
        return {"template_key": self.template_key, "params": self.params, "rendered": self.rendered,
                "number_guard_passed": self.number_guard_passed}


@dataclass
class Published:
    """Orchestrator output: a verified, rendered claim ready to become an insight."""
    result: VerificationResult
    text: RenderedText
    history: list                        # every VerificationResult for this claim, attempt order
