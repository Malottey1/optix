// Replay of the pre-generated showcase match: public/data/ holds byte-for-byte copies of the
// engine's out/ files (npm run data). Every file passes a runtime shape guard on load.
import { checkBundle, parseAttempt, parseInsight, parseJsonl, parseTimeline, parseUi } from "../types/guards";
import type { ClaimAttempt, MatchBundle } from "../types/ui";
import type { StreamSource } from "./StreamSource";

export const DATA_FILES = {
  ui: "ui.json",
  insights: "insights.jsonl",
  claims: "claims.jsonl",
  timeline: "timeline.json",
} as const;

type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

export class ReplaySource implements StreamSource {
  readonly kind = "replay" as const;
  readonly wired = true;

  constructor(
    private readonly base = "./data/",
    private readonly fetchImpl: Fetch = (i, init) => fetch(i, init),
  ) {}

  private async text(name: string, signal?: AbortSignal): Promise<string> {
    const r = await this.fetchImpl(this.base + name, { signal, cache: "no-cache" });
    if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
    return r.text();
  }

  async load(signal?: AbortSignal): Promise<MatchBundle> {
    const [ins, cl, tl, ui] = await Promise.all([
      this.text(DATA_FILES.insights, signal),
      this.text(DATA_FILES.claims, signal),
      this.text(DATA_FILES.timeline, signal),
      this.text(DATA_FILES.ui, signal),
    ]);
    const insights = parseJsonl(ins, DATA_FILES.insights, parseInsight).sort(
      (a, b) => a.clock.start_sec - b.clock.start_sec,
    );
    const attempts: Record<string, ClaimAttempt> = {};
    for (const a of parseJsonl(cl, DATA_FILES.claims, parseAttempt)) attempts[a.claim.claim_id] = a;
    return checkBundle({ insights, attempts, timeline: parseTimeline(JSON.parse(tl)), ui: parseUi(JSON.parse(ui)) });
  }
}
