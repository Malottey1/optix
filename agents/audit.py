"""Audit log: an append-only JSONL file with a hash chain, so any edit, deletion or reordering of a
past record is detectable (tamper-evident; it does not stop anyone from rewriting the whole file and
its chain, so keep the last hash somewhere else if that matters).

Each line is {"seq", "ts", "kind", "data", "prev", "hash"}: `prev` is the previous record's hash
("0" * 64 for the first) and `hash` = sha256 of the canonical JSON of the record without `hash`.

    python -m agents.audit verify out/audit.jsonl     # exit 0 if the chain is intact
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64


def _digest(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class AuditLog:
    """Append-only: records are only ever added at the end; nothing here rewrites a line."""

    def __init__(self, path: str | Path, clock=None):
        self.path = Path(path)
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
        self.seq, self.last = 0, GENESIS
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.seq, self.last = rec["seq"] + 1, rec["hash"]

    def append(self, kind: str, data: dict) -> dict:
        rec = {"seq": self.seq, "ts": self.clock(), "kind": kind, "data": data, "prev": self.last}
        rec["hash"] = _digest(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
        self.seq, self.last = self.seq + 1, rec["hash"]
        return rec


def verify(path: str | Path) -> list:
    """Problems in the chain (empty list = intact)."""
    problems, prev = [], GENESIS
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"line {i + 1}: not JSON")
            prev = None
            continue
        if rec.get("seq") != i:
            problems.append(f"line {i + 1}: seq {rec.get('seq')} != {i}")
        if prev is not None and rec.get("prev") != prev:
            problems.append(f"line {i + 1}: prev does not match the hash of line {i}")
        if rec.get("hash") != _digest(rec):
            problems.append(f"line {i + 1}: hash does not match its content")
        prev = rec.get("hash")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a hash-chained audit log.")
    ap.add_argument("command", choices=("verify",))
    ap.add_argument("path", type=Path)
    a = ap.parse_args(argv)
    problems = verify(a.path)
    n = sum(1 for l in a.path.read_text(encoding="utf-8").splitlines() if l.strip())
    if problems:
        print(f"{a.path}: chain BROKEN ({len(problems)} problems)")
        for p in problems:
            print("  " + p)
        return 1
    print(f"{a.path}: chain intact, {n} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
