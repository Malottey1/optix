import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { zoneShares } from "../lib/viz";
import { HeatPitch, heatValues } from "./HeatPitch";

const DATA = join(__dirname, "..", "..", "public", "data");
const read = (f: string) => JSON.parse(readFileSync(join(DATA, f), "utf8"));
const index = read("matches/index.json");
const showcase = read("matches/m_showcase.json");
const ui = read("ui.json");
const tl = read("timeline.json");

afterEach(cleanup);

const view = () =>
  render(<HeatPitch grid={index.heat} teams={showcase.heat.teams} codes={["AUR", "NTG"]} initialTeam="AUR" />);

describe("HeatPitch", () => {
  it("draws one rect per bin whose counts sum to the team's on-ball events", () => {
    const { container } = view();
    const bins = container.querySelectorAll("rect[data-bin]");
    expect(bins.length).toBe(24 * 16);
    const sum = [...bins].reduce((s, r) => s + Number(r.getAttribute("data-count")), 0);
    const n = ui.track.filter((t: [number, number, number, string]) => t[3] === "AUR").length;
    expect(sum).toBe(n);
  });

  it("the View data table shows the 15 zone shares of the exported data, closed by default", () => {
    const { container } = view();
    const details = container.querySelector("details")!;
    expect(details.open).toBe(false);
    const rows = [...container.querySelectorAll("table[data-heat-table='AUR'] tbody tr")];
    expect(rows.length).toBe(15);
    const [p1, p2] = tl.periods;
    const a = zoneShares(ui.track, "AUR", p1.start_sec, p1.end_sec, ui.visuals.zones.third_x).shares;
    const b = zoneShares(ui.track, "AUR", p2.start_sec, p2.end_sec, ui.visuals.zones.third_x).shares;
    rows.forEach((r, z) => {
      const cells = r.querySelectorAll("td");
      expect(cells[0]!.textContent).toBe(String(Math.round(a[z]! * 1000) / 10));
      expect(cells[1]!.textContent).toBe(String(Math.round(b[z]! * 1000) / 10));
    });
  });

  it("team and mode toggles are buttons, and change mode is symmetric around zero", () => {
    const { container, getByText } = view();
    fireEvent.click(getByText("NTG"));
    expect(container.querySelector("figure")!.getAttribute("data-team")).toBe("NTG");
    fireEvent.click(getByText("Change"));
    expect(container.querySelector("figure")!.getAttribute("data-mode")).toBe("change");
    const legend = container.querySelector("[data-heat-legend='change']")!.textContent!;
    const { scale } = heatValues(index.heat, showcase.heat.teams.NTG, "change", "both");
    expect(legend).toContain(`−${scale}`);
    expect(legend).toContain(`+${scale}`);
  });

  it("one summary sentence, no causal wording", () => {
    const { container } = view();
    const text = container.querySelector("figcaption")!.textContent!;
    expect(text).toMatch(/rose most in the .* and fell most in the /);
    expect(text).not.toMatch(/because|caused|due to|so that/i);
  });

  it("a season touch map (one bin list, no halves) keeps every count and a finite legend", () => {
    const heat = read("matches/players-heat-ntg.json");
    const [pid, bins] = Object.entries(heat.players as Record<string, number[][]>)[0]!;
    const total = bins[0]!.reduce((a, b) => a + b, 0);
    const v = heatValues(heat, bins, "volume", "both");
    expect(v.counts.reduce((a, b) => a + b, 0)).toBe(total);
    expect(v.values.every(Number.isFinite)).toBe(true);
    expect(v.scale).toBeGreaterThan(0);
    const { container } = render(<HeatPitch grid={heat} teams={{ [pid]: bins }} codes={[pid]} compact />);
    const sum = [...container.querySelectorAll("rect[data-bin]")].reduce(
      (s, r) => s + Number(r.getAttribute("data-count")),
      0,
    );
    expect(sum).toBe(total);
  });
});
