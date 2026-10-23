// Live source: used when the page is served by the Optix API (service/app.py). The match bundle
// (board, deck, evidence) loads from the same files as the replay; the verified insights are then
// pushed by the server as server-sent events at match pace (`event: insight`, data = one
// contracts/insight.schema.json object; `event: tick` carries the match clock). Same origin only.
import { parseInsight } from "../types/guards";
import type { Insight, MatchBundle } from "../types/ui";
import { ReplaySource } from "./ReplaySource";
import type { StreamSource } from "./StreamSource";

/** The subset of EventSource this source uses (injectable for tests). */
export interface EventSourceLike {
  addEventListener(type: string, listener: (e: MessageEvent<string>) => void): void;
  onerror: ((e: Event) => void) | null;
  close(): void;
}

export interface SseHandlers {
  onInsight: (insight: Insight) => void;
  onClock?: (clockSec: number) => void;
  onEnd?: () => void;
  onError?: (error: Error) => void;
}

export class SseSource implements StreamSource {
  readonly kind = "sse" as const;
  readonly wired = true;
  private matchId = "";

  constructor(
    private readonly api = "./api",
    private readonly speed = 30,
    private readonly bundle: StreamSource = new ReplaySource(),
    private readonly open: (url: string) => EventSourceLike = (u) => new EventSource(u) as unknown as EventSourceLike,
  ) {}

  async load(signal?: AbortSignal): Promise<MatchBundle> {
    const b = await this.bundle.load(signal);
    this.matchId = b.timeline.match_id;
    return b;
  }

  /** The stream URL (same origin), known once the bundle has loaded. */
  get url(): string {
    return `${this.api}/match/${encodeURIComponent(this.matchId)}/stream?speed=${this.speed}`;
  }

  subscribe(onInsight: (insight: Insight) => void, onError?: (error: Error) => void): () => void {
    return this.listen({ onInsight, onError });
  }

  /** Insights, clock ticks and the end of the match; a malformed frame or a dropped connection
   *  goes to onError (the app then falls back to the replay). Returns an unsubscribe function. */
  listen(h: SseHandlers): () => void {
    const es = this.open(this.url);
    const fail = (err: Error) => h.onError?.(err);
    es.addEventListener("insight", (e) => {
      try {
        const ins = parseInsight(JSON.parse(e.data));
        h.onInsight(ins);
        h.onClock?.(ins.clock.start_sec);
      } catch (err) {
        fail(err as Error);
      }
    });
    es.addEventListener("tick", (e) => {
      try {
        const c = (JSON.parse(e.data) as { clock_sec: unknown }).clock_sec;
        if (typeof c === "number") h.onClock?.(c);
      } catch (err) {
        fail(err as Error);
      }
    });
    es.addEventListener("end", () => {
      h.onEnd?.();
      es.close();
    });
    es.onerror = () => {
      es.close();
      fail(new Error(`stream error: ${this.url}`));
    };
    return () => es.close();
  }
}

type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

/** The live source when this page is served by the Optix API (same-origin `healthz` answers as
 *  the Optix service), else the replay. Never contacts another host. */
export async function pickSource(fetchImpl: Fetch = (i, init) => fetch(i, init)): Promise<StreamSource> {
  try {
    const r = await fetchImpl("./healthz", { cache: "no-store", signal: AbortSignal.timeout(1500) });
    const body = r.ok ? ((await r.json()) as { service?: unknown }) : null;
    if (body?.service === "optix") {
      return new SseSource();
    }
  } catch {
    // no API here (static hosting): replay
  }
  return new ReplaySource();
}
