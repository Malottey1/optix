import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { binZone, density, smooth, zoneChange, zoneFromBins } from "./heat";
import { zoneOf, zoneShares } from "./viz";

const DATA = join(__dirname, "..", "..", "public", "data");
const read = (f: string) => JSON.parse(readFileSync(join(DATA, f), "utf-8"));

const COLS = 24;
const ROWS = 16;
const rand = (seed: number) => () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;

describe("heat smoothing", () => {
  const r = rand(7);
  const bins = Array.from({ length: COLS * ROWS }, () => Math.floor(r() * 9));

  it("preserves mass within 1e-9", () => {
    const total = bins.reduce((s, v) => s + v, 0);
    for (const sigma of [0.6, 1, 1.6]) {
      const s = smooth(bins, COLS, ROWS, sigma).reduce((a, v) => a + v, 0);
      expect(Math.abs(s - total)).toBeLessThan(1e-9);
    }
  });

  it("is symmetric: a mirrored grid smooths to the mirrored result", () => {
    const mirror = (v: number[]) => v.map((_, i) => v[Math.floor(i / COLS) * COLS + (COLS - 1 - (i % COLS))]!);
    const flip = (v: number[]) => v.map((_, i) => v[(ROWS - 1 - Math.floor(i / COLS)) * COLS + (i % COLS)]!);
    const a = smooth(mirror(bins), COLS, ROWS);
    const b = mirror(smooth(bins, COLS, ROWS));
    a.forEach((v, i) => expect(v).toBeCloseTo(b[i]!, 12));
    const c = smooth(flip(bins), COLS, ROWS);
    const d = flip(smooth(bins, COLS, ROWS));
    c.forEach((v, i) => expect(v).toBeCloseTo(d[i]!, 12));
  });

  it("spreads a single event symmetrically around its bin", () => {
    const one = new Array(COLS * ROWS).fill(0);
    one[8 * COLS + 12] = 1;
    const s = smooth(one, COLS, ROWS);
    expect(s[8 * COLS + 11]).toBeCloseTo(s[8 * COLS + 13]!, 12);
    expect(s[7 * COLS + 12]).toBeCloseTo(s[9 * COLS + 12]!, 12);
    expect(s[8 * COLS + 12]).toBeGreaterThan(s[8 * COLS + 13]!);
  });
});

describe("heat bins against the exported data", () => {
  const index = read("matches/index.json");
  const showcase = read("matches/m_showcase.json");
  const ui = read("ui.json");
  const tl = read("timeline.json");

  it("each bin lies in exactly the zone zoneOf gives its centre", () => {
    const g = index.heat;
    for (let b = 0; b < COLS * ROWS; b++) {
      const row = Math.floor(b / COLS);
      const col = b % COLS;
      const x = (g.x_edges[col] + g.x_edges[col + 1]) / 2;
      const y = (g.y_edges[row] + g.y_edges[row + 1]) / 2;
      expect(binZone(b, COLS)).toBe(zoneOf(x, y, ui.visuals.zones.third_x));
    }
  });

  it("bin sums equal the track's event counts and the 15 zones equal zoneShares exactly", () => {
    for (const code of Object.keys(showcase.heat.teams)) {
      showcase.heat.teams[code].forEach((bins: number[], h: number) => {
        const p = tl.periods[h];
        const want = zoneShares(ui.track, code, p.start_sec, p.end_sec, ui.visuals.zones.third_x);
        const got = zoneFromBins(bins, COLS);
        expect(got.n).toBe(want.n);
        expect(got.shares).toEqual(want.shares);
      });
    }
  });

  it("the density map keeps the mass of the bins", () => {
    const bins: number[] = showcase.heat.teams.AUR[0];
    const d = density(index.heat, bins);
    const mass = d.reduce((s, v, b) => {
      const row = Math.floor(b / COLS);
      const col = b % COLS;
      const area =
        ((index.heat.x_edges[col + 1] - index.heat.x_edges[col]) *
          (index.heat.y_edges[row + 1] - index.heat.y_edges[row])) /
        100;
      return s + v * area;
    }, 0);
    expect(Math.abs(mass - bins.reduce((s, v) => s + v, 0))).toBeLessThan(1e-9);
  });

  it("names the largest rise and fall of the zone share", () => {
    const [a, b] = showcase.heat.teams.AUR;
    const { change, rise, fall } = zoneChange(a, b, COLS);
    expect(change[rise]).toBe(Math.max(...change));
    expect(change[fall]).toBe(Math.min(...change));
  });
});
