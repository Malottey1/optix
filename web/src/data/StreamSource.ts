// Where the dashboard's data comes from. ReplaySource loads the files the engine wrote for the
// showcase match and the page replays them on its own clock. SseSource is used when the page is
// served by the Optix API: it loads the same files, then the server pushes the verified insights
// over server-sent events (data/SseSource.ts, pickSource).
import type { Insight, MatchBundle } from "../types/ui";

export interface StreamSource {
  readonly kind: "replay" | "sse";
  /** True when the source is connected to something real. */
  readonly wired: boolean;
  /** Everything the pages need for one match. */
  load(signal?: AbortSignal): Promise<MatchBundle>;
  /** Live sources push verified insights as they are published. Returns an unsubscribe function. */
  subscribe?(onInsight: (insight: Insight) => void, onError?: (error: Error) => void): () => void;
}
