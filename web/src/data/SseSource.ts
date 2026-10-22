// NOT WIRED YET. The live interface for the Azure step: a server pushes each verified insight as a
// server-sent event (`event: insight`, data = one contracts/insight.schema.json object). Nothing
// in the app constructs this source today; it exists so the contract is typed and tested.
import { parseInsight } from "../types/guards";
import type { Insight, MatchBundle } from "../types/ui";
import type { StreamSource } from "./StreamSource";

/** The subset of EventSource this source uses (injectable for tests). */
export interface EventSourceLike {
  addEventListener(type: string, listener: (e: MessageEvent<string>) => void): void;
  onerror: ((e: Event) => void) | null;
  close(): void;
}

export class SseSource implements StreamSource {
  readonly kind = "sse" as const;
  readonly wired = false;

  constructor(
    private readonly url: string,
    private readonly open: (url: string) => EventSourceLike = (u) => new EventSource(u) as unknown as EventSourceLike,
  ) {}

  load(): Promise<MatchBundle> {
    return Promise.reject(new Error("SseSource is not wired yet: the live server is part of the planned Azure step."));
  }

  subscribe(onInsight: (insight: Insight) => void, onError?: (error: Error) => void): () => void {
    const es = this.open(this.url);
    es.addEventListener("insight", (e) => {
      try {
        onInsight(parseInsight(JSON.parse(e.data)));
      } catch (err) {
        onError?.(err as Error);
      }
    });
    es.onerror = () => onError?.(new Error(`stream error: ${this.url}`));
    return () => es.close();
  }
}
