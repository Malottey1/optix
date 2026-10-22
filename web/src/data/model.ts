// Lookups the pages need, built once from a loaded bundle. Nothing here computes a statistic:
// it indexes, orders and searches what the engine wrote.
import type { ClaimAttempt, EvidenceRow, Insight, MatchBundle, TrackEntry } from "../types/ui";

export interface MatchModel extends MatchBundle {
  byId: Record<string, Insight>;
  /** The attempts behind an insight's claim, first attempt first. */
  chain(claimId: string): ClaimAttempt[];
  /** How many insights have appeared at clock t (insights are sorted by start time). */
  visibleCount(t: number): number;
  /** The latest on-ball event at or before t (the ball marker), and the few before it. */
  trackIndex(t: number): number;
  track: TrackEntry[];
  /** Evidence rows of an insight, in the stream's order; ids without a row are dropped. */
  evidenceOf(ids: readonly string[]): EvidenceRow[];
  sideOf(code: string): "home" | "away";
  /** Index in `insights` of the latest insight at or before t that satisfies `pred`. */
  latest(t: number, pred: (i: Insight) => boolean): Insight | null;
}

/** Largest index i with key(arr[i]) <= t, or -1. */
export function lastAtOrBefore<T>(arr: readonly T[], t: number, key: (x: T) => number): number {
  let lo = 0;
  let hi = arr.length - 1;
  let best = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (key(arr[mid]!) <= t) {
      best = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return best;
}

export function buildModel(b: MatchBundle): MatchModel {
  const byId = Object.fromEntries(b.insights.map((i) => [i.insight_id, i]));
  const chains = new Map<string, ClaimAttempt[]>();
  const chain = (claimId: string) => {
    let c = chains.get(claimId);
    if (!c) {
      c = [];
      let a: ClaimAttempt | undefined = b.attempts[claimId];
      while (a) {
        c.unshift(a);
        a = a.revision_of ? b.attempts[a.revision_of] : undefined;
      }
      chains.set(claimId, c);
    }
    return c;
  };
  const track = b.ui.track;
  return {
    ...b,
    byId,
    chain,
    track,
    visibleCount: (t) => lastAtOrBefore(b.insights, t, (i) => i.clock.start_sec) + 1,
    trackIndex: (t) => lastAtOrBefore(track, t, (e) => e[0]),
    evidenceOf: (ids) => ids.map((id) => b.ui.evidence[id]).filter((e): e is EvidenceRow => Boolean(e)),
    sideOf: (code) => (code === b.timeline.home.code ? "home" : "away"),
    latest(t, pred) {
      for (let i = lastAtOrBefore(b.insights, t, (x) => x.clock.start_sec); i >= 0; i--) {
        if (pred(b.insights[i]!)) return b.insights[i]!;
      }
      return null;
    },
  };
}
