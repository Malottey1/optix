import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
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
