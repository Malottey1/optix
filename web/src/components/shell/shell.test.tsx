import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("primary navigation and Settings", () => {
  it("the primary nav is Home, Fixtures, Teams, Players, with no Tech link", async () => {
    window.location.hash = "#/fixtures";
    render(<App source={source()} />);
    await page("fixtures");
    for (const nav of screen.getAllByRole("navigation", { name: "Main" })) {
      const links = within(nav).getAllByRole("link");
      expect(links.map((a) => a.getAttribute("href"))).toEqual(["#/", "#/fixtures", "#/teams", "#/players"]);
      expect(within(nav).queryByText(/tech/i)).toBeNull();
    }
  });

  it("Settings holds Technical details, the kits note, and the link opens the Tech page", async () => {
    window.location.hash = "#/teams";
    render(<App source={source()} />);
    await page("teams");
    const opener = document.getElementById("open-settings")!;
    opener.focus();
    fireEvent.click(opener);
    const sheet = await waitFor(() => document.getElementById("settings") as HTMLElement);
    const link = sheet.querySelector<HTMLAnchorElement>("a[data-settings-tech]")!;
    expect(link.getAttribute("href")).toBe("#/tech");
    expect(link.textContent).toMatch(/Technical details/);
    // above the language switch: it comes first in document (and Tab) order
    const lang = sheet.querySelector("#set-lang-h")!;
    expect(link.compareDocumentPosition(lang) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(sheet.querySelector("[data-kits-note]")!.textContent).toMatch(/illustrative, for fictional clubs/);
    // keyboard path: it is a real link, reachable before the language buttons
    const focusables = [...sheet.querySelectorAll<HTMLElement>("a[href], button")];
    expect(focusables.indexOf(link)).toBeLessThan(
      focusables.findIndex((b) => b.closest("[role='group'], [role='radiogroup']")),
    );
    fireEvent.click(link);
    await page("tech");
    await waitFor(() => expect(document.getElementById("settings")).toBeNull());
  });

  it("the #/tech deep link still works", async () => {
    window.location.hash = "#/tech";
    render(<App source={source()} />);
    expect(await page("tech")).toBeTruthy();
  });
});

describe("the floating nav bar and the bottom tab bar", () => {
  const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
  const bars = () => {
    const top = document.querySelector<HTMLElement>("header nav[aria-label='Main']")!;
    const tabs = document.querySelector<HTMLElement>("[data-tab-bar]")!;
    return { top, tabs };
  };
  const items = (nav: HTMLElement) => [...nav.querySelectorAll<HTMLAnchorElement>("a[data-nav-item]")];

  it("both bars carry Home, Fixtures, Teams, Players with their icons and labels", async () => {
    window.location.hash = "#/teams";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    await page("teams");
    const { top, tabs } = bars();
    for (const nav of [top, tabs]) {
      const links = items(nav);
      expect(links.map((a) => a.getAttribute("data-nav-item"))).toEqual(["home", "fixtures", "teams", "players"]);
      expect(links.map((a) => a.querySelector("svg")!.getAttribute("data-icon"))).toEqual([
        "home",
        "fixtures",
        "teams",
        "players",
      ]);
      expect(links.map((a) => a.textContent)).toEqual(["Home", "Fixtures", "Teams", "Players"]);
    }
    // the bar's 18 px icons, the tab bar's 22 px ones
    expect(items(top)[0]!.querySelector("svg")!.getAttribute("width")).toBe("18");
    expect(items(tabs)[0]!.querySelector("svg")!.getAttribute("width")).toBe("22");
    // the tab bar is the small-screen layout: hidden from the breakpoint up, the top links shown
    expect(tabs.className).toContain("min-[720px]:hidden");
    expect(top.className).toMatch(/hidden .*min-\[720px\]:flex/);
    // tab targets at least 44 px tall
    for (const a of items(tabs)) expect(a.className).toContain("min-h-[52px]");
  });

  it("marks the active item with aria-current on its sub-routes too, and only that one", async () => {
    const show = [
      ["#/teams", "teams"],
      [`#/teams/${ui.teams.teams[0].code}`, "teams"],
      ["#/fixtures", "fixtures"],
      [`#/match/${ui.fixtures[0][0]}`, "fixtures"],
      ["#/players", "players"],
      ["#/", "home"],
    ] as const;
    for (const [hash, active] of show) {
      window.location.hash = hash;
      render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
      await waitFor(() => expect(document.querySelector("[data-page]")).toBeTruthy(), { timeout: 8000 });
      for (const nav of Object.values(bars())) {
        const cur = items(nav).filter((a) => a.getAttribute("aria-current") === "page");
        expect(cur.map((a) => a.dataset.navItem), `${hash} at ${window.location.hash}`).toEqual([active]);
        // the active look: mint text on a soft mint fill; the others muted slate
        expect(cur[0]!.className).toContain("text-accent");
        expect(cur[0]!.className).toContain("bg-accent-soft");
        for (const a of items(nav).filter((x) => x !== cur[0])) expect(a.className).toContain("text-nav-ink");
      }
      cleanup();
    }
    // the Tech page belongs to no nav item
    window.location.hash = "#/tech";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    await page("tech");
    for (const nav of Object.values(bars())) expect(nav.querySelector("[aria-current]")).toBeNull();
  });

  it("every control in the bar has the 2 px mint focus ring and a 200 ms transition", async () => {
    window.location.hash = "#/players";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    await page("players");
    const controls = [
      ...items(bars().top),
      ...items(bars().tabs),
      document.getElementById("open-search")!,
      document.getElementById("open-settings")!,
    ];
    for (const el of controls) {
      for (const c of ["focus-visible:outline-2", "focus-visible:outline-accent", "duration-200"])
        expect(el.className, el.outerHTML.slice(0, 80)).toContain(c);
    }
  });

  it("keyboard: the bar is brand, the four links, Search, Settings in Tab order; the buttons are named and open their dialogs", async () => {
    window.location.hash = "#/fixtures";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    await page("fixtures");
    const bar = document.querySelector<HTMLElement>("[data-nav-bar]")!;
    const order = [...bar.querySelectorAll<HTMLElement>("a[href], button")];
    expect(order.map((e) => e.dataset.navItem ?? e.id ?? "")).toEqual([
      "",
      "home",
      "fixtures",
      "teams",
      "players",
      "open-search",
      "open-settings",
    ]);
    expect(order[0]!.textContent).toContain("Optix");
    for (const e of order) {
      e.focus();
      expect(document.activeElement).toBe(e);
      expect(e.tabIndex).toBe(0);
    }
    const searchBtn = screen.getByRole("button", { name: "Search" });
    const settingsBtn = screen.getByRole("button", { name: "Settings" });
    expect(searchBtn.getAttribute("aria-haspopup")).toBe("dialog");
    fireEvent.click(searchBtn);
    await waitFor(() => expect(document.querySelector("[data-search-input]")).toBeTruthy());
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("[data-search-input]")).toBeNull());
    fireEvent.click(settingsBtn);
    await waitFor(() => expect(document.getElementById("settings")).toBeTruthy());
    // the Settings menu: Technical details, language, clear favourites
    const sheet = document.getElementById("settings")!;
    expect(sheet.querySelector("a[data-settings-tech]")).toBeTruthy();
    expect(sheet.querySelector("#set-lang-h")).toBeTruthy();
    expect(sheet.querySelector("#clear-favourites")).toBeTruthy();
    // a nav link follows its href
    fireEvent.click(items(bars().top)[2]!);
    await page("teams");
  });
});
