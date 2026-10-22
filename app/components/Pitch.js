// SVG pitch drawn in metres (105 x 68). Data coordinates are 0-100 in the acting team's attacking
// frame (engine/zones.py): x 0 own goal -> 100 opponent goal, y 0 = the attacker's left touchline.
// Every team attacks left to right here, so the attacker's left flank is the top edge.
import { html, React } from "../lib/html.js";

export const PX = 105 / 100;
export const PY = 68 / 100;
export const LANE_EDGES = [0, 20, 40, 60, 80, 100];        // engine/zones.py LANE_EDGES
export const FINAL_THIRD_X = 66.7;
export const BOX = { x: 84, y0: 22, y1: 78 };

export const PitchLines = React.memo(function PitchLines({ thirds = true }) {
  const L = { fill: "none", stroke: "var(--pitch-line)", strokeWidth: 0.35 };
  return html`<g aria-hidden="true">
    <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
    <rect x="0" y="0" width="105" height="68" ...${L} />
    <line x1="52.5" y1="0" x2="52.5" y2="68" ...${L} />
    <circle cx="52.5" cy="34" r="9.15" ...${L} />
    <circle cx="52.5" cy="34" r="0.4" fill="var(--pitch-line)" />
    ${[true, false].map((left) => html`<g key=${String(left)}>
      <rect x=${left ? 0 : 105 - 16.5} y=${BOX.y0 * PY} width="16.5" height=${(BOX.y1 - BOX.y0) * PY} ...${L} />
      <rect x=${left ? 0 : 105 - 5.5} y="24.85" width="5.5" height="18.3" ...${L} />
      <circle cx=${left ? 11 : 94} cy="34" r="0.4" fill="var(--pitch-line)" />
      <rect x=${left ? -1.6 : 105} y="30.34" width="1.6" height="7.32" ...${L} />
    </g>`)}
    ${thirds && html`<line x1=${FINAL_THIRD_X * PX} y1="0" x2=${FINAL_THIRD_X * PX} y2="68" stroke="var(--pitch-third)"
        strokeWidth="0.3" strokeDasharray="1.2 1.2" />`}
  </g>`;
});

export function Arrowheads({ id = "pitch" }) {
  return html`<defs>
    ${[["home", "var(--home)"], ["away", "var(--away)"], ["muted", "var(--ink-3)"]].map(([k, c]) => html`
      <marker key=${k} id=${`${id}-arrow-${k}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4"
          orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill=${c} /></marker>`)}
  </defs>`;
}

/** The evidence of one insight: lane band (matchups), focus box, and every point with its event id. */
export const InsightLayer = React.memo(function InsightLayer({ insight, side, markerId = "pitch" }) {
  if (!insight) return null;
  const p = insight.payload || {};
  const color = side === "home" ? "var(--home)" : "var(--away)";
  const lock = insight.insight_type === "perimeter_lock";
  const f = p.focus;
  return html`<g data-layer="insight" data-insight-id=${insight.insight_id}>
    ${f && insight.insight_type === "matchup_mismatch" && html`<rect data-lane=${(p.metrics || {}).lane}
        x="0" y=${f.y_min * PY} width="105" height=${(f.y_max - f.y_min) * PY} fill=${color} opacity="0.1" />`}
    ${f && html`<rect x=${f.x_min * PX} y=${f.y_min * PY} width=${(f.x_max - f.x_min) * PX} height=${(f.y_max - f.y_min) * PY}
        fill="none" stroke="var(--ink-2)" strokeWidth="0.3" strokeDasharray="1 0.8" rx="0.6" />`}
    ${(p.points || []).map((pt, i) => {
      const strong = !(lock && pt.kind === "pass");
      const stroke = strong ? color : "var(--ink-3)";
      const line = pt.x_end != null && pt.y_end != null && pt.kind !== "shot";
      return html`<g key=${pt.event_id || i} data-event-id=${pt.event_id} data-kind=${pt.kind} data-team=${insight.teams.primary}>
        ${line && html`<line x1=${pt.x * PX} y1=${pt.y * PY} x2=${pt.x_end * PX} y2=${pt.y_end * PY} stroke=${stroke}
            strokeWidth=${strong ? 0.45 : 0.3} opacity=${strong ? 0.95 : 0.55} strokeLinecap="round"
            markerEnd=${`url(#${markerId}-arrow-${strong ? side : "muted"})`} />`}
        <circle cx=${pt.x * PX} cy=${pt.y * PY} r=${strong ? 0.85 : 0.55} fill=${stroke} />
      </g>`;
    })}
  </g>`;
});

/** Ball marker at the latest event location, flipped into the frame of the team on the pitch. */
export function Ball({ entry, frameTeam }) {
  if (!entry) return null;
  const [, x, y, team] = entry;
  const fx = team === frameTeam ? x : 100 - x;
  const fy = team === frameTeam ? y : 100 - y;
  return html`<g data-layer="ball" data-team=${team} style=${{ transform: `translate(${fx * PX}px, ${fy * PY}px)` }}
      class="ball">
    <circle r="1.9" fill="rgba(255,255,255,0.10)" />
    <circle r="0.95" fill="#ffffff" stroke="var(--bg)" strokeWidth="0.3" />
  </g>`;
}
