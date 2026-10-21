"""Verifier agent: engine.verifier on a proposal, against the data the claim is about.

Season claims (the pre-match preview) are checked against the season baseline; match and window
claims against the match's events ingested so far (state.view), so a claim can never be backed
by an event the stream has not delivered yet.
"""
from __future__ import annotations

from engine.verifier import verdict, verify

from .messages import VerificationResult


class VerifierAgent:
    name = "verifier"

    def __init__(self, log, match_ds, season_ds):
        self.log, self.ds, self.season = log, match_ds, season_ds

    def check(self, proposal, state) -> VerificationResult:
        ds = self.season if proposal.dataset == "season" else state.view(self.ds)
        out = verify(proposal.claim, ds)
        v = verdict(proposal.claim, ds)
        res = VerificationResult(proposal, out, v)
        ver = out["verification"]
        self.log(self.name, "verified", match_id=state.match_id, clock_sec=proposal.trigger_clock,
                 claim_id=out["claim_id"], attempt=ver["attempt"], status=ver["status"],
                 fact_check=ver["fact_check"], rule_ids=ver["rule_ids"], context_note=ver["context_note"],
                 revision_hint=ver.get("revision_hint"), problems=v.problems)
        return res
