// Pass and chance lines on a pitch (attacker's frame, attacking left to right): one thin line per
// pass, 2 px on screen at any size, with a small start dot and an arrowhead; a chance ends in a ring
// on the shot it set up (filled for a goal). Used by the Player Console's pass map and chances tab
// and by the chance evidence drawer, so all three read the same way.
import { PX, PY } from "../pitch/Pitch";

/** Pitch units: the arrowhead's length and half width, the start dot and the shot ring. */
const HEAD = 1.9;
const HALF = 0.95;
const DOT = 0.6;
const RING = 1.35;

const r2 = (v: number) => Math.round(v * 100) / 100;

/** The line's end (before the arrowhead) and the arrowhead polygon, for a pass from a to b (pitch
 * units). With `ring`, the tip stops on the ring's edge. */
export function lineGeometry(ax: number, ay: number, bx: number, by: number, ring = 0) {
  const len = Math.hypot(bx - ax, by - ay) || 1;
  const ux = (bx - ax) / len;
  const uy = (by - ay) / len;
  const tx = bx - ux * ring;
  const ty = by - uy * ring;
  const head = Math.min(HEAD, len * 0.45);
  const baseX = tx - ux * head;
  const baseY = ty - uy * head;
  const w = (HALF * head) / HEAD;
  return {
    end: [r2(baseX), r2(baseY)] as const,
    head: `${r2(tx)},${r2(ty)} ${r2(baseX - uy * w)},${r2(baseY + ux * w)} ${r2(baseX + uy * w)},${r2(baseY - ux * w)}`,
  };
}

/** One pass: x and y on the 0–100 data scale. `shot` draws the ring of the shot it set up. */
export function PassLine({
  x0,
  y0,
  x1,
  y1,
  color,
  shot,
}: {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  color: string;
  shot?: "goal" | "other";
}) {
  const ax = x0 * PX;
  const ay = y0 * PY;
  const bx = x1 * PX;
  const by = y1 * PY;
  const g = lineGeometry(ax, ay, bx, by, shot ? RING + 0.25 : 0);
  return (
    <>
      <line
        x1={r2(ax)}
        y1={r2(ay)}
        x2={g.end[0]}
        y2={g.end[1]}
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={r2(ax)} cy={r2(ay)} r={DOT} fill={color} />
      <polygon points={g.head} fill={color} />
      {shot && (
        <circle
          cx={r2(bx)}
          cy={r2(by)}
          r={RING}
          fill={shot === "goal" ? color : "var(--surface-1)"}
          stroke={color}
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          data-shot={shot}
        />
      )}
    </>
  );
}
