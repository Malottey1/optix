// SVG pitch drawn in metres (105 x 68). Data coordinates are 0-100 in the acting team's attacking
// frame (engine/zones.py): x 0 = own goal -> 100 = opponent goal, y 0 = the attacker's left
// touchline. Every team attacks left to right here, so the attacker's left flank is the top edge.
import { memo } from "react";
import type { Insight } from "../../types/ui";

export const PX = 105 / 100;
export const PY = 68 / 100;
export const LANE_EDGES = [0, 20, 40, 60, 80, 100] as const; // engine/zones.py
export const FINAL_THIRD_X = 66.7;
export const BOX = { x: 84, y0: 22, y1: 78 } as const;
export const LANE_NAMES: Record<string, string> = {
  left_flank: "Left flank",
  left_half_space: "Left half-space",
  center: "Centre",
  right_half_space: "Right half-space",
  right_flank: "Right flank",
};
/** The same strip of grass named from the other side's own point of view (left and right swap). */
export const MIRROR: Record<string, string> = {
  left_flank: "right_flank",
  left_half_space: "right_half_space",
  center: "center",
  right_half_space: "left_half_space",
  right_flank: "left_flank",
};

export type Side = "home" | "away";
export const sideColor = (side: Side) => (side === "home" ? "var(--home)" : "var(--away)");

export const PitchLines = memo(function PitchLines({
  thirds = true,
  stripes = true,
}: {
  thirds?: boolean;
  stripes?: boolean;
}) {
  const L = { fill: "none", stroke: "var(--pitch-line)", strokeWidth: 0.35 };
  return (
    <g aria-hidden="true">
      <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
      {stripes &&
        Array.from({ length: 6 }, (_, i) => (
          <rect key={i} x={i * 17.5} y="0" width="8.75" height="68" fill="var(--pitch-stripe)" />
        ))}
      <rect x="0" y="0" width="105" height="68" {...L} />
      <line x1="52.5" y1="0" x2="52.5" y2="68" {...L} />
      <circle cx="52.5" cy="34" r="9.15" {...L} />
      <circle cx="52.5" cy="34" r="0.45" fill="var(--pitch-line)" />
      {[true, false].map((left) => (
        <g key={String(left)}>
          <rect x={left ? 0 : 105 - 16.5} y={BOX.y0 * PY} width="16.5" height={(BOX.y1 - BOX.y0) * PY} {...L} />
          <rect x={left ? 0 : 105 - 5.5} y="24.85" width="5.5" height="18.3" {...L} />
          <circle cx={left ? 11 : 94} cy="34" r="0.4" fill="var(--pitch-line)" />
          <path d={left ? "M16.5,26.7 A9.15,9.15 0 0 1 16.5,41.3" : "M88.5,26.7 A9.15,9.15 0 0 0 88.5,41.3"} {...L} />
          <rect x={left ? -1.8 : 105} y="30.34" width="1.8" height="7.32" {...L} />
        </g>
      ))}
      {thirds && (
        <line
          x1={FINAL_THIRD_X * PX}
          y1="0"
          x2={FINAL_THIRD_X * PX}
          y2="68"
          stroke="var(--pitch-faint)"
          strokeWidth="0.3"
          strokeDasharray="1.2 1.2"
        />
      )}
    </g>
  );
});

export function Arrowheads({ id }: { id: string }) {
  const colors: [string, string][] = [
    ["home", "var(--home)"],
    ["away", "var(--away)"],
    ["muted", "var(--ink-3)"],
    ["accent", "var(--accent)"],
  ];
  return (
    <defs>
      {colors.map(([k, c]) => (
        <marker
          key={k}
          id={`${id}-arrow-${k}`}
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="4"
          markerHeight="4"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" fill={c} />
        </marker>
      ))}
      <radialGradient id={`${id}-glow`}>
        <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.55" />
        <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
      </radialGradient>
    </defs>
  );
}

/** Which evidence points a type draws strongly; the rest are context, drawn muted. */
function strongPoint(type: Insight["insight_type"], kind: string | undefined): boolean {
  if (type === "perimeter_lock") return kind === "box_entry";
  return true;
}

/**
 * The evidence of one insight: lane band (matchups), focus box, and every point with its event id.
 * `highlight` emphasises one event (hovered in the evidence table).
 */
export const InsightLayer = memo(function InsightLayer({
  insight,
  side,
  markerId,
  highlight = null,
}: {
  insight: Insight | null;
  side: Side;
  markerId: string;
  highlight?: string | null;
}) {
  if (!insight) return null;
  const p = insight.payload;
  const color = sideColor(side);
  const f = p.focus;
  const lane = typeof p.metrics?.lane === "string" ? p.metrics.lane : undefined;
  const type = insight.insight_type;
  return (
    <g
      data-layer="insight"
      data-insight-id={insight.insight_id}
      data-claim-id={insight.claim_id}
      data-team={insight.teams.primary}
    >
      {f && type === "matchup_mismatch" && f.y_min != null && f.y_max != null && (
        <rect
          data-lane={lane}
          x="0"
          y={f.y_min * PY}
          width="105"
          height={(f.y_max - f.y_min) * PY}
          fill={color}
          opacity="0.12"
        />
      )}
      {type === "perimeter_lock" && (
        <rect
          x={BOX.x * PX}
          y={BOX.y0 * PY}
          width={(100 - BOX.x) * PX}
          height={(BOX.y1 - BOX.y0) * PY}
          fill={color}
          opacity="0.12"
          stroke={color}
          strokeWidth="0.4"
        />
      )}
      {f && f.x_min != null && f.x_max != null && f.y_min != null && f.y_max != null && type !== "matchup_mismatch" && (
        <rect
          x={f.x_min * PX}
          y={f.y_min * PY}
          width={(f.x_max - f.x_min) * PX}
          height={(f.y_max - f.y_min) * PY}
          fill="none"
          stroke="var(--ink-3)"
          strokeWidth="0.3"
          strokeDasharray="1 0.8"
          rx="0.8"
        />
      )}
      {(p.points ?? []).map((pt, i) => {
        const strong = strongPoint(type, pt.kind);
        const hi = highlight === pt.event_id;
        const stroke = hi ? "var(--accent)" : strong ? color : "var(--ink-3)";
        const line = pt.x_end != null && pt.y_end != null && pt.kind !== "shot";
        const shot = pt.kind === "shot";
        const threat = type === "threat_pass";
        return (
          <g
            key={`${pt.event_id}-${i}`}
            data-event-id={pt.event_id}
            data-kind={pt.kind}
            data-team={insight.teams.primary}
          >
            {threat && (
              <circle cx={(pt.x_end ?? pt.x) * PX} cy={(pt.y_end ?? pt.y) * PY} r="5" fill={`url(#${markerId}-glow)`} />
            )}
            {line && (
              <line
                x1={pt.x * PX}
                y1={pt.y * PY}
                x2={pt.x_end! * PX}
                y2={pt.y_end! * PY}
                stroke={stroke}
                strokeWidth={hi ? 0.8 : threat ? 0.7 : strong ? 0.45 : 0.3}
                opacity={strong || hi ? 0.95 : 0.5}
                strokeLinecap="round"
                markerEnd={`url(#${markerId}-arrow-${hi ? "accent" : strong ? side : "muted"})`}
              />
            )}
            <circle
              cx={pt.x * PX}
              cy={pt.y * PY}
              r={hi ? 1.4 : shot ? 1.1 : strong ? 0.8 : 0.5}
              fill={shot ? "none" : stroke}
              stroke={shot ? stroke : "none"}
              strokeWidth={shot ? 0.45 : 0}
            />
          </g>
        );
      })}
    </g>
  );
});
