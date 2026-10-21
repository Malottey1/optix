"""Verifier context rules. One module per rule, each exposing `check(claim, ctx) -> RuleResult | None`.

A rule returns None when it does not apply to the claim (wrong metric or claim type), otherwise a
RuleResult saying whether it fired. A fired rule's `action` is "context" (true but misleading on
its own: publish with a context chip) or "block" (never publish). `note` is a machine-readable
context_note key, never prose. Thresholds live in each module and are documented there.

A context rule also declares REQUIRES: the params the sentence must carry for the claim to be
honest with the context shown (e.g. box entries beside field tilt). A fired context rule whose
REQUIRES are missing from params blocks the claim; the Verifier returns them as a revision hint so
the Analyst can rebuild the claim with that context.

ctx is a verifier.Context: the dataset, the claim's resolved scope, the recomputed (unrounded)
values and the subject's team id.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    fired: bool
    action: str          # "context" or "block"
    note: str | None     # context_note key when fired
    detail: dict


from . import (causal_claim, causal_red_card, field_tilt_with_lead, ppda_alone, set_piece_inflation,  # noqa: E402
               shot_spam, single_match_fatigue, small_sample_xg, wide_forward_passes)

RULES = [causal_claim, causal_red_card, single_match_fatigue, field_tilt_with_lead, shot_spam,
         set_piece_inflation, wide_forward_passes, small_sample_xg, ppda_alone]
