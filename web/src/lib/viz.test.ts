import { describe, expect, it } from "vitest";
import type { RouteRow, ShotRow, StressSpell } from "../types/ui";
import {
  arrowWidth,
  crosshairLane,
  LANES,
  mirrorLane,
  percentile,
  qualityRatio,
  routeGroups,
  seqColor,
  shotBlockSide,
  shotsIn,
  sliceArc,
  sqrtScale,
  stressAt,
  zoneCenter,
} from "./viz";

describe("lane mirroring and the crosshair", () => {
  it("mirrors flanks and half-spaces and keeps the centre", () => {
    expect(mirrorLane("left_flank")).toBe("right_flank");
    expect(mirrorLane("right_half_space")).toBe("left_half_space");
    expect(mirrorLane("center")).toBe("center");
    for (const l of LANES) expect(mirrorLane(mirrorLane(l))).toBe(l);
  });
  it("puts the crosshair on the claim's own lane, and nowhere without an approved claim", () => {
    expect(crosshairLane({ status: "published", lane: "left_flank" })).toBe("left_flank");
    expect(crosshairLane({ status: "published_with_context", lane: "center" })).toBe("center");
    expect(crosshairLane({ status: "blocked", lane: "left_flank" })).toBeNull();
    expect(crosshairLane(null)).toBeNull();
  });
});

describe("area-proportional marks", () => {
  it("shot blocks: area is proportional to xG", () => {
    const k = 10;
    const area = (xg: number) => shotBlockSide(xg, k) ** 2;
    expect(area(0.4) / area(0.1)).toBeCloseTo(4, 10);
    expect(area(0.05) / area(0.2)).toBeCloseTo(0.25, 10);
    expect(shotBlockSide(0, k)).toBe(0);
  });
  it("sqrt scale maps max to the output max and clamps", () => {
    expect(sqrtScale(25, 25, 10)).toBe(10);
    expect(sqrtScale(25 / 4, 25, 10)).toBeCloseTo(5, 10);
    expect(sqrtScale(50, 25, 10)).toBe(10);
    expect(sqrtScale(0, 25, 10)).toBe(0);
    expect(sqrtScale(3, 0, 10)).toBe(0);
  });
  it("arrow width grows with the square root of the pass count, monotonic", () => {
    const w = [1, 4, 9, 16].map((n) => arrowWidth(n, 16, 2, 10));
    expect(w[3]).toBe(10);
    expect(w[0]! - 2).toBeCloseTo((10 - 2) / 4, 10);
    for (let i = 1; i < w.length; i++) expect(w[i]!).toBeGreaterThan(w[i - 1]!);
    expect(arrowWidth(0, 16)).toBe(0);
  });
});

describe("percentile", () => {
  it("counts values below plus half the ties", () => {
    const xs = [1, 2, 3, 4];
    expect(percentile(xs, 4)).toBe(87.5);
    expect(percentile(xs, 1)).toBe(12.5);
    expect(percentile([5, 5, 5, 5], 5)).toBe(50);
    expect(percentile(xs, 10)).toBe(100);
  });
  it("ignores nulls and returns null without a value or a group", () => {
    expect(percentile([null, 1, 3], 3)).toBe(75);
    expect(percentile([], 1)).toBeNull();
    expect(percentile([1, 2], null)).toBeNull();
  });
});

describe("colour, zones, routes, stress, shots, arcs", () => {
  it("sequential colour runs from grey to green and clamps", () => {
    expect(seqColor(0)).toBe("rgb(95, 107, 128)");
    expect(seqColor(1)).toBe("rgb(55, 230, 168)");
    expect(seqColor(2)).toBe(seqColor(1));
    expect(seqColor(Number.NaN)).toBe(seqColor(0));
  });
  it("zone centres follow thirds then lanes, attacker POV", () => {
    expect(zoneCenter(0, [33.3, 66.7])).toEqual({ x: 33.3 / 2, y: 10 });
    expect(zoneCenter(14, [33.3, 66.7])).toEqual({ x: (66.7 + 100) / 2, y: 90 });
    expect(zoneCenter(7, [33.3, 66.7]).y).toBe(50);
  });
  it("route groups: per-pass value and thickest first", () => {
    const rows: RouteRow[] = [
      ["fwd", 6, 11, 2, 0.02, 1],
      ["fwd", 5, 10, 9, 0.009, 0],
      ["sp", 14, 12, 3, 0.3, 2],
      ["op", 13, 12, 1, 0.05, 1],
    ];
    const f = routeGroups(rows, "fwd");
    expect(f.map((g) => g.passes)).toEqual([9, 2]);
    expect(f[0]!.perPass).toBeCloseTo(0.001, 10);
    expect(routeGroups(rows, "chances").map((g) => g.kind)).toEqual(["sp", "op"]);
  });
  it("pass quality ratio: high-threat share over the league share", () => {
    expect(qualityRatio(2, 10, 0.2)).toBeCloseTo(1, 10);
    expect(qualityRatio(1, 10, 0.2)).toBeCloseTo(0.5, 10);
    expect(qualityRatio(0, 0, 0.2)).toBe(0);
  });
  it("territorial stress accumulates spells up to the playhead", () => {
    const spells: StressSpell[] = [
      [10, 40, 30, 5],
      [100, 160, 60, 9],
    ];
    expect(stressAt(spells, 0)).toBe(0);
    expect(stressAt(spells, 25)).toBe(15);
    expect(stressAt(spells, 99)).toBe(30);
    expect(stressAt(spells, 130)).toBe(60);
    expect(stressAt(spells, 1e9)).toBe(90);
  });
  it("shots inside a window are inclusive and per team", () => {
    const s = (id: string, t: number, team: string): ShotRow => [id, t, team, "p", 90, 50, 0.1, "saved", "open_play"];
    const shots = [s("a", 10, "AUR"), s("b", 20, "NOR"), s("c", 30, "AUR"), s("d", 31, "AUR")];
    expect(shotsIn(shots, "AUR", 10, 30).map((x) => x[0])).toEqual(["a", "c"]);
  });
  it("slice arcs are closed paths and empty for zero radius", () => {
    expect(sliceArc(50, 50, 10, 40, 0, 7)).toMatch(/^M.*Z$/);
    expect(sliceArc(50, 50, 10, 10, 0, 7)).toBe("");
  });
});
