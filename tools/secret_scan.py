"""Secret scan of the working tree (tracked files) and, with --history, every committed blob.

    python -m tools.secret_scan              # tracked files
    python -m tools.secret_scan --history    # plus every blob in git history

Looks for private keys, cloud access keys, Azure storage / Application Insights / Service Bus
connection secrets, OpenAI-style and Azure OpenAI-style keys, bearer tokens and key=value
assignments with a literal value. Known test fixtures (the all-zero instrumentation key used to build
the exporter without sending anything) are allowed explicitly. Exit 1 on any finding; values are
never printed, only file, line and rule.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys

RULES = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "storage account key": re.compile(r"AccountKey=[A-Za-z0-9+/=]{20,}"),
    "shared access key": re.compile(r"SharedAccessKey=[A-Za-z0-9+/=]{20,}"),
    "instrumentation key": re.compile(r"InstrumentationKey=([0-9a-f-]{36})", re.I),
    "openai-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "azure openai key": re.compile(r"(?i)(api[-_]?key|openai[-_]?key)\s*[:=]\s*['\"]?[0-9a-f]{32}\b"),
    "bearer token": re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{30,}"),
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "literal secret assignment": re.compile(
        r"(?i)\b(password|passwd|client_secret|api_key|apikey|secret_key)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
}
ALLOWED = {("instrumentation key", "00000000-0000-0000-0000-000000000000")}
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".woff", ".woff2", ".ico", ".pdf")


def scan_text(name: str, text: str) -> list:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for rule, rx in RULES.items():
            for m in rx.finditer(line):
                val = m.group(1) if m.groups() else m.group(0)
                if (rule, val) not in ALLOWED:
                    out.append(f"{name}:{i}: {rule}")
    return out


def _git(*args) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def tracked() -> list:
    out = []
    for f in _git("ls-files").splitlines():
        if f.endswith(SKIP_SUFFIXES):
            continue
        try:
            out += scan_text(f, open(f, encoding="utf-8", errors="replace").read())
        except (FileNotFoundError, IsADirectoryError):
            pass
    return out


def history() -> list:
    """Every blob reachable from any ref (each scanned once)."""
    out, seen = [], set()
    for line in _git("rev-list", "--all", "--objects").splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2 or parts[0] in seen or parts[1].endswith(SKIP_SUFFIXES):
            continue
        seen.add(parts[0])
        kind = _git("cat-file", "-t", parts[0]).strip()
        if kind != "blob":
            continue
        data = subprocess.run(["git", "cat-file", "-p", parts[0]], capture_output=True).stdout
        out += scan_text(f"{parts[1]}@{parts[0][:8]}", data.decode("utf-8", errors="replace"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--history", action="store_true")
    a = ap.parse_args(argv)
    found = tracked() + (history() if a.history else [])
    for f in sorted(set(found)):
        print(f)
    print(f"secret scan ({'tree + history' if a.history else 'tree'}): {len(set(found))} findings")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
