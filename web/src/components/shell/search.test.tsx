import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { setSetting } from "../../state/settings";
import type { UiData } from "../../types/ui";
import { PER_GROUP, search, searchIndex } from "./SearchOverlay";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8")) as UiData;
const index = searchIndex(ui);

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });
const need = <T,>(el: T | null): T => {
  if (!el) throw new Error("not rendered yet");
  return el;
};

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("search ranking", () => {
  it("indexes every team, player and fixture", () => {
    expect(index.filter((e) => e.group === "teams")).toHaveLength(ui.teams.teams.length);
    expect(index.filter((e) => e.group === "players")).toHaveLength(ui.players.length);
    expect(index.filter((e) => e.group === "fixtures")).toHaveLength(ui.fixtures.length);
  });

  it("groups teams, players, fixtures in that order, a code match first, at most PER_GROUP each", () => {
    const team = ui.teams.teams[0]!;
    const r = search(index, team.code.toLowerCase());
    expect(r[0]!.group).toBe("teams");
    expect(r[0]!.id).toBe(team.code);
    const order = r.map((e) => ["teams", "players", "fixtures"].indexOf(e.group));
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(r.filter((e) => e.group === "players").length).toBeLessThanOrEqual(PER_GROUP.players);
    expect(r.filter((e) => e.group === "fixtures").length).toBeLessThanOrEqual(PER_GROUP.fixtures);
  });

  it("is accent- and case-blind, every word must match, and two codes find their fixtures", () => {
    const strip = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "");
    const accented = ui.players.find((p) => strip(p.name) !== p.name)!;
    const plain = strip(accented.name).toUpperCase();
    expect(search(index, plain).map((e) => e.id)).toContain(accented.id);
    const [, , h, a] = ui.fixtures[0]!;
    const fx = search(index, `${h} ${a}`).filter((e) => e.group === "fixtures");
    expect(fx.length).toBeGreaterThan(0);
    for (const e of fx) expect(e.code.split(" ").sort()).toEqual([h, a].sort());
    expect(search(index, "zzzz")).toEqual([]);
    expect(search(index, "   ")).toEqual([]);
  });

  it("a name prefix outranks a match inside a word", () => {
    const p = ui.players[0]!;
    const first = p.name.split(" ")[0]!.slice(0, 3);
    const r = search(index, first).filter((e) => e.group === "players");
    const ranks = r.map((e) =>
      e.label.toLowerCase().startsWith(first.toLowerCase())
        ? 1
        : e.label
              .toLowerCase()
              .split(/[\s'-]+/)
              .some((w) => w.startsWith(first.toLowerCase()))
          ? 2
          : 3,
    );
    expect([...ranks].sort((a, b) => a - b)).toEqual(ranks);
  });
});

describe("search overlay", () => {
  it("Ctrl+K opens it, arrows and Enter open a result, the count is announced", async () => {
    window.location.hash = "#/fixtures";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    await page("fixtures");
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const input = await waitFor(() => need(document.querySelector<HTMLInputElement>("[data-search-input]")));
    expect(document.activeElement).toBe(input);
    const team = ui.teams.teams[1]!;
    fireEvent.change(input, { target: { value: team.name.slice(0, 4) } });
    const count = document.querySelector("[data-search-count]")!;
    const want = search(index, team.name.slice(0, 4));
    expect(count.getAttribute("data-search-count")).toBe(String(want.length));
    expect(count.textContent).toContain(String(want.length));
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.getAttribute("aria-activedescendant")).toContain(want[1 % want.length]!.id);
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(window.location.hash).toBe(`#${want[0]!.to}`));
    await waitFor(() => expect(document.querySelector("[data-search-input]")).toBeNull());
  });

  it("the button opens it, Escape closes it and focus returns to the button; strings follow the language", async () => {
    window.location.hash = "#/teams";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    await page("teams");
    const opener = document.getElementById("open-search")!;
    opener.focus();
    fireEvent.click(opener);
    const input = await waitFor(() => need(document.querySelector<HTMLInputElement>("[data-search-input]")));
    act(() => setSetting("lang", "fr"));
    await waitFor(() => expect(input.getAttribute("aria-label")).toBe("Rechercher équipes, joueurs et matchs"));
    act(() => setSetting("lang", "en"));
    fireEvent.keyDown(input, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("[data-search-input]")).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});
