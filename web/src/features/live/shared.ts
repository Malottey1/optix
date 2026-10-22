// Small read-only helpers over the stream (no statistic is computed here).
import type { Status } from "../../components/ui/badge";
import type { MatchModel } from "../../data/model";
import type { Insight, Lang, Rendered, Tone } from "../../types/ui";

export const textOf = (rendered: Rendered, lang: Lang, tone: Tone): string =>
  rendered[lang]?.[tone] ?? rendered.en?.[tone] ?? "";

/** Rewritten (blocked on a first attempt, then published) wins over the published status. */
export function statusOf(m: MatchModel, ins: Insight): Status {
  if (m.ui.rewrites[ins.insight_id]) return "revised";
  return ins.verification_status === "published_with_context" ? "published_with_context" : "published";
}

export function reasonFor(m: MatchModel, ruleIds: readonly string[], lang: Lang): string | null {
  const r = m.ui.reasons[lang] ?? m.ui.reasons.en ?? {};
  for (const id of ruleIds) if (r[id]) return r[id]!;
  return null;
}

/** Engine metrics whose values are percentages (the sentences print them with a % sign). */
export const PCT_METRICS = new Set([
  "field_tilt",
  "possession_pct",
  "box_entry_share",
  "wide_share",
  "set_piece_share",
]);

/** Evidence rows grouped by event type, largest group first: "pass 12 · shot 3". */
export function evidenceMix(m: MatchModel, ids: readonly string[]): [string, number][] {
  const counts = new Map<string, number>();
  for (const e of m.evidenceOf(ids)) counts.set(e.event_type, (counts.get(e.event_type) ?? 0) + 1);
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
