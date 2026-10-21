"""Contract tests: schemas are valid and the examples conform to them."""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"


def load(path):
    return json.loads(path.read_text())


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
    errors = list(validator.iter_errors(load(CONTRACTS / "examples" / example_name)))
    assert not errors, [e.message for e in errors]


def test_claim_without_evidence_is_rejected():
    validator = Draft202012Validator(load(CONTRACTS / "claim.schema.json"))
    claim = load(CONTRACTS / "examples" / "claim_matchup.json")
    claim["evidence_event_ids"] = []
    assert list(validator.iter_errors(claim))
