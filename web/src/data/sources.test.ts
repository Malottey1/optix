import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { buildModel } from "./model";
import { ReplaySource } from "./ReplaySource";
import { SseSource, pickSource, type EventSourceLike } from "./SseSource";

const DATA = join(__dirname, "..", "..", "public", "data");
const fakeFetch = (overrides: Record<string, string> = {}) =>
  vi.fn(async (url: string) => {
    const name = url.split("/").pop()!;
    const body = overrides[name] ?? readFileSync(join(DATA, name), "utf8");
    return new Response(body, { status: 200 });
  });

describe("ReplaySource", () => {
  it("loads the committed engine output through the shape guards", async () => {
    const f = fakeFetch();
    const b = await new ReplaySource("./data/", f).load();
    expect(f).toHaveBeenCalledTimes(4);
    expect(f.mock.calls.every(([u]) => String(u).startsWith("./data/"))).toBe(true);
    expect(b.insights.length).toBeGreaterThan(0);
    const starts = b.insights.map((i) => i.clock.start_sec);
    expect([...starts].sort((a, c) => a - c)).toEqual(starts);
    const m = buildModel(b);
    const rewritten = Object.keys(b.ui.rewrites)[0]!;
    expect(m.chain(m.byId[rewritten]!.claim_id).length).toBeGreaterThan(1);
    expect(m.visibleCount(-1)).toBe(0);
    expect(m.visibleCount(1e9)).toBe(b.insights.length);
  });

  it("fails with a readable message when a file drifts", async () => {
    const f = fakeFetch({ "timeline.json": JSON.stringify({ match_id: "m" }) });
    await expect(new ReplaySource("./data/", f).load()).rejects.toThrow(/timeline\.json: timeline\.duration_sec/);
  });

  it("reports an HTTP error by file name", async () => {
    const f = vi.fn(async () => new Response("", { status: 404 }));
    await expect(new ReplaySource("./data/", f).load()).rejects.toThrow(/HTTP 404/);
  });
});

function fakeEs() {
  const listeners: Record<string, ((e: MessageEvent<string>) => void)[]> = {};
  const es: EventSourceLike & { emit(type: string, data: string): void } = {
    addEventListener: (t, l) => (listeners[t] ??= []).push(l),
    onerror: null,
    close: vi.fn(),
    emit: (t, data) => listeners[t]?.forEach((l) => l(new MessageEvent(t, { data }))),
  };
  return es;
}

describe("SseSource (live, same origin)", () => {
  it("loads the bundle from the replay files and builds the same-origin stream URL", async () => {
    const s = new SseSource("./api", 30, new ReplaySource("./data/", fakeFetch()));
    expect(s.wired).toBe(true);
    const b = await s.load();
    expect(s.url).toBe(`./api/match/${b.timeline.match_id}/stream?speed=30`);
  });

  it("parses pushed insights through the contract guard, follows ticks and closes", async () => {
    const es = fakeEs();
    const open = vi.fn(() => es);
    const s = new SseSource("./api", 30, new ReplaySource("./data/", fakeFetch()), open);
    await s.load();
    const got: string[] = [];
    const clocks: number[] = [];
    const errors: Error[] = [];
    let ended = false;
    const stop = s.listen({
      onInsight: (i) => got.push(i.insight_id),
      onClock: (c) => clocks.push(c),
      onEnd: () => (ended = true),
      onError: (e) => errors.push(e),
    });
    const line = readFileSync(join(DATA, "insights.jsonl"), "utf8").split("\n")[0]!;
    es.emit("insight", line);
    es.emit("insight", "{}");
    es.emit("tick", JSON.stringify({ clock_sec: 60 }));
    expect(open).toHaveBeenCalledWith(s.url);
    expect(got).toHaveLength(1);
    expect(clocks).toEqual([JSON.parse(line).clock.start_sec, 60]);
    expect(errors[0]?.message).toMatch(/insight_id/);
    es.emit("end", "{}");
    expect(ended).toBe(true);
    expect(es.close).toHaveBeenCalled();
    stop();
  });

  it("reports a dropped connection so the app can fall back", async () => {
    const es = fakeEs();
    const s = new SseSource("./api", 30, new ReplaySource("./data/", fakeFetch()), () => es);
    await s.load();
    const errors: Error[] = [];
    s.listen({ onInsight: () => {}, onError: (e) => errors.push(e) });
    es.onerror?.(new Event("error"));
    expect(errors[0]?.message).toMatch(/stream error/);
    expect(es.close).toHaveBeenCalled();
  });
});

describe("pickSource", () => {
  it("picks the live source only when the same-origin healthz answers as the Optix service", async () => {
    const ok = vi.fn(async () => new Response(JSON.stringify({ status: "ok", service: "optix" })));
    expect((await pickSource(ok)).kind).toBe("sse");
    expect(ok).toHaveBeenCalledWith("./healthz", expect.anything());
    const html = vi.fn(async () => new Response("<!doctype html>", { status: 200 }));
    expect((await pickSource(html)).kind).toBe("replay");
    const missing = vi.fn(async () => new Response("", { status: 404 }));
    expect((await pickSource(missing)).kind).toBe("replay");
    const down = vi.fn(async () => {
      throw new TypeError("network");
    });
    expect((await pickSource(down)).kind).toBe("replay");
  });
});
