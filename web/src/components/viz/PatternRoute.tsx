// The visual of a tactical pattern card (engine/patterns), drawn only from the claim's evidence
// events (the insight's payload points, in the attacking team's frame). Two forms:
//  - "arrows": a pitch with each pass of the evidence as an arrow and each shot as a dot, for the
//    families about where the ball went (build and switch, cut-backs, touchline spells);
//  - "route": the evidence events as a chain of nodes with their event icons and match clock, for
//    families about sequences in time (regains, counters, fouls after losses, a forward's shots) and
//    for any family the page does not know (the generic fallback).
// Nothing is computed beyond counting the events drawn.
import { memo } from "react";
import { Icon, eventIcon } from "../../icons";
import { clock } from "../../lib/format";
import type { EvidenceRow, Period } from "../../types/ui";
import { VizFigure } from "./Figure";

export interface RoutePoint {
  event_id: string;
  x: number;
  y: number;
  x_end?: number | null;
  y_end?: number | null;
  kind?: string;
}

export const ARROW_FAMILIES = new Set(["pat_bait_switch", "pat_cutback", "pat_flank_isolation"]);
export const ROUTE_MAX_NODES = 8;

const PX = 1.05;
const PY = 0.68;

/** The kinds of event the visual draws, with how many of each (for tests and the text alternative). */
export function kindCounts(points: readonly RoutePoint[]): [string, number][] {
  const c = new Map<string, number>();
  for (const p of points) c.set(p.kind ?? "event", (c.get(p.kind ?? "event") ?? 0) + 1);
  return [...c.entries()];
}

const words = (s: string) => s.replace(/_/g, " ");

function Arrows({ points, color, label }: { points: readonly RoutePoint[]; color: string; label: string }) {
  return (
    <svg viewBox="-1 -1 107 70" role="img" aria-label={label} className="block h-auto w-full">
      <rect x="0" y="0" width="105" height="68" rx="1.5" fill="var(--pitch, var(--surface-3))" stroke="var(--line)" strokeWidth="0.4" />
      <line x1="52.5" y1="0" x2="52.5" y2="68" stroke="var(--line)" strokeWidth="0.3" />
      <rect x="88.5" y="13.8" width="16.5" height="40.4" fill="none" stroke="var(--line)" strokeWidth="0.3" />
      <defs>
        <marker id="pr-head" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill={color} />
        </marker>
      </defs>
      {points.map((p) =>
        p.kind === "shot" || p.x_end == null || p.y_end == null ? (
          <circle key={p.event_id} data-event-id={p.event_id} cx={p.x * PX} cy={p.y * PY} r="1.6" fill={color} stroke="var(--bg)" strokeWidth="0.4" />
        ) : (
          <line
            key={p.event_id}
            data-event-id={p.event_id}
            x1={p.x * PX}
            y1={p.y * PY}
            x2={p.x_end * PX}
            y2={p.y_end * PY}
            stroke={color}
            strokeWidth="0.6"
            strokeOpacity="0.85"
            markerEnd="url(#pr-head)"
          />
        ),
      )}
    </svg>
  );
}

function Route({
  points,
  rows,
  periods,
  label,
}: {
  points: readonly RoutePoint[];
  rows: Record<string, EvidenceRow>;
  periods: readonly Period[];
  label: string;
}) {
  const shown = points.slice(0, ROUTE_MAX_NODES);
  return (
    <ol role="img" aria-label={label} className="flex flex-wrap items-center gap-1.5 text-[11.5px] text-ink-2">
      {shown.map((p, i) => {
        const r = rows[p.event_id];
        const icon = eventIcon(p.kind ?? r?.event_type ?? "", r?.outcome);
        return (
          <li key={p.event_id} data-event-id={p.event_id} className="inline-flex items-center gap-1">
            {i > 0 && <span aria-hidden="true" className="text-ink-4">→</span>}
            <span className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5">
              {icon && <Icon name={icon} size={12} />}
              {words(p.kind ?? r?.event_type ?? "event")}
              {r && <time className="num text-ink-3">{clock(r.clock_sec, periods)}</time>}
            </span>
          </li>
        );
      })}
      {points.length > shown.length && <li className="text-ink-3">and more (the evidence drawer lists all)</li>}
    </ol>
  );
}

export const PatternRoute = memo(function PatternRoute({
  family,
  points,
  rows,
  periods,
  color,
  claimId,
}: {
  family: string | null;
  points: readonly RoutePoint[];
  rows: Record<string, EvidenceRow>;
  periods: readonly Period[];
  color: string;
  claimId: string;
}) {
  if (!points.length) return null;
  const kinds = kindCounts(points).map(([k]) => words(k)).join(", ");
  const arrows = ARROW_FAMILIES.has(family ?? "");
  const label = `The claim's evidence events (${kinds})${arrows ? " drawn on the pitch" : " in match order"}`;
  return (
    <VizFigure
      viz={arrows ? "pattern-arrows" : "pattern-route"}
      caption={arrows ? "The claim's evidence: passes as arrows, shots as dots, attacking left to right." : "The claim's evidence events in match order."}
      table={{
        caption: `Evidence of claim ${claimId}`,
        head: ["event", "kind", "x", "y"],
        rows: points.map((p) => [p.event_id, p.kind ?? "", p.x, p.y]),
      }}
    >
      {arrows ? (
        <Arrows points={points} color={color} label={label} />
      ) : (
        <Route points={points} rows={rows} periods={periods} label={label} />
      )}
    </VizFigure>
  );
});
