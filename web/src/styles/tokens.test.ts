import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// Vitest runs from web/; a ?raw import of a .css file comes back empty under its CSS handling.
const css = readFileSync("src/styles/tokens.css", "utf8");
const root = css.slice(0, css.indexOf("}"));
const token = (name: string) => root.match(new RegExp(`--${name}:\\s*(#[0-9a-f]{6})`, "i"))?.[1];

function lum(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const f = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(r!) + 0.7152 * f(g!) + 0.0722 * f(b!);
}
const contrast = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x! + 0.05) / (y! + 0.05);
};

describe("club accent tokens", () => {
  const bg = token("bg")!;
  const surface = token("surface-2")!;
  for (const code of ["aur", "ntg", "cal", "ves", "har"]) {
    it(`${code}: at least 3:1 on the dark background and 4.5:1 for the code text on the disc`, () => {
      const c = token(`team-${code}`);
      expect(c, `--team-${code}`).toBeTruthy();
      expect(contrast(c!, bg)).toBeGreaterThanOrEqual(3);
      expect(contrast(c!, surface)).toBeGreaterThanOrEqual(3);
      expect(contrast(c!, "#05080f")).toBeGreaterThanOrEqual(4.5);
    });
  }
  it("no club accent equals a verdict colour", () => {
    const verdicts = ["pass", "revise", "block", "accent"].map((n) => token(n)!.toLowerCase());
    for (const code of ["aur", "ntg", "cal", "ves", "har"]) expect(verdicts).not.toContain(token(`team-${code}`));
  });
});

describe("heat map tokens", () => {
  const pitch = token("pitch")!;
  const reserved = ["pass", "revise", "block", "accent", "home", "away", "card-yellow", "card-red", "muted-accent"]
    .concat(["aur", "ntg", "cal", "ves", "har"].map((c) => `team-${c}`))
    .map((n) => token(n)!.toLowerCase());
  for (const name of ["heat-seq", "heat-rise", "heat-fall"]) {
    it(`${name}: at least 3:1 on the pitch and not a verdict, team or club colour`, () => {
      const c = token(name);
      expect(c, `--${name}`).toBeTruthy();
      expect(contrast(c!, pitch)).toBeGreaterThanOrEqual(3);
      expect(reserved).not.toContain(c!.toLowerCase());
    });
  }
  it("rise and fall differ in lightness as well as hue (readable without colour vision)", () => {
    expect(Math.abs(lum(token("heat-rise")!) - lum(token("heat-fall")!))).toBeGreaterThan(0.05);
  });
});
