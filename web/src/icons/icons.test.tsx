import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { InsightLayer, LANE_EDGES } from "../components/pitch/Pitch";
import type { Insight } from "../types/ui";
import { Icon, ICON_GROUPS, ICON_NAMES, type IconName } from "./index";

const SHEET: Record<string, string[]> = {
  navigation: ["live", "home", "teams", "players", "tech", "settings"],
  playback: ["play", "pause", "restart", "speed", "scrub"],
  events: [
    "pass",
    "shot",
    "goal",
    "tackle",
    "interception",
    "pressure",
    "possession-change",
    "foul",
    "yellow-card",
    "red-card",
    "substitution",
    "corner",
  ],
  lanes: ["lane-left-flank", "lane-left-half-space", "lane-centre", "lane-right-half-space", "lane-right-flank"],
  verdicts: [
    "verdict-passed",
    "verdict-revised",
    "verdict-blocked",
    "verdict-context",
    "evidence-drawer",
    "trace-to-data",
  ],
  styles: [
    "style-high-press",
    "style-low-block",
    "style-patient-possession",
    "style-direct-play",
    "style-wing-play",
    "style-central-play",
  ],
  metrics: [
    "metric-xg",
    "metric-xt",
    "metric-field-tilt",
    "metric-momentum",
    "metric-territorial-stress",
    "metric-rhythm",
  ],
  patterns: [
    "pattern-bait-switch",
    "pattern-cutback",
    "pattern-flank-isolation",
    "pattern-elastic-low-block",
    "pattern-counter-press",
    "pattern-rest-defence",
    "pattern-starved-finisher",
    "pattern-tactical-fouling",
  ],
};
const ALLOWED_PAINT = new Set(["none", "currentColor", "var(--card-yellow)", "var(--card-red)", "var(--lane-fill)"]);
const html = (name: IconName, title?: string) => renderToStaticMarkup(<Icon name={name} title={title} />);

describe("icon manifest", () => {
  it("holds exactly the 54 icons of the sheet, in its groups", () => {
    expect(ICON_GROUPS).toEqual(SHEET);
    expect(ICON_NAMES).toHaveLength(54);
    expect(new Set(ICON_NAMES).size).toBe(54);
  });

  it.each(ICON_NAMES)("%s is a 24 x 24 outline svg without raster, text or remote reference", (name) => {
    const h = html(name);
    expect(h.startsWith("<svg")).toBe(true);
    expect(h).toContain('viewBox="0 0 24 24"');
    expect(h).toContain('stroke-width="1.75"');
    expect(h).toContain('stroke-linecap="round"');
    expect(h).toContain('stroke-linejoin="round"');
    expect(h).not.toMatch(/<image|<text|<use|<foreignObject|href|base64|data:|https?:/);
    for (const m of h.matchAll(/\b(?:fill|stroke)="([^"]*)"/g)) expect(ALLOWED_PAINT).toContain(m[1]);
    expect(h).toContain(`data-icon="${name}"`);
    expect(h).toContain('aria-hidden="true"');
  });

  it("is decorative by default and named when a title is given", () => {
    const h = html("live", "Live Center");
    expect(h).toContain('role="img"');
    expect(h).not.toContain("aria-hidden");
    const id = /aria-labelledby="([^"]+)"/.exec(h)?.[1];
    expect(id).toBeTruthy();
    expect(h).toContain(`<title id="${id}">Live Center</title>`);
  });

  it("only the card and lane icons use colour tokens", () => {
    for (const name of ICON_NAMES) {
      const tokens = [...html(name).matchAll(/var\((--[a-z-]+)\)/g)].map((m) => m[1]);
      if (name === "yellow-card") expect(new Set(tokens)).toEqual(new Set(["--card-yellow"]));
      else if (name === "red-card") expect(new Set(tokens)).toEqual(new Set(["--card-red"]));
      else if (name.startsWith("lane-")) expect(new Set(tokens)).toEqual(new Set(["--lane-fill"]));
      else expect(tokens).toEqual([]);
    }
  });

  it("the colour tokens are defined", () => {
    const css = readFileSync("src/styles/tokens.css", "utf8");
    for (const t of ["--card-yellow", "--card-red", "--lane-fill"]) expect(css).toMatch(new RegExp(`${t}:`));
  });
});

describe("lane icons follow the Focus Pitch", () => {
  const LANES = ["left_flank", "left_half_space", "center", "right_half_space", "right_flank"];
  const ICON: Record<string, IconName> = {
    left_flank: "lane-left-flank",
    left_half_space: "lane-left-half-space",
    center: "lane-centre",
    right_half_space: "lane-right-half-space",
    right_flank: "lane-right-flank",
  };
  const attr = (h: string, tag: RegExp, a: string) => Number(new RegExp(`${a}="([0-9.]+)"`).exec(tag.exec(h)![0])![1]);

  it.each(LANES.map((l, i) => [l, i] as const))("%s: the glyph's band sits in the pitch's lane band", (lane, i) => {
    const y0 = LANE_EDGES[i]!;
    const y1 = LANE_EDGES[i + 1]!;
    const insight = {
      insight_id: "ins",
      claim_id: "clm",
      insight_type: "matchup_mismatch",
      teams: { primary: "AUR" },
      payload: { focus: { x_min: 0, x_max: 100, y_min: y0, y_max: y1 }, metrics: { lane }, points: [] },
    } as unknown as Insight;
    const pitch = renderToStaticMarkup(
      <svg>
        <InsightLayer insight={insight} side="home" markerId="m" />
      </svg>,
    );
    const band = /<rect data-lane="[a-z_]+"[^>]*>/;
    expect(band.exec(pitch)![0]).toContain(`data-lane="${lane}"`);
    const pTop = attr(pitch, band, "y") / 68;
    const pBot = pTop + attr(pitch, band, "height") / 68;

    const glyph = html(ICON[lane]!);
    const gBand = /<rect data-lane-band="\d"[^>]*>/;
    expect(gBand.exec(glyph)![0]).toContain(`data-lane-band="${i}"`);
    // the glyph's pitch outline runs from y = 5 to 19
    const gTop = (attr(glyph, gBand, "y") - 5) / 14;
    const gBot = gTop + attr(glyph, gBand, "height") / 14;
    // same lane: the glyph's (inset) band lies inside the pitch band and shares its centre
    expect(pTop).toBeCloseTo(y0 / 100, 6);
    expect(gTop).toBeGreaterThanOrEqual(pTop - 1e-9);
    expect(gBot).toBeLessThanOrEqual(pBot + 1e-9);
    expect((gTop + gBot) / 2).toBeCloseTo((pTop + pBot) / 2, 6);
  });
});
