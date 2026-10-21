"""Structured logs: one JSON object per agent action, kept in memory and optionally written as JSONL."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

LOGGER = logging.getLogger("optix.agents")


class AgentLog:
    def __init__(self, path: str | Path | None = None):
        self.records: list = []
        self.path = Path(path) if path else None

    def __call__(self, agent: str, event: str, **fields):
        rec = {"ts_ms": int(time.time() * 1000), "agent": agent, "event": event, **fields}
        self.records.append(rec)
        LOGGER.debug(json.dumps(rec, sort_keys=True))
        return rec

    def where(self, **match):
        return [r for r in self.records if all(r.get(k) == v for k, v in match.items())]

    def flush(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", newline="\n") as f:
                for r in self.records:
                    f.write(json.dumps(r, sort_keys=True) + "\n")
