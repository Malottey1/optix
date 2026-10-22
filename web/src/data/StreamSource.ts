// Where the dashboard's data comes from. Today only ReplaySource is wired: it loads the files the
// engine wrote for the showcase match and the page replays them on its own clock. SseSource
// defines the live interface (insights pushed one at a time) and is not wired yet; the Azure step
// will connect it to a server.
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
