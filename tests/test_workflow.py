"""The Agent Framework workflow (agents/workflow.py) is the same pipeline: with the template
phraser its stream equals the direct pipeline's, blocked claims go back over the conditional edge,
and the function tools are called by the Verifier executor."""
import json

import pytest

from agents.stream import InsightStream
from data_gen.generate import main as generate
from engine.tables import load

MID = "m_showcase"
LANGS = ("en", "es", "fr")


@pytest.fixture(scope="module")
def ds(tmp_path_factory):
    root = tmp_path_factory.mktemp("workflow")
    generate(2026, root / "season", root / "showcase")
    return load(root / "showcase", baseline="season", season_dir=root / "season")


@pytest.fixture(scope="module")
def both(ds):
    direct = InsightStream(ds, MID, languages=LANGS)
    direct.run()
    wf = InsightStream(ds, MID, languages=LANGS, engine="workflow")
    wf.run()
    return direct, wf


def _strip(ins):
    ins = json.loads(json.dumps(ins))
    ins["clock"].pop("emitted_latency_ms")
    return ins


def _attempts(s):
    out = []
    for a in s.attempts():
        a = json.loads(json.dumps(a))
        a["claim"]["verification"].pop("verified_at", None)
        out.append(a)
    return out


def test_workflow_stream_equals_the_direct_pipeline(both):
    direct, wf = both
    assert direct.insights
    assert [_strip(i) for i in wf.insights] == [_strip(i) for i in direct.insights]


def test_workflow_attempts_and_drops_equal_the_direct_pipeline(both):
    direct, wf = both
    assert _attempts(wf) == _attempts(direct)
    assert wf.orc.state.dropped == direct.orc.state.dropped


def test_blocked_claims_were_revised_through_the_conditional_edge(both):
    _, wf = both
    revised = [a for a in wf.attempts() if a["revision_of"]]
    assert revised, "the showcase has blocked-then-rewritten claims"
    assert all(a["claim"]["verification"]["attempt"] > 1 for a in revised)


def test_the_verifier_executor_calls_the_function_tools(both):
    _, wf = both
    calls = wf.orc.log.where(agent="verifier", event="tools")
    verified = wf.orc.log.where(agent="verifier", event="verified")
    assert len(calls) == len(verified) > 0
    assert all(c["evidence_found"] <= c["evidence_cited"] for c in calls)
    assert any(c["recomputed_amount"] is not None for c in calls)


def test_the_workflow_graph():
    from agents.workflow import build_workflow

    class Stub:
        on_published = None
    wf = build_workflow(Stub())
    ids = {e.id for e in wf.get_executors_list()}
    assert ids == {"analyst", "verifier", "phraser", "publisher"}
    assert wf.get_start_executor().id == "analyst"
