"""The Verifier: fact check, then context check, on a claim object (never on free text).

Fact check
    * every evidence ID must exist in the tables and satisfy the claim metric's definition
      (e.g. a field_tilt claim's evidence are the subject's final-third passes in scope),
      else missing_evidence;
    * value.amount and every supporting_values entry are recomputed from the claim's own scope,
      match, window, subject and params (engine.claims.compute) and must match within half the
      last rounding step, else value_mismatch;
    * every number in params must equal value.amount or a supporting value
      (contracts.checks.check_param_numbers), else value_mismatch.
Context check
    every rule in engine/rules/ that applies; a fired "block" rule blocks; a fired "context" rule
    publishes with context when the claim's params carry the rule's REQUIRES, else it blocks and
    verification.revision_hint names the params to add.
Status: blocked (fact fail or block rule) / published_with_context / published.
The input claim is never modified; verify() returns a new claim with `verification` filled in.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from contracts.checks import check_param_numbers

from . import claims as C
from .rules import RULES, RuleResult
from .tables import Dataset


@dataclass
class Context:
    ds: Dataset
    scope: C.Scope
    values: dict
    team_id: str


@dataclass
class Verdict:
    status: str
    fact_check: str
    actual_value: float | None
    context_check: str | None
    rule_ids: list
    context_note: str | None
    problems: list = field(default_factory=list)
    rule_results: list = field(default_factory=list)
    revision_hint: dict = field(default_factory=dict)     # rule_id -> params the claim must add


_RULE_MODULES = {r.RULE_ID: r for r in RULES}


def _events_by_id(ds):
    key = id(ds)
    if _EV.get(key, (None,))[0] is not ds:
        _EV[key] = (ds, {e["event_id"]: e for e in ds.events})
    return _EV[key][1]


_EV: dict = {}


def fact_check(claim: dict, ds: Dataset):
    """-> (passed, problems, rule_ids, recomputed values, scope)."""
    problems, rules = [], []
    ids = claim.get("evidence_event_ids") or []
    by_id = _events_by_id(ds)
    if not ids:
        return False, ["no evidence"], ["missing_evidence"], None, None
    missing = [i for i in ids if i not in by_id]
    if missing:
        return False, [f"unknown event ids: {missing[:5]}"], ["missing_evidence"], None, None
    metric = claim["metric"]
    if metric not in C.COMPUTE:
        return False, [f"metric {metric} cannot be recomputed"], ["value_mismatch"], None, None
    try:
        scope = C.resolve_scope(ds, claim["scope"], claim.get("match_id"), claim.get("window"))
        vals, pred = C.compute(ds, metric, claim["scope"], claim["subject"], claim.get("params"),
                               claim.get("match_id"), claim.get("window"))
    except (KeyError, TypeError) as exc:
        return False, [f"cannot resolve claim: {exc}"], ["missing_evidence"], None, None
    # a season scope is every event, so only narrower scopes need the membership check
    in_scope = None if claim["scope"] == "season" else {e["event_id"] for e in scope.events}
    bad = [i for i in ids if not pred(by_id[i])
           or (in_scope is not None and metric != "zone_mismatch" and i not in in_scope)]
    if bad:
        problems.append(f"evidence does not support the claim: {bad[:5]}")
        rules.append("missing_evidence")
    unit = claim["value"]["unit"]
    tol = C.tolerance(C.AMOUNT_DP.get(unit, 2))
    if vals["amount"] is None or not math.isclose(vals["amount"], claim["value"]["amount"], abs_tol=tol):
        problems.append(f"value.amount {claim['value']['amount']} != recomputed {vals['amount']}")
        rules.append("value_mismatch")
    for k, v in (claim.get("supporting_values") or {}).items():
        if k not in vals or vals[k] is None:
            problems.append(f"supporting_values.{k} cannot be recomputed")
            rules.append("value_mismatch")
        elif not math.isclose(vals[k], v, abs_tol=C.tolerance(C.support_dp(k))):
            problems.append(f"supporting_values.{k} {v} != recomputed {vals[k]}")
            rules.append("value_mismatch")
    pn = check_param_numbers(claim)
    if pn:
        problems += pn
        rules.append("value_mismatch")
    return not problems, problems, sorted(set(rules)), vals, scope


def verify(claim: dict, ds: Dataset, now: datetime | None = None) -> dict:
    """Return a copy of `claim` with verification filled in (status, fact/context check, rules)."""
    out = copy.deepcopy(claim)
    v = verdict(claim, ds)
    attempt = (claim.get("verification") or {}).get("attempt", 1)
    out["verification"] = {
        "status": v.status,
        "fact_check": v.fact_check,
        "actual_value": v.actual_value,
        "context_check": v.context_check,
        "rule_ids": v.rule_ids,
        "context_note": v.context_note,
        **({"revision_hint": v.revision_hint} if v.revision_hint else {}),
        "attempt": attempt,
        "verified_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
    }
    return out


def verdict(claim: dict, ds: Dataset) -> Verdict:
    ok, problems, rule_ids, vals, scope = fact_check(claim, ds)
    actual = None if vals is None else round(vals["amount"], 6) if vals["amount"] is not None else None
    if not ok:
        return Verdict("blocked", "fail", actual, None, rule_ids, None, problems)
    tid = C._team_of(ds, claim["subject"]) if claim["subject"]["kind"] in ("team", "player") else None
    ctx = Context(ds, scope, vals, tid)
    results = [r for r in (rule.check(claim, ctx) for rule in RULES) if r is not None]
    fired = [r for r in results if r.fired]
    params = claim.get("params") or {}
    requires = {r.rule_id: list(_RULE_MODULES[r.rule_id].REQUIRES) for r in fired if r.action == "context"}
    hint = {rid: [k for k in keys if k not in params] for rid, keys in requires.items()}
    hint = {rid: keys for rid, keys in hint.items() if keys}
    blocks = [r for r in fired if r.action == "block" or r.rule_id in hint]
    contexts = [r for r in fired if r.action == "context"]
    ids = [r.rule_id for r in fired]
    if blocks:
        return Verdict("blocked", "pass", actual, "misleading", ids, blocks[0].note, problems, results, hint)
    if contexts:
        return Verdict("published_with_context", "pass", actual, "misleading", ids, contexts[0].note,
                       problems, results)
    return Verdict("published", "pass", actual, "ok", [], None, problems, results)
