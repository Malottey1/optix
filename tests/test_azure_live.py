"""Live Azure tests: real model calls, so they are marked `azure_live` and skipped (and counted as
skipped) unless the Azure settings are present and `az account show` succeeds. CI never sets them."""
import pytest

from agents.config import load_env
from tools.azure_live_check import LANGS, preconditions, run_live

load_env()
READY, REASONS = preconditions()
pytestmark = [pytest.mark.azure_live,
              pytest.mark.skipif(not READY, reason="azure_live: " + "; ".join(REASONS))]


def test_live_phrasing_is_guarded_and_capped():
    r = run_live(max_calls=3)
    assert 0 < r["calls"] <= 3
    assert all(row["number_guard_passed"] for row in r["rows"])
    assert len(r["spans"]) == len(r["rows"])
    for row in r["rows"]:
        for lang in LANGS:
            assert row["source"][lang] in ("model", "cache") or row["guard_rejected"][lang]


def test_entra_id_is_used_when_no_key_is_set(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    from agents.phraser import AzureChatClient
    assert AzureChatClient().auth == "entra-id"
