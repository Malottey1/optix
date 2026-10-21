"""Contract rules that JSON Schema cannot express. Pure functions, used by the Verifier and tests."""
from __future__ import annotations

import math


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_param_numbers(claim: dict, rel_tol: float = 1e-9) -> list[str]:
    """Every number in claim["params"] must equal value.amount or an entry of supporting_values.

    Returns a list of problems (empty = ok), one per offending param, e.g.
    "params.concede_share=41 not in value.amount or supporting_values".
    """
    allowed = [claim.get("value", {}).get("amount")]
    allowed += list((claim.get("supporting_values") or {}).values())
    allowed = [a for a in allowed if _is_number(a)]
    problems = []
    for k, v in (claim.get("params") or {}).items():
        if _is_number(v) and not any(math.isclose(v, a, rel_tol=rel_tol, abs_tol=1e-12) for a in allowed):
            problems.append(f"params.{k}={v} not in value.amount or supporting_values")
    return problems
