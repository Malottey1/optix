import { describe, expect, it } from "vitest";
import { cell, clock, num, pct, phase, signed } from "./format";

const periods = [
  { period: 1, start_sec: 6, end_sec: 2958 },
  { period: 2, start_sec: 2965, end_sec: 6081 },
];

describe("format", () => {
  it("writes numbers as the engine did, with the language's decimal mark", () => {
    expect(num(75.5)).toBe("75.5");
    expect(num(75.5, "fr")).toBe("75,5");
    expect(num(null)).toBe("–");
    expect(pct(19.3, "es")).toBe("19,3%");
    expect(signed(-6.1)).toBe("−6.1");
    expect(cell("0.81 [0.69-0.90]", "fr")).toBe("0,81 [0,69-0,90]");
  });

  it("turns clock seconds into football time with stoppage time", () => {
    expect(clock(0, periods)).toBe("00:00");
    expect(clock(2706, periods)).toBe("45:00");
    expect(clock(2760, periods)).toBe("45+1");
    expect(clock(2965, periods)).toBe("45:00");
    expect(clock(6081, periods)).toBe("90+7");
  });

  it("names the phase of the match", () => {
    expect(phase(0, periods, 6081)).toBe("pre");
    expect(phase(100, periods, 6081)).toBe("first");
    expect(phase(2960, periods, 6081)).toBe("half");
    expect(phase(4000, periods, 6081)).toBe("second");
    expect(phase(6081, periods, 6081)).toBe("full");
  });
});
