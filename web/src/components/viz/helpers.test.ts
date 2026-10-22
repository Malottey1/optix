import { describe, expect, it } from "vitest";
import type { PlayerRow, RouteRow, ShotRow } from "../../types/ui";
import { leagueXaPerChance, per3, ratio2, routeValue, visibleRoutes } from "./PassRoutes";
import { comparisonGroup, MIN_PASSES, pizzaValues } from "./PercentilePizza";
import { shotStats } from "./ShotBlocks";
import { press3, tiltPct } from "./StateSwaps";

const player = (id: string, involvement: number, passes = 200, position = "MF"): PlayerRow => ({
  id,
  name: id,
  team: "AUR",
  position,
  involvement,
  team_share: null,
  passes,
  pass_completion: 0.8,
  forward_passes: 50,
  wide_share: 0.3,
  pass_quality_ratio: 1,
  chances: 2,
  chances_open_play: 1,
  chances_set_piece: 1,
  checks: [],
});

describe("pizza", () => {
  it("compares against outfield players with enough passes", () => {
    const ps = [player("a", 10), player("b", 20), player("gk", 99, 400, "GK"), player("few", 99, MIN_PASSES - 1)];
    expect(comparisonGroup(ps).map((p) => p.id)).toEqual(["a", "b"]);
  });
  it("rounds percentiles to whole numbers", () => {
    const g = [player("a", 10), player("b", 20), player("c", 30)];
    const inv = pizzaValues(g[2]!, g).find((v) => v.key === "involvement")!;
    expect(inv.pctl).toBe(83);
  });
});

describe("routes", () => {
  const rows: RouteRow[] = [
    ["fwd", 6, 11, 4, 0.04, 2],
    ["fwd", 5, 10, 1, 0.01, 0],
    ["op", 13, 12, 2, 0.2, 1],
    ["sp", 14, 12, 3, 0.6, 2],
  ];
  it("hides forward routes with one pass and keeps every chance route", () => {
    expect(visibleRoutes(rows, "fwd").map((g) => g.passes)).toEqual([4]);
    expect(visibleRoutes(rows, "chances")).toHaveLength(2);
  });
  it("colours forward routes by pass quality and chances by xA per chance", () => {
    const [f] = visibleRoutes(rows, "fwd");
    expect(routeValue(f!, 0.25)).toBeCloseTo(2, 10);
    const sp = visibleRoutes(rows, "chances").find((g) => g.kind === "sp")!;
    expect(routeValue(sp, 0.25)).toBeCloseTo(0.2, 10);
  });
  it("league xA per chance pools every player's chance routes", () => {
    expect(leagueXaPerChance({ a: rows, b: [["op", 1, 2, 5, 0.2, 0]] })).toBeCloseTo(1 / 10, 10);
    expect(leagueXaPerChance({})).toBe(0);
  });
  it("display rounding", () => {
    expect(per3(0.10449)).toBe(0.104);
    expect(ratio2(4.166)).toBe(4.17);
    expect(tiltPct(0.7551)).toBe(75.5);
    expect(press3(0.14949)).toBe(0.149);
  });
});

describe("shot stats", () => {
  it("count, total xG and xG per shot", () => {
    const s = (xg: number): ShotRow => ["e", 1, "NOR", "p", 90, 50, xg, "saved", "open_play"];
    const st = shotStats([s(0.05), s(0.05), s(0.2)]);
    expect(st.shots).toBe(3);
    expect(st.xg).toBe(0.3);
    expect(st.perShot).toBe(0.1);
  });
});
