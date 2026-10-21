"""Contract tests: schemas are valid, the examples conform, and the rules JSON Schema cannot
express (numbers in params) are enforced by contracts.checks."""
import copy
import json
import re
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contracts.checks import check_param_numbers

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"


def load(path):
    return json.loads(path.read_text())


@pytest.fixture
def claim():
    return load(CONTRACTS / "examples" / "claim_matchup.json")


@pytest.fixture(scope="module")
def claim_validator():
    return Draft202012Validator(load(CONTRACTS / "claim.schema.json"))


def errors(validator, obj):
    return [e.message for e in validator.iter_errors(obj)]


@pytest.mark.parametrize("schema_name", ["claim.schema.json", "insight.schema.json"])
def test_schema_is_valid(schema_name):
    Draft202012Validator.check_schema(load(CONTRACTS / schema_name))


@pytest.mark.parametrize(
    "schema_name,example_name",
    [
        ("claim.schema.json", "claim_matchup.json"),
        ("insight.schema.json", "insight_perimeter_lock.json"),
    ],
)
def test_example_conforms(schema_name, example_name):
    validator = Draft202012Validator(load(CONTRACTS / schema_name))
    assert not errors(validator, load(CONTRACTS / "examples" / example_name))


def test_claim_without_evidence_is_rejected(claim, claim_validator):
    claim["evidence_event_ids"] = []
    assert errors(claim_validator, claim)


def test_season_claim_needs_no_window(claim, claim_validator):
    assert claim["scope"] == "season" and "window" not in claim
    assert not errors(claim_validator, claim)


@pytest.mark.parametrize("scope", ["match", "window"])
def test_match_and_window_claims_require_window_and_match_id(claim, claim_validator, scope):
    claim["scope"] = scope
    assert errors(claim_validator, claim)                 # no window
    claim["window"] = {"from_sec": 0, "to_sec": 5400}
    assert not errors(claim_validator, claim)
    claim["match_id"] = None
    assert errors(claim_validator, claim)                 # window/match claims need a real match


def test_scope_is_required_and_enumerated(claim, claim_validator):
    bad = copy.deepcopy(claim)
    bad["scope"] = "career"
    assert errors(claim_validator, bad)
    del claim["scope"]
    assert errors(claim_validator, claim)


def test_new_value_fields_are_typed(claim, claim_validator):
    for field, bad in (("confidence", "certain"), ("interval", {"low": 1}),
                       ("baseline_source", {"kind": "match", "n": 3})):
        c = copy.deepcopy(claim)
        c["value"][field] = bad
        assert errors(claim_validator, c), field
    c = copy.deepcopy(claim)
    del c["value"]["z_score"]                             # z is optional
    assert not errors(claim_validator, c)


def test_example_params_numbers_are_backed(claim):
    assert check_param_numbers(claim) == []


def test_param_number_found_nowhere_is_rejected(claim):
    claim["params"]["concede_share"] = 41
    problems = check_param_numbers(claim)
    assert problems == ["params.concede_share=41 not in value.amount or supporting_values"]


def test_param_number_check_ignores_strings_and_bools(claim):
    claim["params"]["flag"] = True
    claim["params"]["label"] = "38%"
    assert check_param_numbers(claim) == []


def test_insight_example_rendered_text_carries_every_numeric_param():
    ins = load(CONTRACTS / "examples" / "insight_perimeter_lock.json")
    nums = [v for v in ins["text"]["params"].values() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    for lang in ins["text"]["rendered"].values():
        for text in lang.values():
            found = re.findall(r"\d+(?:\.\d+)?", text)
            for n in nums:
                assert str(n) in found, (n, text)
