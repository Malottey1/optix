"""OpenTelemetry spans for the agent pipeline:

    analyst.propose   one per proposal (claim_id, attempt, strategy, insight_type)
    verifier.check    claim_id, attempt, status (the verdict), fact_check, rule_ids
    phraser.call      claim_id, phraser, sources per language, guard result and rejections
    publish           claim_id, status, insight_type

The API (opentelemetry-api) is optional: without it every span is a no-op and the pipeline runs as
before. `setup_tracing()` picks the exporter once per process, from the environment:
  * APPLICATIONINSIGHTS_CONNECTION_STRING set -> Azure Monitor (Application Insights) exporter;
  * else OPTIX_TRACE_FILE set                 -> one JSON span per line in that file;
  * else OPTIX_TRACE_CONSOLE=1                -> console;
  * else nothing is exported.
The connection string is read from the environment only and never logged.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

try:
    from opentelemetry import trace as _trace
except ImportError:            # optional dependency (requirements-azure.txt)
    _trace = None

TRACER_NAME = "optix.agents"
_PROVIDER = None            # set by use_provider (tests); else the global provider


def use_provider(provider) -> None:
    """Send spans to `provider` instead of the global one (None restores the global provider).
    OpenTelemetry allows the global provider to be set once per process, so tests use this."""
    global _PROVIDER
    _PROVIDER = provider


def _clean(v):
    """Span attributes must be primitives or lists of primitives."""
    if isinstance(v, (str, bool, int, float)):
        return v
    if isinstance(v, (list, tuple)) and all(isinstance(x, (str, bool, int, float)) for x in v):
        return list(v)
    return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)


@contextmanager
def span(name: str, **attrs):
    """A span named `name` with `attrs`; yields a setter for attributes known only at the end."""
    if _trace is None:
        yield lambda **_: None
        return
    tracer = (_PROVIDER or _trace.get_tracer_provider()).get_tracer(TRACER_NAME)
    with tracer.start_as_current_span(name) as s:
        def put(**more):
            for k, v in more.items():
                if v is not None:
                    s.set_attribute(f"optix.{k}", _clean(v))
        put(**attrs)
        yield put


class JsonlSpanExporter:
    """Local exporter: one JSON object per finished span."""

    def __init__(self, path):
        self.path = path

    def export(self, spans):
        from opentelemetry.sdk.trace.export import SpanExportResult
        with open(self.path, "a", encoding="utf-8") as f:
            for s in spans:
                f.write(json.dumps({"name": s.name, "trace_id": format(s.context.trace_id, "032x"),
                                    "span_id": format(s.context.span_id, "016x"),
                                    "parent_id": format(s.parent.span_id, "016x") if s.parent else None,
                                    "start_ns": s.start_time, "end_ns": s.end_time,
                                    "attributes": dict(s.attributes or {})}, sort_keys=True) + "\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000):
        return True


_CONFIGURED = None


def build_provider(env=None, service_name: str = "optix"):
    """(TracerProvider, exporter kind) for the environment `env` (default os.environ)."""
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
    env = os.environ if env is None else env
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    conn = env.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if conn:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter
        provider.add_span_processor(BatchSpanProcessor(AzureMonitorTraceExporter.from_connection_string(conn)))
        return provider, "azure-monitor"
    if env.get("OPTIX_TRACE_FILE"):
        provider.add_span_processor(SimpleSpanProcessor(JsonlSpanExporter(env["OPTIX_TRACE_FILE"])))
        return provider, "jsonl"
    if env.get("OPTIX_TRACE_CONSOLE") == "1":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        return provider, "console"
    return provider, "none"


def setup_tracing(service_name: str = "optix") -> str:
    """Install the global tracer provider with the exporter the environment asks for; returns which
    one ("azure-monitor", "jsonl", "console", "none" or "unavailable"). Safe to call more than once."""
    global _CONFIGURED
    if _CONFIGURED is not None:
        return _CONFIGURED
    if _trace is None:
        _CONFIGURED = "unavailable"
        return _CONFIGURED
    provider, kind = build_provider(service_name=service_name)
    _trace.set_tracer_provider(provider)
    _CONFIGURED = kind
    return kind
