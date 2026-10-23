"""OpenTelemetry spans of the agent pipeline, captured with an in-memory exporter."""
import json

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from agents import telemetry
from agents.stream import InsightStream
from data_gen.generate import main as generate
from engine.tables import load

EXPORTER = InMemorySpanExporter()


@pytest.fixture(scope="module")
def spans(tmp_path_factory):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(EXPORTER))
    telemetry.use_provider(provider)
    root = tmp_path_factory.mktemp("otel")
    generate(2026, root / "season", root / "showcase")
    ds = load(root / "showcase", baseline="season", season_dir=root / "season")
    EXPORTER.clear()
    try:
        s = InsightStream(ds, "m_showcase", languages=("en", "es"))
        s.run()
    finally:
        telemetry.use_provider(None)
    return s, EXPORTER.get_finished_spans()


def _by(spans, name):
    return [s for s in spans if s.name == name]


def test_every_stage_has_spans(spans):
    s, sp = spans
    attempts = s.attempts()
    assert len(_by(sp, "verifier.check")) >= len(attempts)
    assert len(_by(sp, "publish")) == len(s.insights)
    assert len(_by(sp, "phraser.call")) == len(s.insights)
    assert len(_by(sp, "analyst.propose")) == len(_by(sp, "verifier.check"))


def test_verifier_spans_carry_rule_and_verdict(spans):
    _, sp = spans
    v = _by(sp, "verifier.check")
    statuses = {x.attributes["optix.status"] for x in v}
    assert {"published", "blocked"} <= statuses
    blocked = [x for x in v if x.attributes["optix.status"] == "blocked"]
    assert all(len(x.attributes["optix.rule_ids"]) > 0 for x in blocked)
    assert all("optix.fact_check" in x.attributes for x in v)


def test_phraser_spans_carry_the_guard_result(spans):
    _, sp = spans
    p = _by(sp, "phraser.call")
    assert all(x.attributes["optix.phraser"] == "template" for x in p)
    assert all(x.attributes["optix.guard_result"] == "accepted" for x in p)
    assert all(x.attributes["optix.number_guard_passed"] is True for x in p)
    assert json.loads(p[0].attributes["optix.source"]) == {"en": "template", "es": "template"}


def test_publish_spans_name_the_claim(spans):
    s, sp = spans
    assert [x.attributes["optix.claim_id"] for x in _by(sp, "publish")] == [i["claim_id"] for i in s.insights]


def test_exporter_choice_from_the_environment(tmp_path):
    _, kind = telemetry.build_provider({})
    assert kind == "none"
    f = tmp_path / "spans.jsonl"
    provider, kind = telemetry.build_provider({"OPTIX_TRACE_FILE": str(f)})
    assert kind == "jsonl"
    with provider.get_tracer("t").start_as_current_span("verifier.check") as sp:
        sp.set_attribute("optix.status", "published")
    rec = json.loads(f.read_text().splitlines()[0])
    assert rec["name"] == "verifier.check" and rec["attributes"] == {"optix.status": "published"}
    # a well-formed but fake connection string: the exporter is built, nothing is sent
    fake = "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://example.invalid/"
    provider, kind = telemetry.build_provider({"APPLICATIONINSIGHTS_CONNECTION_STRING": fake})
    assert kind == "azure-monitor"
    provider.shutdown()
