"""Status of every Microsoft / Azure piece, derived from facts in the repo, never typed by hand.

Three states:
  * "verified live"              the live check (docs/azure-live-check.md) ran against Azure and the
                                 component took part in it;
  * "verified by tests"          its tests exist in the default suite and exercise the real code
                                 (fakes only where a network service would be);
  * "verified by CI build/lint"  a finished GitHub Actions run built or compiled it successfully, as
                                 recorded in infra/ci-verified.json (tools/ci_record.py);
  * "built, not verified live"   the code or file exists, but nothing has run it against Azure;
  * "not built"                  nothing exists.
The first that applies wins. Used by docs/AZURE.md (`python -m agents.azure_status --write`) and by
ui.json (`azure_status`, the Tech Blueprint's status list). tests/test_azure_status.py keeps both in
step with this module. No text here contains a digit, so the dashboard's number tracer has nothing
to trace.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE_REPORT = ROOT / "docs" / "azure-live-check.md"
CI_RECORD = ROOT / "infra" / "ci-verified.json"
CI_JOB = {"container": "docker-build", "iac": "bicep-build"}     # component -> CI job that verifies it

VERIFIED_LIVE = "verified live"
VERIFIED_TESTS = "verified by tests"
VERIFIED_CI = "verified by CI build/lint"
BUILT = "built, not verified live"
NOT_BUILT = "not built"

# id, name, Microsoft technology, files that must exist, tests that verify it (empty = none that
# exercise it for real), takes part in the live check, plain note
COMPONENTS = [
    ("workflow", "Agent workflow", "Microsoft Agent Framework (agent-framework-core)",
     ["agents/workflow.py"], ["tests/test_workflow.py"], False,
     "Analyst, Verifier, Phraser and Publisher executors with a block-and-revise conditional edge; "
     "same stream as the direct pipeline. Runs locally, needs no Azure resource."),
    ("guard", "Output guard and template fallback", "Applies to any model output",
     ["agents/output_guard.py", "agents/phraser.py"], ["tests/test_phraser.py"], False,
     "Altered or invented numbers, other teams, talk of future results, wrong decimal separator, over-length, "
     "wrong language and malformed JSON are rejected and replaced by the template, with a fake model client."),
    ("phraser", "Model phrasing client", "Azure OpenAI in Azure AI Foundry, Microsoft Entra ID (DefaultAzureCredential)",
     ["agents/phraser.py"], [], True,
     "Calls a chat deployment with the claim object only; the guard above decides what is kept."),
    ("cache", "Phrasing cache", "Local files (data/phrasing-cache)",
     ["data/phrasing-cache/README.md"], ["tests/test_phraser.py"], False,
     "Accepted replies keyed by claim hash, deployment and prompt version; re-guarded on replay. "
     "Holds no model sentences until a live run writes some."),
    ("otel", "Spans for every agent step", "OpenTelemetry",
     ["agents/telemetry.py"], ["tests/test_telemetry.py"], False,
     "Proposal, verdict with rule ids, phraser with guard result, publication; checked with an in-memory exporter."),
    ("appinsights", "Telemetry export", "Azure Monitor / Application Insights",
     ["agents/telemetry.py", "infra/main.bicep"], [], True,
     "The exporter is built from APPLICATIONINSIGHTS_CONNECTION_STRING; no span has been sent to a real resource."),
    ("audit", "Audit log", "Append-only JSONL with a hash chain",
     ["agents/audit.py"], ["tests/test_audit.py"], False,
     "Tamper-evident: an edited, removed or reordered record fails verification."),
    ("service", "Live stream service", "FastAPI with server-sent events",
     ["service/app.py"], ["tests/test_service.py"], False,
     "Health, matches, the SSE replay at a chosen speed and claim attempts; the dashboard shows Live stream "
     "when served by it and Replay otherwise."),
    ("container", "Container image", "Docker (multi-stage, non-root)",
     ["Dockerfile", "docker-compose.yml"], [], False,
     "Checked statically; not built on the machine that produced this build."),
    ("iac", "Infrastructure as code", "Bicep: Azure Container Apps, Log Analytics, managed identity",
     ["infra/main.bicep", "infra/deploy.md"], [], False,
     "System-assigned identity with one least-privilege role on the Azure OpenAI resource. "
     "Not linted with the Bicep CLI here and never deployed."),
    ("eventhubs", "Event ingestion from a hub", "Azure Event Hubs",
     [], [], False, "Events are replayed from files; no Event Hubs adapter exists."),
]


# the note once a CI run verified it (no digits: the dashboard's number tracer reads these)
CI_NOTE = {
    "container": "Built by the CI job docker-build (not pushed), and the container answered its health check there.",
    "iac": "Compiled by az bicep build in the CI job bicep-build, parameters too. Never deployed.",
}


def live_check_ran(report: Path = LIVE_REPORT) -> bool:
    """True only when the live report exists and does not say it was not run."""
    if not report.exists():
        return False
    return "Not run" not in report.read_text(encoding="utf-8")


def ci_record(root: Path = ROOT) -> dict | None:
    p = root / "infra" / "ci-verified.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ci_passed(cid: str, root: Path = ROOT) -> bool:
    """True only when the recorded CI run finished the component's job with success."""
    rec = ci_record(root)
    return bool(rec and cid in CI_JOB and rec.get("jobs", {}).get(CI_JOB[cid]) == "success")


def status(root: Path = ROOT) -> list:
    live = live_check_ran(root / "docs" / "azure-live-check.md")
    out = []
    for cid, name, tech, files, tests, in_live, note in COMPONENTS:
        built = bool(files) and all((root / f).exists() for f in files)
        tested = bool(tests) and all((root / t).exists() for t in tests)
        state = (VERIFIED_LIVE if in_live and live and built else VERIFIED_TESTS if tested and built
                 else VERIFIED_CI if built and ci_passed(cid, root) else BUILT if built else NOT_BUILT)
        if state == VERIFIED_CI:
            note = CI_NOTE[cid]
        out.append(dict(id=cid, name=name, tech=tech, state=state, files=files, tests=tests, note=note,
                        live=VERIFIED_LIVE if (in_live and live) else "not run" if in_live else "not applicable"))
    return out


DIAGRAM = """```mermaid
flowchart LR
  subgraph local["Runs anywhere, no Azure needed"]
    EV[(event files)] --> WF
    subgraph WF["Microsoft Agent Framework workflow"]
      AN[Analyst] --> VE[Verifier<br/>deterministic engine]
      VE -- blocked --> AN
      VE -- approved --> PH[Phraser]
      PH --> PU[Publisher]
    end
    PH --> GU{{output guard<br/>+ number guard}}
    PU --> AU[(hash-chained audit log)]
    PU --> ST[(insight stream)]
    ST --> API[FastAPI SSE service] --> UI[dashboard: Live stream / Replay]
  end
  subgraph azure["Azure services (status in the table below)"]
    AOAI[Azure OpenAI in Foundry<br/>Entra ID, managed identity]
    AI[Application Insights]
    ACA[Azure Container Apps]
  end
  PH -. claim object only .-> AOAI
  AOAI -. reply .-> GU
  WF -. OpenTelemetry spans .-> AI
  API -. container image .-> ACA
```"""


def render(root: Path = ROOT) -> str:
    rows = status(root)
    lines = ["# Azure integration", "",
             "Optix keeps its core promise with or without Azure: every number is computed and verified by the "
             "deterministic engine before any sentence exists, and a model can only reword a claim the Verifier "
             "already approved, behind a guard that falls back to the template on any doubt.", "",
             DIAGRAM, "",
             "## Status", "",
             "Generated by `python -m agents.azure_status --write` from the files, tests and the live-check report "
             "(tests/test_azure_status.py fails if this table drifts). States: **verified live**, "
             "**verified by tests**, **verified by CI build/lint**, **built, not verified live**, **not built**.", "",
             "| Component | Technology | Status | Live check | Evidence | Note |", "|---|---|---|---|---|---|"]
    for r in rows:
        ev = ", ".join(f"`{t}`" for t in r["tests"]) or ", ".join(f"`{f}`" for f in r["files"]) or "none"
        if r["state"] == VERIFIED_CI:
            rec = ci_record(root)
            ev += f", [CI run {rec['run_id']}]({rec['url']}) at `{rec['head_sha'][:7]}`"
        lines.append(f"| {r['name']} | {r['tech']} | **{r['state']}** | {r['live']} | {ev} | {r['note']} |")
    lines += ["", "Live check: " + ("ran, see docs/azure-live-check.md." if live_check_ran(root / "docs" / "azure-live-check.md")
                                     else "not run (no Azure configuration present); see docs/azure-live-check.md "
                                          "for the steps."),
              "", "## Where things are", "",
              "- Phrasing layer and guard: `agents/phraser.py`, `agents/output_guard.py` (docs/ARCHITECTURE.md).",
              "- Workflow: `agents/workflow.py`; run with `python -m agents.run_match --engine workflow`.",
              "- Spans and audit: `agents/telemetry.py`, `agents/audit.py` (`python -m agents.audit verify FILE`).",
              "- Service: `service/app.py` (`uvicorn service.app:app`), dashboard wiring in `web/src/data/SseSource.ts`.",
              "- Container and Bicep: `Dockerfile`, `docker-compose.yml`, `infra/`; deploy steps in `infra/deploy.md`.",
              "- Configuration: `.env.example` (copy to the gitignored `.env`); Entra ID via `az login`, no keys in the repo.",
              ""]
    return "\n".join(lines)


README_START, README_END = "<!-- azure-status:start -->", "<!-- azure-status:end -->"


def readme_block(root: Path = ROOT) -> str:
    """The README's status list (between the markers), from the same facts."""
    lines = [README_START, "", "| Component | Technology | Status |", "|---|---|---|"]
    lines += [f"| {r['name']} | {r['tech']} | {r['state']} |" for r in status(root)]
    lines += ["", "Details, evidence and the diagram: `docs/AZURE.md`. Generated by "
              "`python -m agents.azure_status --write`.", "", README_END]
    return "\n".join(lines)


def with_readme_block(text: str, root: Path = ROOT) -> str:
    a, b = text.index(README_START), text.index(README_END) + len(README_END)
    return text[:a] + readme_block(root) + text[b:]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Azure status table from repo facts.")
    ap.add_argument("--write", action="store_true", help="write docs/AZURE.md")
    a = ap.parse_args(argv)
    text = render()
    if a.write:
        (ROOT / "docs" / "AZURE.md").write_text(text, encoding="utf-8")
        readme = ROOT / "README.md"
        readme.write_text(with_readme_block(readme.read_text(encoding="utf-8")), encoding="utf-8")
        print("wrote docs/AZURE.md and the README status block")
    else:
        print(text)


if __name__ == "__main__":
    main()
