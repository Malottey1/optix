import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { setSetting } from "../../state/settings";
import { capCards, layoutMarks } from "./parts";
import type { Insight } from "../../types/ui";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const matches = () => new MatchFiles("./matches/", disk);
const index = JSON.parse(readFileSync(join(DATA, "matches", "index.json"), "utf8"));

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("Fixtures", () => {
  it("lists every match in the data, the live replay pinned first, and filters by team and status", async () => {
    window.location.hash = "#/fixtures";
    render(<App source={source()} matches={matches()} />);
    const p = await page("fixtures");
    const rows = () => [...p.querySelectorAll("[data-fixture]")];
    await waitFor(() => expect(rows().length).toBe(index.fixtures.length));
    expect(rows()[0]!.getAttribute("data-fixture")).toBe("m_showcase");
    expect(rows()[0]!.getAttribute("href")).toBe("#/match/m_showcase");
    fireEvent.change(p.querySelector("#fixtures-team")!, { target: { value: "HAR" } });
    const har = index.fixtures.filter((f: { home: string; away: string }) => f.home === "HAR" || f.away === "HAR");
    await waitFor(() => expect(rows().length).toBe(har.length));
    fireEvent.click(screen.getByRole("radio", { name: "Live replay" }));
    await waitFor(() => expect(rows().length).toBe(0));
  });
});

describe("Match Hub, Final", () => {
  it("shows the recap sections in order, the matchup only with a verified lane claim", async () => {
    for (const [id, withMatchup] of [
      ["m_001", true],
      ["m_007", false],
    ] as const) {
      window.location.hash = `#/match/${id}`;
      render(<App source={source()} matches={matches()} />);
      const p = await page("hub");
      await waitFor(() => expect(p.querySelector("[data-turning-points]")).toBeTruthy());
      const ids = [...p.querySelectorAll("section[id]")].map((s) => s.id);
      expect(ids).toEqual(
        withMatchup ? ["turning", "heat", "cards", "matchup", "log"] : ["turning", "heat", "cards", "log"],
      );
      expect(p.textContent).not.toMatch(/No claim/i);
      expect(p.querySelector("[data-ledger-link]")!.getAttribute("href")).toBe(`#/match/${id}/ledger`);
      cleanup();
    }
  });

  it("a turning point opens the evidence drawer; the language switch changes no number", async () => {
    window.location.hash = "#/match/m_001";
    render(<App source={source()} matches={matches()} />);
    const p = await page("hub");
    const goal = (await waitFor(() => p.querySelector("[data-tp='goal']"))) as HTMLElement;
    fireEvent.click(goal);
    const drawer = await waitFor(() => document.querySelector("#hub-evidence") as HTMLElement);
    expect(drawer.querySelector(`[data-event-id='${goal.dataset.eventId}']`)).toBeTruthy();
    fireEvent.keyDown(drawer, { key: "Escape" });
    await waitFor(() => expect(document.querySelector("#hub-evidence")).toBeNull());
    const nums = () =>
      (p.querySelector("header")!.textContent!.match(/\d+(?:[.,]\d+)?/g) ?? []).map((n) => n.replace(",", "."));
    const before = nums();
    act(() => setSetting("lang", "fr"));
    await waitFor(() => expect(p.textContent).toMatch(/Moments clés/));
    expect(nums()).toEqual(before);
    act(() => setSetting("lang", "en"));
  });

  it("the event log moves with the keyboard", async () => {
    window.location.hash = "#/match/m_002";
    render(<App source={source()} matches={matches()} />);
    const p = await page("hub");
    const list = (await waitFor(() => p.querySelector("[role='listbox']"))) as HTMLElement;
    const first = list.getAttribute("aria-activedescendant");
    fireEvent.keyDown(list, { key: "ArrowDown" });
    await waitFor(() => expect(list.getAttribute("aria-activedescendant")).not.toBe(first));
    fireEvent.keyDown(list, { key: "End" });
    fireEvent.keyDown(list, { key: "Home" });
    await waitFor(() => expect(list.getAttribute("aria-activedescendant")).toBe(first));
  });

  it("unknown match ids say so", async () => {
    window.location.hash = "#/match/m_999";
    render(<App source={source()} matches={matches()} />);
    await page("hub");
    expect(await screen.findByText("This match is not in the data.")).toBeTruthy();
  });
});

describe("hub helpers", () => {
  it("caps pattern cards per family and other cards per type", () => {
    const c = (id: string, type: string, family?: string) =>
      ({ insight_id: id, insight_type: type, payload: { family } }) as unknown as Insight;
    const out = capCards([
      c("a", "tactical_pattern", "p1"),
      c("b", "tactical_pattern", "p1"),
      c("c", "tactical_pattern", "p1"),
      c("d", "tactical_pattern", "p2"),
      c("e", "recap_line"),
      c("f", "recap_line"),
      c("g", "recap_line"),
    ]);
    expect(out.map((i) => i.insight_id)).toEqual(["a", "b", "d", "e", "f"]);
  });

  it("timeline marks never share a row closer than the gap", () => {
    const xs = [1, 2, 3, 10, 10.5, 50];
    const rows = layoutMarks(xs, 4, 8);
    for (let i = 0; i < xs.length; i++)
      for (let j = 0; j < i; j++) if (rows[i] === rows[j]) expect(Math.abs(xs[i]! - xs[j]!)).toBeGreaterThanOrEqual(4);
  });
});
