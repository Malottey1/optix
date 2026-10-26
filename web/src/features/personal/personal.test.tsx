// Personalization in the UI: Fan view (the default) against Analyst view, follow a player, the focus
// metric, Home's "For you" and the blocked-storage fallback. Personalization only selects: every
// number Fan view shows is also in Analyst view, and switching mode or language changes no number.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../App";
import { involvedFromEvents, involvedFromLog, parseEventFile, soFarFromLog } from "../../data/events";
import { expandCard, MatchFiles, parseMatchFile } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { involves, personalize, type Personalizable } from "../../lib/personalize";
import { clearFavourites, toggleFavourite } from "../../state/favourites";
import { seek } from "../../state/replay";
import { setSetting } from "../../state/settings";
import { sanitizeView, setFocus, setMetric, setMode, useView, VIEW_KEY } from "../../state/view";
import { capCards } from "../hub/parts";

const ROOT = join(__dirname, "..", "..", "..", "..");
const DATA = join(ROOT, "web", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const matches = () => new MatchFiles("./matches/", disk);
const m001 = parseMatchFile(JSON.parse(readFileSync(join(DATA, "matches", "m_001.json"), "utf8")), "m_001");
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
const soFarGolden = JSON.parse(readFileSync(join(ROOT, "tests", "fixtures", "player_so_far_golden.json"), "utf8"));

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });
/** Numbers in a text, decimal commas read as points (es / fr), so languages compare. */
const numbers = (s: string) => (s.match(/\d+(?:[.,]\d+)?/g) ?? []).map((n) => Number(n.replace(",", ".")));
const cardIds = (root: ParentNode) =>
  [...root.querySelectorAll("#insights article[data-insight-id]")].map((a) => a.getAttribute("data-insight-id"));

beforeEach(() => {
  setMode("fan");
  setFocus(null);
  setMetric(null);
  clearFavourites();
  setSetting("lang", "en");
});

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

async function hub(id = "m_001") {
  window.location.hash = `#/match/${id}`;
  render(<App source={source()} matches={matches()} />);
  const p = await page("hub");
  await waitFor(() => expect(p.querySelector("[data-turning-points]")).toBeTruthy());
  return p;
}

describe("Fan and Analyst view", () => {
  it("Fan is the default: story sections, at most five cards with a Verified tick, no analyst sections", async () => {
    expect(useView.getState().mode).toBe("fan");
    const p = await hub();
    expect(p.getAttribute("data-view")).toBe("fan");
    expect([...p.querySelectorAll("section[id]")].map((s) => s.id)).toEqual(["insights", "turning", "lineups", "heat"]);
    expect(p.querySelector("[data-ledger-link]")).toBeNull();
    expect(p.querySelector("[data-pager]")).toBeNull();
    expect(p.querySelector("[data-family-chips]")).toBeNull();
    const ids = cardIds(p);
    const want = personalize(capCards(m001.insights.map((c) => expandCard(m001, c))), { mode: "fan" });
    expect(ids).toEqual(want.map((i) => i.insight_id));
    expect(ids.length).toBeLessThanOrEqual(5);
    expect(p.querySelectorAll("[data-verified-tick]").length).toBe(ids.length);
    fireEvent.click(p.querySelector("[data-verified-tick]")!);
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("every number in Fan view is in Analyst view; the mode and language switches change no number", async () => {
    const p = await hub();
    const fanText = p.querySelector("#insights")!.textContent!;
    const header = p.querySelector("[data-budget=hub-header] [data-score]")!.parentElement!.parentElement!.textContent!;
    const fanNums = numbers(fanText.replace(/Top picks from \d+ checked insights/, ""));
    act(() => setSetting("lang", "es"));
    await waitFor(() => expect(p.querySelector("#insights")!.textContent).not.toBe(fanText));
    expect(numbers(p.querySelector("#insights")!.textContent!).sort()).toEqual(numbers(fanText).sort());
    act(() => setSetting("lang", "en"));
    fireEvent.click(
      within(p.querySelector("[data-hub-controls]") as HTMLElement).getByRole("radio", { name: "Analyst view" }),
    );
    await waitFor(() => expect(p.querySelector("[data-pager]")).toBeTruthy());
    expect(p.querySelector("[data-budget=hub-header] [data-score]")!.parentElement!.parentElement!.textContent).toBe(
      header.replace("Chance quality", "xG").replace("Chance quality", "xG"),
    );
    // walk every page of every tab and collect the numbers Analyst view shows
    const seen: number[] = [];
    for (const tab of ["insights", "patterns"]) {
      const b = p.querySelector(`[data-tab=${tab}]`) as HTMLButtonElement;
      if (b.disabled) continue;
      fireEvent.click(b);
      for (;;) {
        seen.push(...numbers(p.querySelector("#insights-list")!.textContent!));
        const next = within(p.querySelector("[data-pager]") as HTMLElement).getByRole("button", { name: /Next/ });
        if ((next as HTMLButtonElement).disabled) break;
        fireEvent.click(next);
      }
    }
    for (const n of fanNums) expect(seen).toContain(n);
  });
});

describe("Follow a player", () => {
  it("focus from the lineup sheet: chip, highlighted jersey, only that player's cards, Player so far", async () => {
    const p = await hub();
    const xi = p.querySelector("[data-xi=home] [data-node]") as HTMLElement;
    const pid = xi.getAttribute("data-node")!;
    fireEvent.click(xi);
    const sheet = await screen.findByRole("dialog");
    fireEvent.click(within(sheet).getByRole("button", { name: "Focus on this player" }));
    expect(useView.getState().focus).toBe(pid);
    fireEvent.keyDown(sheet, { key: "Escape" });
    await waitFor(() => expect(p.querySelector("[data-following]")).toBeTruthy());
    expect(p.querySelector("[data-following]")!.textContent).toContain(String(m001.players[pid]![0]));
    expect(p.querySelector(`[data-node="${pid}"]`)!.getAttribute("data-focused")).toBe("true");
    const cards = capCards(m001.insights.map((c) => expandCard(m001, c)));
    const want = personalize(cards, { mode: "fan", players: [pid] }, involvedFromLog(m001)).map((i) => i.insight_id);
    expect(cardIds(p)).toEqual(want);
    if (!want.length)
      expect(p.querySelector("[data-focus-empty]")!.textContent).toBe("No insight involves this player yet.");
    // the card's counts: an independent recount over the raw log rows
    const card = p.querySelector(`[data-so-far="${pid}"]`)!;
    const shots = (m001.events.rows as unknown[][]).filter(
      (r) => r[3] === pid && m001.events.types[r[4] as number] === "shot",
    ).length;
    expect(card.querySelector("[data-count=shots]")!.getAttribute("data-value")).toBe(String(shots));
    expect(soFarFromLog(m001, pid, m001.duration_sec).shots).toBe(shots);
    expect(card.querySelector("[data-count=passes]")).toBeNull();
    fireEvent.click(p.querySelector("[data-following-remove]")!);
    await waitFor(() => expect(p.querySelector("[data-following]")).toBeNull());
    expect(useView.getState().focus).toBeNull();
  });

  it("live hub: the feed keeps the player's insights and the card counts the events up to the clock", async () => {
    const c = soFarGolden.cases.find(
      (x: { player: string; clock: number }) => x.player === "NTG_10" && x.clock === 2883,
    );
    setFocus("NTG_10");
    setMode("analyst");
    window.location.hash = "#/match/m_showcase";
    render(<App source={source()} matches={matches()} />);
    await page("live");
    act(() => seek(2883));
    const card = await screen.findByText((_, el) => el?.getAttribute("data-so-far") === "NTG_10", undefined, {
      timeout: 8000,
    });
    await waitFor(() => expect(card.querySelector("[data-count=passes]")).toBeTruthy());
    for (const k of ["passes", "shots", "xg", "key_passes", "cards", "subs"])
      expect(Number(card.querySelector(`[data-count=${k}]`)!.getAttribute("data-value"))).toBe(c.counts[k]);
    expect(document.querySelector("[data-following]")!.textContent).toContain("Following:");
    const ev = parseEventFile(
      JSON.parse(readFileSync(join(DATA, "matches", "events-m_showcase.json"), "utf8")),
      "m_showcase",
    );
    const inv = involvedFromEvents(ev);
    const stream = readFileSync(join(DATA, "insights.jsonl"), "utf8")
      .split("\n")
      .filter(Boolean)
      .map((l) => JSON.parse(l) as Personalizable);
    const want = new Set(
      stream.filter((i) => i.clock.start_sec <= 2883 && involves(i, "NTG_10", inv)).map((i) => i.insight_id),
    );
    expect(want.size).toBeGreaterThan(0);
    await waitFor(() =>
      expect(
        new Set(
          [...document.querySelectorAll("#feed article[data-insight-id]")].map((a) =>
            a.getAttribute("data-insight-id"),
          ),
        ),
      ).toEqual(want),
    );
  }, 20000);
});

describe("Focus metric", () => {
  it("a played match offers its one series; the readout reads it and the cards keep that family", async () => {
    const p = await hub();
    const picker = p.querySelector("[data-metric-picker]")!;
    expect([...picker.querySelectorAll("[data-metric]")].map((b) => b.getAttribute("data-metric"))).toEqual([
      "none",
      "momentum",
    ]);
    fireEvent.click(picker.querySelector("[data-metric=momentum]")!);
    const r = await waitFor(() => p.querySelector("[data-metric-readout=momentum]")!);
    const last = (m001.momentum as [number, number][]).at(-1)![1];
    expect(Number(r.querySelector("[data-readout-value]")!.getAttribute("data-readout-value"))).toBe(last);
    expect(r.textContent).toContain("Who is on top");
    for (const a of p.querySelectorAll("#insights article[data-type]"))
      expect(a.getAttribute("data-type")).toBe("momentum_shift");
    fireEvent.click(picker.querySelector("[data-metric=none]")!);
    await waitFor(() => expect(p.querySelector("[data-metric-readout]")).toBeNull());
  });

  it("the live hub offers every metric with a series; rhythm reads the row at the clock", async () => {
    window.location.hash = "#/match/m_showcase";
    render(<App source={source()} matches={matches()} />);
    await page("live");
    const picker = document.querySelector("[data-metric-picker]")!;
    expect([...picker.querySelectorAll("[data-metric]")].map((b) => b.getAttribute("data-metric"))).toEqual([
      "none",
      "momentum",
      "xg",
      "rhythm",
      "stress",
    ]);
    act(() => seek(2760));
    fireEvent.click(picker.querySelector("[data-metric=rhythm]")!);
    const r = await waitFor(() => document.querySelector("[data-metric-readout=rhythm]")!);
    const rows = ui.visuals.rhythm as number[][];
    const row = rows.filter((x) => x[2]! <= 2760).at(-1)!;
    expect(Number(r.querySelector("[data-readout-value]")!.getAttribute("data-readout-value"))).toBe(row[3]);
    // exiting cards animate out first, so wait for the list to settle
    await waitFor(() =>
      expect(
        new Set([...document.querySelectorAll("#feed article[data-type]")].map((a) => a.getAttribute("data-type"))),
      ).toEqual(new Set(["rhythm_wave"])),
    );
  }, 20000);
});

describe("For you", () => {
  it("is hidden without favourites and lists followed clubs' fixtures and players", async () => {
    window.location.hash = "#/";
    render(<App source={source()} matches={matches()} />);
    const p = await page("home");
    await waitFor(() => expect(p.querySelector("[data-home]")).toBeTruthy(), { timeout: 8000 });
    expect(p.querySelector("[data-for-you]")).toBeNull();
    act(() => {
      toggleFavourite("teams", "AUR");
      toggleFavourite("players", "AUR_09");
    });
    const fy = await waitFor(() => p.querySelector("[data-for-you]")!);
    await waitFor(() => expect(fy.querySelectorAll("[data-fixture]").length).toBeGreaterThan(0));
    for (const f of fy.querySelectorAll("[data-fixture]")) expect(f.textContent).toMatch(/AUR|Aur/);
    const row = fy.querySelector("[data-for-you-player=AUR_09]")!;
    const pl = ui.players.find((x: { id: string }) => x.id === "AUR_09");
    expect(row.textContent).toContain(`${pl.goals} goals`);
    expect(fy.querySelector('[data-fav="players:AUR_09"]')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/sign in|log in|account/i);
  });
});

describe("Storage blocked", () => {
  it("falls back to the defaults and keeps the choice in memory", () => {
    const get = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(sanitizeView(undefined)).toEqual({ mode: "fan", focus: null });
    expect(sanitizeView({ mode: "boss", focus: "<x>" })).toEqual({ mode: "fan", focus: null });
    expect(() => setMode("analyst")).not.toThrow();
    expect(() => setFocus("NTG_10")).not.toThrow();
    expect(useView.getState()).toMatchObject({ mode: "analyst", focus: "NTG_10" });
    get.mockRestore();
    set.mockRestore();
    expect(VIEW_KEY).toBe("optix.view.v1");
  });
});
