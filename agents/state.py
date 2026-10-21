"""Per-match state store: everything the agents know about the match so far.

Only the Orchestrator writes it. Agents read it; the Analyst keeps its rolling counters here so a
new event costs O(1) work, not a recompute over the match (the latency budget in Step 7).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace

from engine.tables import Dataset


@dataclass
class MatchState:
    match_id: str
    home_id: str
    away_id: str
    events: list = field(default_factory=list)          # ingested (clean) events, in order
    seen_ids: set = field(default_factory=set)
    clock: int = 0
    score: tuple = (0, 0)
    # rolling counters (updated per event by the Analyst)
    shots: dict = field(default_factory=lambda: defaultdict(int))
    completed_passes: dict = field(default_factory=lambda: defaultdict(int))   # player -> n
    last_emit: dict = field(default_factory=dict)       # (insight key) -> clock of last emission
    momentum_sign: int = 0
    # outcomes
    published: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    _view: Dataset | None = None
    _view_n: int = -1

    def team_ids(self):
        return self.home_id, self.away_id

    def opponent(self, team_id: str) -> str:
        return self.away_id if team_id == self.home_id else self.home_id

    def view(self, ds: Dataset) -> Dataset:
        """The match dataset restricted to ingested events so far (what the Verifier may see).
        Rebuilt only when new events arrived since the last call."""
        if self._view_n != len(self.events):
            self._view = replace(ds, events=list(self.events))
            self._view_n = len(self.events)
        return self._view
