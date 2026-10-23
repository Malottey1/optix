"""Optix API: serves the dashboard and replays a match's verified insights as server-sent events.

    uvicorn service.app:app --port 8000          # then open http://127.0.0.1:8000/#/live

Endpoints
  GET /healthz                          liveness: {"status": "ok", "service": "optix", "matches": n}
  GET /api/matches                      the matches in the data directory (id, teams, duration)
  GET /api/match/{id}/stream?speed=60   SSE replay: `event: insight` per verified insight at its match
                                        clock, `event: tick` every TICK_SEC match seconds, `event: end`
  GET /api/claims/{claim_id}            every verification attempt of one claim, first attempt first
  /                                     web/dist (the built dashboard), when it exists

The stream replays what the engine already verified and wrote (insights.jsonl): the service never
computes, phrases or changes an insight. Config comes from the environment only:
  OPTIX_DATA_DIR  engine output to serve (default web/public/data; one match per directory)
  OPTIX_WEB_DIST  the built dashboard (default web/dist)
  OPTIX_MAX_SPEED fastest replay allowed (default 600; speed = match seconds per real second)
No CORS middleware: the dashboard is served from the same origin.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from agents.config import load_env

ROOT = Path(__file__).resolve().parent.parent
TICK_SEC = 30


def _jsonl(path: Path) -> list:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


class MatchStore:
    """The engine output of one match directory (insights.jsonl, claims.jsonl, timeline.json)."""

    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.timeline = json.loads((self.dir / "timeline.json").read_text(encoding="utf-8"))
        self.insights = sorted(_jsonl(self.dir / "insights.jsonl"), key=lambda i: i["clock"]["start_sec"])
        self.claims: dict = {}
        for a in _jsonl(self.dir / "claims.jsonl"):
            self.claims.setdefault(a["claim"]["claim_id"], a)
        self.match_id = self.timeline["match_id"]

    def chain(self, claim_id: str) -> list:
        out, a = [], self.claims.get(claim_id)
        while a is not None:
            out.insert(0, a)
            a = self.claims.get(a["revision_of"]) if a.get("revision_of") else None
        return out

    def summary(self) -> dict:
        t = self.timeline
        return {"match_id": self.match_id, "home": t["home"], "away": t["away"],
                "duration_sec": t["duration_sec"], "insights": len(self.insights)}


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, sort_keys=True)}\n\n"


async def replay(store: MatchStore, speed: float, start: int = 0, sleep=asyncio.sleep):
    """SSE frames for one match: each insight when the match clock reaches its start_sec, a tick
    every TICK_SEC match seconds in between, then `end`. `sleep` is injectable (a fake clock in tests)."""
    duration = store.timeline["duration_sec"]
    clock = start
    pending = [i for i in store.insights if i["clock"]["start_sec"] >= start]
    yield sse("hello", {"match_id": store.match_id, "speed": speed, "start_sec": start, "duration_sec": duration})
    while clock < duration or pending:
        nxt_tick = min(clock + TICK_SEC - clock % TICK_SEC, duration)
        nxt = min(nxt_tick, pending[0]["clock"]["start_sec"]) if pending else nxt_tick
        if nxt > clock:
            await sleep((nxt - clock) / speed)
            clock = nxt
        while pending and pending[0]["clock"]["start_sec"] <= clock:
            yield sse("insight", pending.pop(0))
        if clock == nxt_tick:
            yield sse("tick", {"clock_sec": clock})
        if clock >= duration and not pending:
            break
    yield sse("end", {"clock_sec": duration})


def create_app(data_dir: str | Path | None = None, web_dist: str | Path | None = None,
               max_speed: float | None = None, sleep=asyncio.sleep) -> FastAPI:
    load_env()
    data_dir = Path(data_dir or os.environ.get("OPTIX_DATA_DIR") or ROOT / "web" / "public" / "data")
    web_dist = Path(web_dist or os.environ.get("OPTIX_WEB_DIST") or ROOT / "web" / "dist")
    max_speed = float(max_speed or os.environ.get("OPTIX_MAX_SPEED") or 600)
    store = MatchStore(data_dir)
    stores = {store.match_id: store}

    app = FastAPI(title="Optix", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "service": "optix", "matches": len(stores)}

    @app.get("/api/matches")
    def matches():
        return [s.summary() for s in stores.values()]

    @app.get("/api/match/{match_id}/stream")
    def stream(match_id: str, speed: float = Query(60.0, gt=0), start: int = Query(0, ge=0)):
        s = stores.get(match_id)
        if s is None:
            raise HTTPException(404, f"unknown match {match_id}")
        if speed > max_speed:
            raise HTTPException(422, f"speed must be at most {max_speed:g}")
        return StreamingResponse(replay(s, speed, start, sleep), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/claims/{claim_id}")
    def claim(claim_id: str):
        for s in stores.values():
            chain = s.chain(claim_id)
            if chain:
                return {"claim_id": claim_id, "match_id": s.match_id, "attempts": chain}
        raise HTTPException(404, f"unknown claim {claim_id}")

    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


def __getattr__(name):          # `uvicorn service.app:app` builds the app on first access
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
