"""The API service: health, matches, claims, and the SSE replay (httpx streaming, fake clock)."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from service.app import TICK_SEC, MatchStore, create_app

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "public" / "data"


class FakeClock:
    """Records every sleep and returns at once; `now` is the replay's elapsed wall time."""

    def __init__(self):
        self.now, self.sleeps = 0.0, []

    async def __call__(self, sec):
        self.sleeps.append(sec)
        self.now += sec


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


def _run(coro):
    return asyncio.run(coro)


async def _events(app, url):
    out = []
    async with _client(app) as c:
        async with c.stream("GET", url) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            event = None
            async for line in r.aiter_lines():
                if line.startswith("event: "):
                    event = line[7:]
                elif line.startswith("data: "):
                    out.append((event, json.loads(line[6:])))
    return out


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def app(clock, tmp_path):
    return create_app(DATA, tmp_path / "no-dist", sleep=clock)


def test_health_and_matches(app):
    async def go():
        async with _client(app) as c:
            h = (await c.get("/healthz")).json()
            m = (await c.get("/api/matches")).json()
        return h, m
    h, m = _run(go())
    assert h == {"status": "ok", "service": "optix", "matches": 1}
    store = MatchStore(DATA)
    assert m == [store.summary()] and m[0]["insights"] == len(store.insights) > 0


def test_stream_replays_every_insight_in_order_at_its_clock(app, clock):
    store = MatchStore(DATA)
    speed = 60
    ev = _run(_events(app, f"/api/match/{store.match_id}/stream?speed={speed}"))
    assert ev[0][0] == "hello" and ev[-1][0] == "end"
    ins = [d for e, d in ev if e == "insight"]
    assert ins == store.insights                       # unchanged objects, every one, in order
    total = sum(clock.sleeps)
    assert total == pytest.approx(store.timeline["duration_sec"] / speed)
    ticks = [d["clock_sec"] for e, d in ev if e == "tick"]
    assert ticks == sorted(ticks) and all(t % TICK_SEC == 0 or t == store.timeline["duration_sec"] for t in ticks)


def test_insight_arrives_when_its_clock_is_reached(clock):
    """The replay generator on the fake clock: each insight frame is sent when the elapsed time is
    its match clock / speed. (httpx's ASGI transport buffers the body, so timing is read here.)"""
    from service.app import replay
    store = MatchStore(DATA)

    async def go():
        stamps = []
        async for frame in replay(store, 10, sleep=clock):
            if frame.startswith("event: insight"):
                stamps.append((json.loads(frame.split("data: ", 1)[1])["clock"]["start_sec"], clock.now))
        return stamps
    stamps = _run(go())
    assert len(stamps) == len(store.insights)
    assert all(now == pytest.approx(start / 10) for start, now in stamps)


def test_stream_start_and_speed_limits(app):
    store = MatchStore(DATA)
    mid = store.match_id
    late = store.insights[len(store.insights) // 2]["clock"]["start_sec"]
    ev = _run(_events(app, f"/api/match/{mid}/stream?speed=600&start={late}"))
    assert all(d["clock"]["start_sec"] >= late for e, d in ev if e == "insight")

    async def go():
        async with _client(app) as c:
            return ((await c.get(f"/api/match/{mid}/stream?speed=601")).status_code,
                    (await c.get(f"/api/match/{mid}/stream?speed=0")).status_code,
                    (await c.get("/api/match/m_nope/stream")).status_code)
    assert _run(go()) == (422, 422, 404)


def test_claims_endpoint_returns_the_attempt_chain(app):
    store = MatchStore(DATA)
    rewritten = next(i["claim_id"] for i in store.insights if len(store.chain(i["claim_id"])) > 1)

    async def go():
        async with _client(app) as c:
            return (await c.get(f"/api/claims/{rewritten}")).json(), (await c.get("/api/claims/nope")).status_code
    body, missing = _run(go())
    assert missing == 404
    assert body["attempts"][-1]["claim"]["claim_id"] == rewritten
    assert body["attempts"][0]["claim"]["verification"]["status"] == "blocked"


def test_pattern_cards_stream_and_their_claims_carry_evidence_and_the_verification_record(app):
    """The tactical pattern cards arrive over SSE unchanged; /api/claims returns, for a pattern claim
    and for a naive claim a pattern rule rewrote, the evidence ids and every verification attempt."""
    from engine.rules import PATTERN_RULES
    store = MatchStore(DATA)
    ev = _run(_events(app, f"/api/match/{store.match_id}/stream?speed=600"))
    cards = [d for e, d in ev if e == "insight" and d["insight_type"] == "tactical_pattern"]
    assert cards == [i for i in store.insights if i["insight_type"] == "tactical_pattern"] and cards
    own = next(c for c in cards if c["payload"]["claim_metric"].startswith("pat_"))
    rewritten = next(c for c in cards if not c["payload"]["claim_metric"].startswith("pat_"))

    async def go(cid):
        async with _client(app) as c:
            return (await c.get(f"/api/claims/{cid}")).json()
    for card in (own, rewritten):
        body = _run(go(card["claim_id"]))
        last = body["attempts"][-1]
        assert last["claim"]["evidence_event_ids"] == card["evidence_event_ids"]
        assert last["claim"]["verification"]["status"] in ("published", "published_with_context")
    first = _run(go(rewritten["claim_id"]))["attempts"][0]["claim"]["verification"]
    assert first["status"] == "blocked" and set(first["rule_ids"]) & set(PATTERN_RULES)


def test_no_cors_headers_and_no_api_docs(app):
    async def go():
        async with _client(app) as c:
            r = await c.get("/healthz", headers={"Origin": "https://elsewhere.example"})
            return r.headers, (await c.get("/docs")).status_code, (await c.get("/openapi.json")).status_code
    headers, docs, spec = _run(go())
    assert "access-control-allow-origin" not in {k.lower() for k in headers}
    assert docs == spec == 404


def test_serves_the_built_dashboard_when_present(tmp_path, clock):
    (tmp_path / "index.html").write_text("<!doctype html><title>Optix</title>")
    app = create_app(DATA, tmp_path, sleep=clock)

    async def go():
        async with _client(app) as c:
            return (await c.get("/")).text, (await c.get("/healthz")).status_code
    html, ok = _run(go())
    assert "Optix" in html and ok == 200


def _numbers(o):
    """Every number in a JSON value, in order (the personalized frames must carry the same ones)."""
    if isinstance(o, bool):
        return []
    if isinstance(o, (int, float)):
        return [o]
    if isinstance(o, dict):
        return [n for k in sorted(o) for n in _numbers(o[k])]
    if isinstance(o, list):
        return [n for v in o for n in _numbers(v)]
    return []


def test_personalized_stream_caps_fan_filters_a_player_and_keeps_every_number(app):
    store = MatchStore(DATA)
    by_id = {i["insight_id"]: i for i in store.insights}
    url = f"/api/match/{store.match_id}/stream?speed=600"
    fan = [d for e, d in _run(_events(app, url + "&mode=fan&lang=es")) if e == "insight"]
    assert 0 < len(fan) <= 5
    starts = [d["clock"]["start_sec"] for d in fan]
    assert starts == sorted(starts)                    # replayed in clock order
    for d in fan:                                      # the very same objects: same numbers, same text
        assert d == by_id[d["insight_id"]] and _numbers(d) == _numbers(by_id[d["insight_id"]])
    assert store.involved, "events-m_showcase.json missing from the data directory"
    mine = [d for e, d in _run(_events(app, url + "&player=NTG_10")) if e == "insight"]
    assert mine and all(d == by_id[d["insight_id"]] for d in mine)
    assert all("NTG_10" in d["player_ids"] or any("NTG_10" in store.involved.get(x, ()) for x in d["evidence_event_ids"])
               for d in mine)
    assert len(mine) < len(store.insights)


def test_unknown_personalization_values_are_ignored(app):
    store = MatchStore(DATA)
    url = f"/api/match/{store.match_id}/stream?speed=600&mode=boss&lang=xx&club=ZZZ&player=nobody&metric=pace"
    ins = [d for e, d in _run(_events(app, url)) if e == "insight"]
    assert ins == store.insights

    async def health():
        async with _client(app) as c:
            return (await c.get("/healthz")).json()
    assert _run(health())["status"] == "ok"
