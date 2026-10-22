import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { buildModel } from "./model";
import { ReplaySource } from "./ReplaySource";
import { SseSource, type EventSourceLike } from "./SseSource";

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

describe("SseSource (not wired yet)", () => {
  it("says it is not wired and refuses to load", async () => {
    const s = new SseSource("/stream");
    expect(s.wired).toBe(false);
    await expect(s.load()).rejects.toThrow(/not wired yet/);
  });

  it("parses pushed insights through the contract guard and closes on unsubscribe", () => {
    const listeners: ((e: MessageEvent<string>) => void)[] = [];
    const es: EventSourceLike = { addEventListener: (_t, l) => listeners.push(l), onerror: null, close: vi.fn() };
    const open = vi.fn(() => es);
    const got: string[] = [];
    const errors: Error[] = [];
    const stop = new SseSource("/stream", open).subscribe(
      (i) => got.push(i.insight_id),
      (e) => errors.push(e),
    );
    const line = readFileSync(join(DATA, "insights.jsonl"), "utf8").split("\n")[0]!;
    listeners[0]!(new MessageEvent("insight", { data: line }));
    listeners[0]!(new MessageEvent("insight", { data: "{}" }));
    expect(open).toHaveBeenCalledWith("/stream");
    expect(got).toHaveLength(1);
    expect(errors[0]?.message).toMatch(/insight_id/);
    stop();
    expect(es.close).toHaveBeenCalled();
  });
});
