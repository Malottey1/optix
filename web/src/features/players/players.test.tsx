import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { setSetting } from "../../state/settings";
import type { PlayerRow } from "../../types/ui";
import { divergingValues } from "./PlayerConsole";
import { filterPlayers } from "./PlayerDeck";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const matches = () => new MatchFiles("./matches/", disk);
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
const players = ui.players as PlayerRow[];

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });
const words = (el: Element) => (el.textContent ?? "").split(/\s+/).filter(Boolean).length;

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("Player Deck", () => {
  it("filters by team and position and searches names, accent-blind", () => {
    expect(filterPlayers(players, "", "", "")).toHaveLength(players.length);
    const har = filterPlayers(players, "HAR", "", "");
    expect(har.length).toBeGreaterThan(0);
    expect(har.every((p) => p.team === "HAR")).toBe(true);
    const gk = filterPlayers(players, "HAR", "GK", "");
    expect(gk.every((p) => p.team === "HAR" && p.position === "GK")).toBe(true);
    const strip = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "");
    const accented = players.find((p) => strip(p.name) !== p.name)!;
    const plain = strip(accented.name).toUpperCase();
    expect(filterPlayers(players, "", "", plain).map((p) => p.id)).toContain(accented.id);
    expect(filterPlayers(players, "", "", "zzzz")).toHaveLength(0);
  });

  it("cards show only badge, name, position, goals and assists, within the card budget", async () => {
    window.location.hash = "#/players";
    render(<App source={source()} />);
    const p = await page("players");
    const cards = await waitFor(() => {
      const c = [...p.querySelectorAll("a[data-player]")];
      expect(c.length).toBe(players.length);
      return c;
    });
    for (const c of cards) {
      const row = players.find((x) => x.id === c.getAttribute("data-player"))!;
      expect(c.getAttribute("href")).toBe(`#/players/${row.id}`);
      expect(c.querySelector("[data-team-badge]")).toBeTruthy();
      expect([...c.querySelectorAll("dd")].map((d) => d.textContent)).toEqual([String(row.goals), String(row.assists)]);
      expect(words(c)).toBeLessThanOrEqual(30);
    }
    fireEvent.change(p.querySelector("#deck-team")!, { target: { value: "VES" } });
    fireEvent.change(p.querySelector("#deck-position")!, { target: { value: "FW" } });
    await waitFor(() =>
      expect(p.querySelectorAll("a[data-player]").length).toBe(filterPlayers(players, "VES", "FW", "").length),
    );
  });
});

describe("Player Console", () => {
  it("diverging bars are the pizza's percentiles around the median", () => {
    for (const p of players.slice(0, 20))
      for (const r of divergingValues(p, players)) {
        if (r.pctl == null) expect(r.delta).toBeNull();
        else expect(r.delta).toBe(r.pctl - 50);
      }
  });

  it("Raw / With context comes only from the Verifier's fired check", async () => {
    const withCheck = players.find((p) => p.checks.some((c) => c.fired && c.original))!;
    const check = withCheck.checks.find((c) => c.fired && c.original)!;
    window.location.hash = `#/players/${withCheck.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    const box = await waitFor(() => p.querySelector(`[data-context='${check.rule}']`) as HTMLElement);
    const sentence = () => box.querySelector("[data-role='player-sentence']")!.textContent;
    expect(sentence()).toBe(check.text.en!.casual);
    fireEvent.click(screen.getByRole("radio", { name: "Raw" }));
    await waitFor(() => expect(sentence()).toBe(check.original!.en!.casual));
    cleanup();

    const none = players.find((x) => !x.checks.some((c) => c.fired))!;
    window.location.hash = `#/players/${none.id}`;
    render(<App source={source()} matches={matches()} />);
    const q = await page("player");
    const off = await waitFor(() => q.querySelector("[data-context='none']") as HTMLElement);
    for (const b of off.querySelectorAll("button")) expect((b as HTMLButtonElement).disabled).toBe(true);
    expect(off.textContent).toMatch(/No context claim/);
  });

  it("shows routes (top eight, then all), the touch map and pattern evidence", async () => {
    const [pid, rows] = Object.entries(
      ui.patterns.players as Record<string, { family: string; evidence: string[] }[]>,
    )[0]!;
    window.location.hash = `#/players/${pid}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    await waitFor(() => expect(p.querySelector("[data-viz='pass-routes']")).toBeTruthy());
    const showAll = [...p.querySelectorAll("button")].find((b) => /Show all routes/.test(b.textContent ?? ""));
    if (showAll) expect(showAll.textContent).toMatch(/\(\d+\)/);
    await waitFor(() => expect(p.querySelectorAll("#touch rect[data-bin]").length).toBe(24 * 16), { timeout: 8000 });
    fireEvent.click(p.querySelector(`[data-family='${rows[0]!.family}'] button`)!);
    const sheet = await waitFor(() => document.querySelector("#player-evidence") as HTMLElement);
    expect([...sheet.querySelectorAll("[data-event-id]")].map((e) => e.getAttribute("data-event-id"))).toEqual(
      rows[0]!.evidence,
    );
  });

  it("console strings follow the language", async () => {
    window.location.hash = `#/players/${players[0]!.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    act(() => setSetting("lang", "fr"));
    await waitFor(() => expect(p.textContent).toMatch(/Carte des touches/));
    expect(p.textContent).not.toMatch(/Touch map|Passing routes/);
    act(() => setSetting("lang", "en"));
  });
});
