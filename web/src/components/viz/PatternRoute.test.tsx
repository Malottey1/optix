import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { patternIcon } from "../../icons";
import { patternLabel } from "../../lib/i18n";
import type { Insight } from "../../types/ui";
import { ARROW_FAMILIES, PatternRoute, ROUTE_MAX_NODES, kindCounts, type RoutePoint } from "./PatternRoute";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const insights: Insight[] = readFileSync(join(DATA, "insights.jsonl"), "utf8")
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l));
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));

const pt = (i: number, kind: string): RoutePoint => ({
  event_id: `e${i}`,
  x: 10 + i,
  y: 20,
  x_end: kind === "pass" ? 30 + i : null,
  y_end: kind === "pass" ? 60 : null,
  kind,
});

afterEach(cleanup);

describe("tactical pattern cards", () => {
  it("every pattern family in the showcase stream has its own icon and name", () => {
    const fams = insights.filter((i) => i.insight_type === "tactical_pattern").map((i) => i.payload.family);
    expect(fams.length).toBeGreaterThan(0);
    for (const f of fams) {
      expect(patternIcon(f)).not.toBe("evidence-drawer");
      for (const lang of ["en", "es", "fr"] as const) expect(patternLabel(f, lang)).not.toMatch(/^pat_|_/);
    }
  });

  it("an unknown family degrades to the generic icon, a readable name and the route of event nodes", () => {
    expect(patternIcon("pat_not_yet_built")).toBe("evidence-drawer");
    expect(patternLabel("pat_not_yet_built", "es")).toBe("not yet built");
    const points = [pt(1, "pass"), pt(2, "pressure"), pt(3, "shot")];
    const { container } = render(
      <PatternRoute family="pat_not_yet_built" points={points} rows={{}} periods={[]} color="red" claimId="c1" />,
    );
    expect(container.querySelector("[data-viz='pattern-route']")).toBeTruthy();
    expect(container.querySelectorAll("li[data-event-id]").length).toBe(3);
  });

  it("families about where the ball went draw arrows, one per pass, and a dot per shot", () => {
    const points = [pt(1, "pass"), pt(2, "pass"), pt(3, "shot")];
    for (const family of ARROW_FAMILIES) {
      const { container } = render(
        <PatternRoute family={family} points={points} rows={{}} periods={[]} color="red" claimId="c" />,
      );
      expect(container.querySelector("[data-viz='pattern-arrows']")).toBeTruthy();
      expect(container.querySelectorAll("line[data-event-id]").length).toBe(2);
      expect(container.querySelectorAll("circle[data-event-id]").length).toBe(1);
      cleanup();
    }
  });

  it("a long route is capped and points to the drawer for the rest; no count is computed on the page", () => {
    const points = Array.from({ length: ROUTE_MAX_NODES + 3 }, (_, i) => pt(i, "possession_change"));
    const { container, getByText } = render(
      <PatternRoute family="pat_counter_press" points={points} rows={{}} periods={[]} color="red" claimId="c" />,
    );
    expect(container.querySelectorAll("li[data-event-id]").length).toBe(ROUTE_MAX_NODES);
    expect(getByText("and more (the evidence drawer lists all)")).toBeTruthy();
    expect(kindCounts(points)).toEqual([["possession_change", ROUTE_MAX_NODES + 3]]);
  });

  it("the catalogue and signature patterns come from ui.json, every family with a registry icon", () => {
    expect(ui.patterns.catalogue.length).toBe(12); // eight Tier 1 and four Tier 2 families
    for (const r of ui.patterns.catalogue) expect(patternIcon(r.family)).toBe(r.icon);
    for (const rows of Object.values(ui.patterns.signature) as { family: string; icon: string }[][])
      for (const r of rows) expect(patternIcon(r.family)).toBe(r.icon);
  });
});
