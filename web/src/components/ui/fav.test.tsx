import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { followedFixture } from "../../features/fixtures/FixturesPage";
import { clearFavourites, EMPTY, sanitizeFavs, toggleFavourite, useFavourites } from "../../state/favourites";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const matches = () => new MatchFiles("./matches/", disk);
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });

afterEach(() => {
  cleanup();
  act(() => clearFavourites());
  window.location.hash = "";
  vi.restoreAllMocks();
});

describe("favourites store", () => {
  it("sanitizes stored data: string ids only, unique, unknown keys dropped", () => {
    expect(sanitizeFavs(null)).toEqual(EMPTY);
    expect(sanitizeFavs({ teams: ["AUR", "AUR", 3], players: "x", extra: [1] })).toEqual({
      teams: ["AUR"],
      players: [],
      fixtures: [],
    });
  });

  it("toggles and clears; blocked storage never throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    act(() => toggleFavourite("teams", "AUR"));
    expect(useFavourites.getState().teams).toEqual(["AUR"]);
    act(() => toggleFavourite("teams", "AUR"));
    expect(useFavourites.getState().teams).toEqual([]);
    act(() => toggleFavourite("players", "AUR_09"));
    act(() => clearFavourites());
    expect(useFavourites.getState()).toEqual(EMPTY);
  });

  it("a fixture is followed when starred or when a followed team plays", () => {
    const f = { id: "m_001", home: "AUR", away: "NTG" } as Parameters<typeof followedFixture>[0];
    expect(followedFixture(f, [], [])).toBe(false);
    expect(followedFixture(f, ["m_001"], [])).toBe(true);
    expect(followedFixture(f, [], ["NTG"])).toBe(true);
  });
});

describe("favourites on the pages", () => {
  it("a team star is named 'Follow <club>', the Following chip filters, Settings clears", async () => {
    window.location.hash = "#/teams";
    render(<App source={source()} matches={matches()} />);
    const p = await page("teams");
    const team = ui.teams.teams[0];
    const star = screen.getByRole("button", { name: `Follow ${team.name}` });
    expect(star.getAttribute("aria-pressed")).toBe("false");
    expect(star.closest("a")).toBeNull();
    fireEvent.click(star);
    expect(star.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(p.querySelector("[data-following-chip]")!);
    await waitFor(() => expect(p.querySelectorAll("a[data-team]").length).toBe(1));
    expect(p.textContent).not.toMatch(/account|sign in|log in/i);
    fireEvent.click(document.getElementById("open-settings")!);
    const clear = await waitFor(() => document.getElementById("clear-favourites") as HTMLButtonElement);
    expect(clear.disabled).toBe(false);
    fireEvent.click(clear);
    expect(useFavourites.getState()).toEqual(EMPTY);
    expect(clear.disabled).toBe(true);
  });

  it("player and fixture stars sit beside their links", async () => {
    window.location.hash = "#/players";
    render(<App source={source()} matches={matches()} />);
    const p = await page("players");
    const pl = ui.players[0];
    const star = await waitFor(() => p.querySelector(`[data-fav='players:${pl.id}']`) as HTMLButtonElement);
    expect(star.getAttribute("aria-label")).toBe(`Follow ${pl.name}`);
    fireEvent.click(star);
    fireEvent.click(p.querySelector("[data-following-chip]")!);
    await waitFor(() => expect(p.querySelectorAll("a[data-player]").length).toBe(1));
    cleanup();
    window.location.hash = "#/fixtures";
    render(<App source={source()} matches={matches()} />);
    const f = await page("fixtures");
    const fx = await waitFor(() => {
      const el = f.querySelector("[data-fav^='fixtures:']");
      if (!el) throw new Error("not yet");
      return el;
    });
    expect(fx.closest("a")).toBeNull();
  });
});
