// Heat map maths for HeatPitch (pure, unit-tested). The export gives raw integer counts of on-ball
// events per bin on a zone-aligned 24 x 16 grid (agents/match_export.py): 8 columns per third and
// 3/3/4/3/3 rows per lane, so the 15 zone values below are sums of whole bins and equal the zone
// shares of the track (zoneShares in lib/viz.ts) exactly. Smoothing is display only: every number
// a reader sees (legend, table, sentence) comes from the raw bins or from the smoothed mass, which
// equals the raw mass.

export interface HeatGrid {
  cols: number;
  rows: number;
  x_edges: number[];
  y_edges: number[];
}

/** Rows per lane and columns per third of the export's grid. */
export const ROWS_PER_LANE = [3, 3, 4, 3, 3] as const;
export const COLS_PER_THIRD = 8;

/** Normalised 1-D Gaussian weights at offsets -r..r. */
function kernel(sigma: number): number[] {
  const r = Math.max(1, Math.ceil(3 * sigma));
  const w: number[] = [];
  for (let d = -r; d <= r; d++) w.push(Math.exp(-(d * d) / (2 * sigma * sigma)));
  return w;
}

/** One pass along an axis. Each cell spreads its mass over its in-grid neighbours with the kernel
 * renormalised to the cells that exist (edge-normalised), so the total is unchanged. */
function pass1d(src: Float64Array, cols: number, rows: number, w: number[], alongX: boolean): Float64Array {
  const out = new Float64Array(src.length);
  const r = (w.length - 1) / 2;
  const n = alongX ? cols : rows;
  // per position, the kernel sum over in-grid targets (same for every line)
  const norm = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let s = 0;
    for (let d = -r; d <= r; d++) if (i + d >= 0 && i + d < n) s += w[d + r]!;
    norm[i] = s;
  }
  for (let row = 0; row < rows; row++)
    for (let col = 0; col < cols; col++) {
      const v = src[row * cols + col]!;
      if (!v) continue;
      const i = alongX ? col : row;
      for (let d = -r; d <= r; d++) {
        const j = i + d;
        if (j < 0 || j >= n) continue;
        const k = alongX ? row * cols + j : j * cols + col;
        out[k]! += (v * w[d + r]!) / norm[i]!;
      }
    }
  return out;
}

/** Separable Gaussian smoothing in bin-index space (sigma in bins, default 1), edge-normalised:
 * mass is preserved and a mirrored grid gives the mirrored result. */
export function smooth(bins: readonly number[], cols: number, rows: number, sigma = 1): number[] {
  const w = kernel(sigma);
  const a = pass1d(Float64Array.from(bins), cols, rows, w, true);
  return Array.from(pass1d(a, cols, rows, w, false));
}

/** Zone (third · 5 + lane, as zoneOf) of a bin index (row · cols + col). */
export function binZone(b: number, cols: number): number {
  const row = Math.floor(b / cols);
  const col = b % cols;
  let lane = 0;
  let acc = ROWS_PER_LANE[0];
  while (row >= acc) acc += ROWS_PER_LANE[++lane]!;
  return Math.floor(col / COLS_PER_THIRD) * 5 + lane;
}

/** The 15 zone counts and shares of a bin vector (shares sum to 1; all 0 without events). */
export function zoneFromBins(bins: readonly number[], cols: number): { counts: number[]; shares: number[]; n: number } {
  const counts = new Array<number>(15).fill(0);
  bins.forEach((v, b) => (counts[binZone(b, cols)]! += v));
  const n = counts.reduce((s, v) => s + v, 0);
  return { counts, shares: counts.map((c) => (n ? c / n : 0)), n };
}

/** Area of a bin in % of the pitch (coordinates are 0-100 on both axes). */
export function binArea(g: HeatGrid, b: number): number {
  const row = Math.floor(b / g.cols);
  const col = b % g.cols;
  return ((g.x_edges[col + 1]! - g.x_edges[col]!) * (g.y_edges[row + 1]! - g.y_edges[row]!)) / 100;
}

/** Display values: smoothed events per 1% of the pitch area (bins differ in size, so a count alone
 * would make the centre lane's smaller bins look cooler). */
export function density(g: HeatGrid, bins: readonly number[], sigma = 1): number[] {
  return smooth(bins, g.cols, g.rows, sigma).map((v, b) => v / binArea(g, b));
}

/** Largest rise and fall of the zone share, second half minus first, in points (1 dp). */
export function zoneChange(first: readonly number[], second: readonly number[], cols: number) {
  const a = zoneFromBins(first, cols).shares;
  const b = zoneFromBins(second, cols).shares;
  const change = a.map((s, z) => Math.round((b[z]! - s) * 1000) / 10);
  let rise = 0;
  let fall = 0;
  change.forEach((c, z) => {
    if (c > change[rise]!) rise = z;
    if (c < change[fall]!) fall = z;
  });
  return { change, rise, fall };
}
