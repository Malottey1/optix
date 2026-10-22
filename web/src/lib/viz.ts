// Pure geometry and scale functions behind the visuals. Every visual draws engine numbers through
// these, so each formula is unit-tested (viz.test.ts) and documented in docs/visuals.md.
import type { RouteKind, RouteRow, ShotRow, StressSpell } from "../types/ui";

export const LANES = ["left_flank", "left_half_space", "center", "right_half_space", "right_flank"] as const;
export type Lane = (typeof LANES)[number];

/** The same lane seen from the other team's attacking frame (engine/zones.flip mirrors y). */
export const MIRROR_LANE: Record<Lane, Lane> = {
  left_flank: "right_flank",
  left_half_space: "right_half_space",
  center: "center",
  right_half_space: "left_half_space",
  right_flank: "left_flank",
};
export const mirrorLane = (lane: string): string => MIRROR_LANE[lane as Lane] ?? lane;

/** Lane of greatest structural mismatch, read from the Verifier-approved claim only. A blocked or
 * missing claim gives no crosshair, whatever the bars look like. */
export function crosshairLane(claim: { status: string; lane: string } | null | undefined): string | null {
  if (!claim || claim.status === "blocked") return null;
  return claim.lane;
}

/** Square-root scale: a value's mark grows in AREA with the value (side or width ∝ √value).
 * `max` maps to `maxOut`; 0 maps to 0. */
export function sqrtScale(value: number, max: number, maxOut: number): number {
  if (!(max > 0) || !(value > 0)) return 0;
  return maxOut * Math.sqrt(Math.min(value, max) / max);
}

/** Side of a shot block in pitch units: area ∝ xG, so side = k·√xG, with `kPerUnitXg` the side of a
 * 1.0 xG block. */
export const shotBlockSide = (xg: number, kPerUnitXg: number) => (xg > 0 ? kPerUnitXg * Math.sqrt(xg) : 0);

/** Arrow width ∝ √passes between `min` and `max` px, so area (width × length) tracks the count. */
export function arrowWidth(passes: number, maxPasses: number, min = 1.5, max = 14): number {
  if (passes <= 0) return 0;
  return min + sqrtScale(passes, maxPasses, max - min);
}

/** Percentile rank of `v` among `values`: 100 · (below + ½·equal) / n. null when v or the group is empty. */
export function percentile(values: readonly (number | null)[], v: number | null): number | null {
  const xs = values.filter((x): x is number => x != null && Number.isFinite(x));
  if (v == null || !xs.length) return null;
  let below = 0;
  let equal = 0;
  for (const x of xs) {
    if (x < v) below++;
    else if (x === v) equal++;
  }
  return (100 * (below + 0.5 * equal)) / xs.length;
}

/** Sequential colour from cool grey (t = 0) to the accent green (t = 1), interpolated in sRGB.
 * Lightness rises with t, so the scale still reads in greyscale and for colour-blind viewers. */
const LOW = [0x5f, 0x6b, 0x80];
const HIGH = [0x37, 0xe6, 0xa8];
export function seqColor(t: number): string {
  const u = Math.max(0, Math.min(1, Number.isFinite(t) ? t : 0));
  const c = LOW.map((lo, i) => Math.round(lo + (HIGH[i]! - lo) * u));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

/** Zone index from the export: third (0 own, 1 middle, 2 attacking) · 5 + lane (0 left flank … 4). */
export function zoneCenter(zone: number, thirdX: readonly [number, number]): { x: number; y: number } {
  const third = Math.floor(zone / 5);
  const lane = zone % 5;
  const xs = [0, thirdX[0], thirdX[1], 100];
  return { x: (xs[third]! + xs[third + 1]!) / 2, y: lane * 20 + 10 };
}

export interface RouteGroup {
  kind: RouteKind;
  from: number;
  to: number;
  passes: number;
  /** sum / passes: mean xT added per pass (fwd) or mean xA per chance (op, sp). */
  perPass: number;
  /** Passes ending in a high-threat central cell. */
  hot: number;
}
/** Routes of one kind, thickest first (ties: lower zones first, stable). */
export function routeGroups(rows: readonly RouteRow[], kind: RouteKind | "chances"): RouteGroup[] {
  return rows
    .filter((r) => (kind === "chances" ? r[0] !== "fwd" : r[0] === kind))
    .map(([k, from, to, passes, sum, hot]) => ({ kind: k, from, to, passes, perPass: passes ? sum / passes : 0, hot }))
    .sort((a, b) => b.passes - a.passes || a.from - b.from || a.to - b.to);
}

/** Pass quality of a set of forward passes, the engine's way: share ending in a high-threat cell
 * divided by the league share (1 = league average). */
export const qualityRatio = (hot: number, passes: number, leagueShare: number) =>
  passes && leagueShare ? hot / passes / leagueShare : 0;

/** Cumulative seconds of the spells up to clock t (a spell in progress counts up to t). */
export function stressAt(spells: readonly StressSpell[], t: number): number {
  let s = 0;
  for (const [start, end] of spells) {
    if (start >= t) break;
    s += Math.min(end, t) - start;
  }
  return s;
}

/** Shots of one team inside [from, to] (inclusive), in clock order. */
export const shotsIn = (shots: readonly ShotRow[], team: string, from: number, to: number) =>
  shots.filter((s) => s[2] === team && s[1] >= from && s[1] <= to);

export const sum = (xs: readonly number[]) => xs.reduce((a, b) => a + b, 0);

/** SVG path of slice i of n in a radial chart, between radii r0 and r1
 * (slices run clockwise from 12 o'clock). */
export function sliceArc(cx: number, cy: number, r0: number, r1: number, i: number, n: number, gap = 0.02): string {
  const a0 = (2 * Math.PI * i) / n - Math.PI / 2 + gap;
  const a1 = (2 * Math.PI * (i + 1)) / n - Math.PI / 2 - gap;
  const p = (r: number, a: number) => `${(cx + r * Math.cos(a)).toFixed(2)} ${(cy + r * Math.sin(a)).toFixed(2)}`;
  const large = a1 - a0 > Math.PI ? 1 : 0;
  if (r1 <= r0) return "";
  return `M${p(r0, a0)} L${p(r1, a0)} A${r1} ${r1} 0 ${large} 1 ${p(r1, a1)} L${p(r0, a1)} A${r0} ${r0} 0 ${large} 0 ${p(r0, a0)}Z`;
}
