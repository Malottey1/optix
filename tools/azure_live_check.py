"""Live check against a real Azure OpenAI / Azure AI Foundry deployment, with a hard call cap.

    python -m tools.azure_live_check            # writes docs/azure-live-check.md

Runs only when AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT are set (environment or the
gitignored .env) and `az account show` succeeds (Microsoft Entra ID sign-in). Then, at most
MAX_LIVE_CALLS (10) model calls: a few verified showcase claims phrased in en, es and fr through
AzureOpenAIPhraser, each reply through the output guard, spans captured in memory, accepted replies
written to data/phrasing-cache/. Otherwise it writes the report saying it was not run and why.
The report never contains a key, a token or the endpoint's host name.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from agents.config import load_env

ROOT = Path(__file__).resolve().parent.parent
MAX_LIVE_CALLS = 10
LANGS = ("en", "es", "fr")

STEPS = """## How to run it

1. `az login` (Microsoft Entra ID; the phraser uses DefaultAzureCredential, no key needed).
2. Give your user the **Cognitive Services OpenAI User** role on the Azure OpenAI / Foundry resource.
3. Copy `.env.example` to `.env` and set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT`
   (optional: `AZURE_OPENAI_API_VERSION`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).
4. `pip install -r requirements-azure.txt`
5. `python -m tools.azure_live_check` (at most 10 model calls), then
   `python -m pytest -m azure_live` for the live tests.
"""


def preconditions() -> tuple[bool, list]:
    """(ready, reasons it is not)."""
    from agents.phraser import azure_configured
    reasons = []
    if not azure_configured():
        reasons.append("AZURE_OPENAI_ENDPOINT and/or AZURE_OPENAI_DEPLOYMENT not set")
    if shutil.which("az") is None:
        reasons.append("Azure CLI (`az`) not installed, so no `az account show`")
    else:
        r = subprocess.run(["az", "account", "show", "--output", "none"], capture_output=True, text=True)
        if r.returncode != 0:
            reasons.append("`az account show` failed (not signed in)")
    return not reasons, reasons


def _claims(n: int = 3):
    """A few verified claims from the committed showcase replay, the ones with the most numbers first."""
    rows = [json.loads(l) for l in (ROOT / "web/public/data/claims.jsonl").read_text(encoding="utf-8").splitlines()]
    ok = [r["claim"] for r in rows if r["claim"]["verification"]["status"] in ("published", "published_with_context")]
    seen, out = set(), []
    for c in sorted(ok, key=lambda c: -sum(isinstance(v, (int, float)) for v in c["params"].values())):
        if c["template_key"] not in seen:
            seen.add(c["template_key"])
            out.append(c)
    return out[:n]


def run_live(max_calls: int = MAX_LIVE_CALLS) -> dict:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from agents import telemetry
    from agents.narrative import NarrativeAgent
    from agents.phraser import AzureChatClient, AzureOpenAIPhraser, PhrasingCache, known_entities
    from engine.tables import load

    ds = load(ROOT / "data/showcase")
    known, names = known_entities(ds)
    client = AzureChatClient()
    phraser = AzureOpenAIPhraser(client, known, names, cache=PhrasingCache(), max_calls=max_calls)
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    telemetry.use_provider(provider)
    rows = []
    try:
        agent = NarrativeAgent(lambda *a, **k: None, LANGS, phraser)
        for c in _claims():
            text = agent.write(c)
            res = agent.last_phrase
            rows.append(dict(claim_id=c["claim_id"], template_key=c["template_key"], source=res.source,
                             guard_rejected=res.guard_rejected, number_guard_passed=text.number_guard_passed,
                             casual={l: text.rendered[l]["casual"] for l in LANGS}))
    finally:
        telemetry.use_provider(None)
    spans = [s for s in exp.get_finished_spans() if s.name == "phraser.call"]
    return dict(calls=phraser.calls, auth=client.auth, deployment=client.deployment, rows=rows,
                spans=[dict(s.attributes) for s in spans])


def report(result: dict | None, reasons: list) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if result is None:
        return ("# Azure live check\n\n"
                f"**Not run: no Azure configuration present** ({now}).\n\n"
                + "".join(f"- {r}\n" for r in reasons)
                + "\nNothing in this repo has been verified against a live Azure service. Everything Azure-related "
                  "is \"built, not verified live\" (see docs/AZURE.md).\n\n" + STEPS)
    acc = sum(1 for r in result["rows"] for l in LANGS if r["source"].get(l) in ("model", "cache"))
    rej = sum(len(r["guard_rejected"]) for r in result["rows"])
    lines = ["# Azure live check", "", f"Run {now}: deployment `{result['deployment']}`, auth {result['auth']}, "
             f"{result['calls']} model calls (cap {MAX_LIVE_CALLS}).", "",
             f"- sentences accepted by the output guard: {acc}; rejected (template used): {rej}",
             f"- phraser.call spans captured: {len(result['spans'])}",
             f"- number guard passed on every sentence: {all(r['number_guard_passed'] for r in result['rows'])}", "",
             "| claim | language | source | guard | casual sentence |", "|---|---|---|---|---|"]
    for r in result["rows"]:
        for l in LANGS:
            g = "; ".join(r["guard_rejected"].get(l, [])) or "accepted"
            lines.append(f"| `{r['template_key']}` | {l} | {r['source'].get(l)} | {g} | {r['casual'][l]} |")
    return "\n".join(lines) + "\n\n" + STEPS


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "azure-live-check.md")
    ap.add_argument("--max-calls", type=int, default=MAX_LIVE_CALLS)
    a = ap.parse_args(argv)
    load_env()
    ready, reasons = preconditions()
    result = run_live(min(a.max_calls, MAX_LIVE_CALLS)) if ready else None
    a.out.write_text(report(result, reasons), encoding="utf-8")
    print(f"{'ran' if ready else 'not run'}: {a.out}" + ("" if ready else f" ({'; '.join(reasons)})"))
    return result


if __name__ == "__main__":
    main()
