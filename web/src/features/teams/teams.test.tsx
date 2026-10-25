import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { nodePos, surname } from "../../charts/LineupPitch";
import { ReplaySource } from "../../data/ReplaySource";
import { setSetting } from "../../state/settings";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });
const words = (el: Element) => (el.textContent ?? "").split(/\s+/).filter(Boolean).length;

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("Team Grid", () => {
  it("one card per club with badge, name, matches and five chips, each card within its word budget", async () => {
    window.location.hash = "#/teams";
    render(<App source={source()} />);
    const p = await page("teams");
    const cards = await waitFor(() => {
      const c = [...p.querySelectorAll("[data-budget='team-card']")];
      expect(c.length).toBe(ui.teams.teams.length);
      return c;
    });
    for (const c of cards) {
      expect(c.getAttribute("href")).toBe(`#/teams/${c.getAttribute("data-team")}`);
      expect(c.querySelectorAll("[data-chip]").length).toBe(5);
      expect(words(c)).toBeLessThanOrEqual(20);
    }
    // the kits line lives once, in Settings; it no longer repeats on the grid
    expect(p.textContent!.split(/kit/i).length - 1).toBe(0);
  });
});

describe("Lineup pitch", () => {
  it("lays out eleven nodes per club that never overlap", () => {
    for (const lu of Object.values(
      ui.lineups as Record<string, { xi: { line: number; slot: number; of: number }[] }>,
    )) {
      expect(lu.xi.length).toBe(11);
      const pts = lu.xi.map(nodePos);
      for (let i = 0; i < pts.length; i++)
        for (let j = i + 1; j < pts.length; j++) {
          const d = Math.hypot(pts[i]!.x - pts[j]!.x, pts[i]!.y - pts[j]!.y);
          expect(d).toBeGreaterThan(9); // metres: more than one node footprint apart
        }
    }
  });

  it("roving focus moves with arrows; Enter opens the mini-profile, Escape closes it and returns focus", async () => {
    window.location.hash = "#/teams/AUR";
    render(<App source={source()} />);
    const p = await page("team-board");
    const nodes = await waitFor(() => {
      const n = [...p.querySelectorAll<HTMLButtonElement>("[data-lineup='AUR'] button[data-node]")];
      expect(n.length).toBe(11);
      return n;
    });
    expect(nodes.filter((n) => n.tabIndex === 0).length).toBe(1);
    const xi = ui.lineups.AUR.xi as { id: string; shirt: number; position: string }[];
    const name = (id: string) => ui.players.find((r: { id: string }) => r.id === id).name as string;
    const pos = { GK: "Goalkeeper", DF: "Defender", MF: "Midfielder", FW: "Forward" }[xi[0]!.position];
    // the visible number and surname come first (the accessible name contains the visible text)
    expect(nodes[0]!.getAttribute("aria-label")).toBe(
      `${xi[0]!.shirt} ${surname(name(xi[0]!.id))}, ${name(xi[0]!.id)}, ${pos}`,
    );
    nodes[0]!.focus();
    fireEvent.keyDown(nodes[0]!, { key: "ArrowRight" });
    expect(document.activeElement).toBe(nodes[1]);
    expect(nodes[1]!.tabIndex).toBe(0);
    fireEvent.keyDown(nodes[1]!, { key: "ArrowLeft" });
    fireEvent.keyDown(nodes[0]!, { key: "ArrowLeft" });
    expect(document.activeElement).toBe(nodes[10]);
    fireEvent.click(nodes[10]!);
    const sheet = await waitFor(() => document.querySelector("#player-sheet") as HTMLElement);
    const pid = xi[10]!.id;
    expect(sheet.querySelector(`[data-player-sheet='${pid}']`)).toBeTruthy();
    expect(sheet.querySelector(`a[data-ledger-link='${pid}']`)!.getAttribute("href")).toBe(`#/players/${pid}`);
    expect(sheet.textContent).toMatch(/VIEW DEEP TACTICAL LEDGER/);
    fireEvent.keyDown(sheet, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("#player-sheet")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(nodes[10]));
    // the close button dismisses it too
    fireEvent.click(nodes[10]!);
    const again = await waitFor(() => document.querySelector("#player-sheet") as HTMLElement);
    fireEvent.click(again.querySelector("[data-close]")!);
    await waitFor(() => expect(document.querySelector("#player-sheet")).toBeNull());
  });

  it("the ledger button and the board explanations are translated", async () => {
    window.location.hash = "#/teams/VES";
    render(<App source={source()} />);
    const p = await page("team-board");
    const en = p.textContent;
    act(() => setSetting("lang", "es"));
    await waitFor(() => expect(p.textContent).not.toBe(en));
    expect(p.textContent).not.toMatch(/Most-used starting XI|Field tilt|trailing/);
    const node = p.querySelector<HTMLButtonElement>("button[data-node]")!;
    fireEvent.click(node);
    const sheet = await waitFor(() => document.querySelector("#player-sheet") as HTMLElement);
    expect(sheet.textContent).not.toMatch(/VIEW DEEP TACTICAL LEDGER/);
    act(() => setSetting("lang", "en"));
  });
});

describe("Style against the league", () => {
  it("rows sit on one league scale per measure and the chips follow the numbers", async () => {
    const { styleRows } = await import("./StyleRows");
    const teams = ui.teams.teams as { code: string; labels: { id: string; value: number; league: number }[] }[];
    const tol = ui.teams.style_rule.tolerance_rel as number;
    for (const team of teams) {
      const rows = styleRows(teams as never, team as never, tol);
      expect(rows.map((r) => r.id)).toEqual(["tempo", "press", "directness", "territory", "counter"]);
      for (const r of rows) {
        const vals = teams.map((t) => t.labels.find((l) => l.id === r.id)!.value);
        expect([r.lo, r.hi]).toEqual([Math.min(...vals), Math.max(...vals)]);
        expect(r.team).toBeCloseTo((r.value - r.lo) / (r.hi - r.lo), 9);
        const uniq = (v: number) => vals.filter((x) => x === v).length === 1;
        const want =
          r.value === r.hi && uniq(r.hi)
            ? "highest"
            : r.value === r.lo && uniq(r.lo)
              ? "lowest"
              : Math.abs(r.value - r.league) <= tol * Math.abs(r.league)
                ? "average"
                : r.value > r.league
                  ? "above"
                  : "below";
        expect(r.chip).toBe(want);
      }
    }
  });

  it("the board renders five rows in the club accent, with no verdict or heat colour", async () => {
    window.location.hash = "#/teams/AUR";
    render(<App source={source()} />);
    const p = await page("team-board");
    const rows = await waitFor(() => {
      const r = [...p.querySelectorAll("[data-style-row]")];
      expect(r.length).toBe(5);
      return r;
    });
    const html = rows.map((r) => r.outerHTML).join("");
    expect(html).toMatch(/--team-aur/);
    expect(html).not.toMatch(/--(pass|revise|block|heat-)/);
  });
});
