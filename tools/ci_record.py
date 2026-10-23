"""Record a finished GitHub Actions run of the infrastructure jobs as a repo fact.

    python -m tools.ci_record <run id>       # writes infra/ci-verified.json

Reads the run with `gh run view` (read-only) and keeps the jobs `docker-build` and `bicep-build`
with their conclusions, the run's commit and URL. agents/azure_status.py marks the container image
and the Bicep "verified by CI build/lint" only when this file records a successful run of that job.
Nothing is recorded for a run that has not finished.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORD = ROOT / "infra" / "ci-verified.json"
JOBS = ("docker-build", "bicep-build")


def record_from(view: dict) -> dict:
    if view.get("status") != "completed":
        raise SystemExit(f"run not finished (status {view.get('status')!r}); nothing recorded")
    jobs = {j["name"]: j["conclusion"] for j in view.get("jobs", []) if j["name"] in JOBS}
    return {"run_id": view["databaseId"], "head_sha": view["headSha"], "head_branch": view.get("headBranch"),
            "url": view["url"], "workflow": view.get("workflowName"), "jobs": {k: jobs.get(k) for k in JOBS}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("run_id")
    a = ap.parse_args(argv)
    out = subprocess.run(["gh", "run", "view", a.run_id, "--json",
                          "databaseId,headSha,headBranch,url,workflowName,status,conclusion,jobs"],
                         capture_output=True, text=True, check=True).stdout
    rec = record_from(json.loads(out))
    RECORD.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"recorded run {rec['run_id']}: {rec['jobs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
