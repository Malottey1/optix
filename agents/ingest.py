"""Ingest agent: deduplicate raw event rows and flag rows missing the fields their type needs.

Dropped rows are reported, never repaired: guessing a missing coordinate would be inventing data.
"""
from __future__ import annotations

from .messages import IngestReport

REQUIRED = ("event_id", "match_id", "clock_sec", "team_id", "event_type", "x_start", "y_start", "outcome")
REQUIRED_BY_TYPE = {"pass": ("player_id", "x_end", "y_end"), "shot": ("player_id",)}


def missing_fields(row: dict, passes: dict | None = None, shots: dict | None = None) -> list:
    need = REQUIRED + REQUIRED_BY_TYPE.get(row.get("event_type"), ())
    miss = [k for k in need if row.get(k) in (None, "")]
    if row.get("event_type") == "pass" and passes is not None and row.get("event_id") not in passes:
        miss.append("passes_row")
    if row.get("event_type") == "shot" and shots is not None and row.get("event_id") not in shots:
        miss.append("shots_row")
    return miss


class IngestAgent:
    name = "ingest"

    def __init__(self, log, passes: dict | None = None, shots: dict | None = None):
        self.log, self.passes, self.shots = log, passes, shots

    def process(self, rows, state) -> tuple[list, IngestReport]:
        """Rows -> (clean new events in order, report). Updates nothing; the Orchestrator commits."""
        clean, dups, missing = [], [], {}
        seen = set()
        for r in rows:
            eid = r.get("event_id")
            if eid in state.seen_ids or eid in seen:
                dups.append(eid)
                continue
            miss = missing_fields(r, self.passes, self.shots)
            if miss:
                missing[eid] = miss
                continue
            seen.add(eid)
            clean.append(r)
        rep = IngestReport(len(clean), tuple(dups), missing)
        if dups or missing:
            self.log(self.name, "rows_dropped", match_id=state.match_id, duplicates=list(dups),
                     missing_fields=missing)
        return clean, rep
