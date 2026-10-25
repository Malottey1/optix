import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";
import { MatchFiles } from "./data/matches";
import { ReplaySource } from "./data/ReplaySource";
import { SseSource, type EventSourceLike } from "./data/SseSource";
import { seek, useReplay } from "./state/replay";
import { useSource } from "./state/source";
import { setSetting } from "./state/settings";

const DATA = join(__dirname, "..", "public", "data");
const source = () =>
  new ReplaySource(
    "./data/",
    async (url: string) => new Response(readFileSync(join(DATA, url.split("/").pop()!), "utf8")),
  );
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
const insights = readFileSync(join(DATA, "insights.jsonl"), "utf8")
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l));

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("Live Center", () => {
  it("renders the stream with a rewritten card, its reason and Before / After", async () => {
    window.location.hash = "#/live?t=2760";
    render(<App source={source()} />);
    const page = await screen.findByText((_, el) => el?.getAttribute("data-page") === "live", undefined, {
      timeout: 5000,
    });
    const iid = Object.keys(ui.rewrites).find(
      (id) => insights.find((i) => i.insight_id === id).clock.start_sec <= 2760,
    )!;
    const card = await waitFor(() => page.querySelector(`article[data-insight-id='${iid}']`) as HTMLElement);
    expect(card.dataset.status).toBe("revised");
    const ins = insights.find((i) => i.insight_id === iid);
    expect(within(card).getByText(ins.text.rendered.en.casual)).toBeTruthy();
    expect(within(card).getByText(ui.reasons.en[ui.rewrites[iid].rule_ids[0]])).toBeTruthy();
    fireEvent.click(within(card).getByRole("radio", { name: "Before" }));
    await waitFor(() => expect(within(card).getByText(ui.rewrites[iid].original.en.casual)).toBeTruthy());
  });

  it("switches language to the stream's translated sentence", async () => {
    window.location.hash = "#/live";
    render(<App source={source()} />);
    await screen.findByText((_, el) => el?.getAttribute("data-page") === "live", undefined, { timeout: 5000 });
    act(() => {
      seek(1e9);
      setSetting("lang", "fr");
    });
    const last = insights.at(-1);
    await waitFor(() => expect(screen.getAllByText(last.text.rendered.fr.casual).length).toBeGreaterThan(0));
    act(() => setSetting("lang", "en"));
  });
});

describe("Live stream source", () => {
  it("shows only pushed insights under a Live stream chip, then falls back to Replay on error", async () => {
    const listeners: Record<string, ((e: MessageEvent<string>) => void)[]> = {};
    const es: EventSourceLike = {
      addEventListener: (t, l) => (listeners[t] ??= []).push(l),
      onerror: null,
      close: () => {},
    };
    const emit = (t: string, data: string) => listeners[t]?.forEach((l) => l(new MessageEvent(t, { data })));
    window.location.hash = "#/live";
    render(<App source={new SseSource("./api", 30, source(), () => es)} />);
    await screen.findByText((_, el) => el?.getAttribute("data-page") === "live", undefined, { timeout: 5000 });
    const chip = () => document.querySelector("[data-source]") as HTMLElement;
    await waitFor(() => expect(chip().dataset.source).toBe("live"));
    expect(chip().textContent).toMatch(/Live stream/);
    expect(document.querySelectorAll("article[data-insight-id]").length).toBe(0);
    act(() => {
      emit("insight", JSON.stringify(insights[0]));
      emit("insight", JSON.stringify(insights[1]));
    });
    await waitFor(() => expect(document.querySelectorAll("article[data-insight-id]").length).toBe(2));
    expect(useReplay.getState().limit).toBe(insights[1].clock.start_sec);
    act(() => seek(1e9));
    expect(useReplay.getState().t).toBe(insights[1].clock.start_sec);
    act(() => es.onerror?.(new Event("error")));
    await waitFor(() => expect(chip().dataset.source).toBe("replay"));
    expect(useSource.getState().fellBack).toBe(true);
    act(() => seek(1e9));
    await waitFor(() => expect(document.querySelectorAll("article[data-insight-id]").length).toBe(insights.length));
    act(() => useSource.setState({ mode: "replay", fellBack: false }));
  });
});

describe("Home", () => {
  it("is the default route; the sections read the data and keep their numbers in every language", async () => {
    window.location.hash = "";
    render(<App source={source()} matches={new MatchFiles("./matches/", disk)} />);
    const page = await screen.findByText((_, el) => el?.getAttribute("data-page") === "home", undefined, {
      timeout: 5000,
    });
    // the trust strip: three statements, the revised count read from the ledger
    const trust = await waitFor(() => {
      const el = page.querySelector("[data-home='trust']");
      if (!el) throw new Error("not yet");
      return el;
    });
    expect(trust.querySelectorAll("[data-proof]").length).toBe(3);
    const revised = () => page.querySelector("[data-proof='revised']")?.textContent ?? "";
    expect(revised()).toContain(String(ui.ledger.counts.revised));
    // the showcase strip: the score from the match file
    const show = JSON.parse(readFileSync(join(DATA, "matches", "m_showcase.json"), "utf8"));
    const strip = await waitFor(() => {
      const el = page.querySelector("[data-home='showcase'] [data-score]");
      if (!el) throw new Error("not yet");
      return el;
    });
    expect(strip.textContent).toContain(`${show.header.home.goals}–${show.header.away.goals}`);
    expect(page.querySelectorAll("[data-timeline] [data-mark]").length).toBe(
      show.turning_points.filter((tp: { kind: string }) => ["goal", "card", "sub"].includes(tp.kind)).length,
    );
    // three key insights, a mix of revised and passed
    const statuses = [...page.querySelectorAll("[data-home='insights'] article[data-status]")].map((a) =>
      a.getAttribute("data-status"),
    );
    expect(statuses).toHaveLength(3);
    expect(statuses).toContain("revised");
    expect(statuses.some((x) => x !== "revised")).toBe(true);
    const hero = page.querySelector("img[data-hero]") as HTMLImageElement;
    expect(hero.getAttribute("fetchpriority")).toBe("high");
    expect(hero.getAttribute("width")).toBe("1600");
    expect(hero.alt).not.toBe("");
    for (const img of page.querySelectorAll("img")) {
      expect(img.hasAttribute("alt"), img.outerHTML).toBe(true);
      expect(img.getAttribute("width") && img.getAttribute("height"), img.outerHTML).toBeTruthy();
    }
    act(() => setSetting("lang", "fr"));
    await waitFor(() => expect(page.querySelector("h1")?.textContent).toMatch(/données/));
    expect(revised()).toContain(String(ui.ledger.counts.revised));
    act(() => setSetting("lang", "en"));
    expect(page.querySelector("a[href='#/live']")).toBeTruthy();
    expect(page.querySelectorAll("[data-home='teams'] [data-team-badge]").length).toBe(5);
  });
});

describe("Tactical patterns on the pages", () => {
  it("Player Deck shows the starved-finisher chip, Team Board the signatures, Tech the catalogue", async () => {
    window.location.hash = "#/players";
    render(<App source={source()} />);
    const page = await screen.findByText((_, el) => el?.getAttribute("data-page") === "players", undefined, {
      timeout: 5000,
    });
    // the deck links every player to the Player Console, which carries the pattern chips
    const links = await waitFor(() => {
      const l = page.querySelectorAll("a[data-player]");
      expect(l.length).toBe(ui.players.length);
      return l;
    });
    const options = new Set([...links].map((a) => a.getAttribute("data-player")));
    const pid = Object.entries(ui.patterns.players as Record<string, { family: string }[]>).find(
      ([id, rows]) => options.has(id) && rows.some((r) => r.family === "pat_starved_finisher"),
    )![0];
    fireEvent.click(page.querySelector(`a[data-player='${pid}']`)!);
    const console_ = await screen.findByText((_, el) => el?.getAttribute("data-page") === "player", undefined, {
      timeout: 5000,
    });
    await waitFor(() =>
      expect(
        console_.querySelector(`[data-player-patterns='${pid}'] [data-family='pat_starved_finisher']`),
      ).toBeTruthy(),
    );
    cleanup();

    // one Team Board per club now (#/teams is the grid); the board lists at most three signatures
    for (const [code, rows] of Object.entries(ui.patterns.signature as Record<string, { family: string }[]>)) {
      window.location.hash = `#/teams/${code}`;
      render(<App source={source()} />);
      const board = await screen.findByText((_, el) => el?.getAttribute("data-page") === "team-board", undefined, {
        timeout: 5000,
      });
      const box = await waitFor(() => board.querySelector(`[data-signature-patterns='${code}']`) as HTMLElement);
      expect(rows.length).toBeLessThanOrEqual(3);
      expect([...box.querySelectorAll("[data-family]")].map((e) => e.getAttribute("data-family"))).toEqual(
        rows.map((r) => r.family),
      );
      cleanup();
    }

    window.location.hash = "#/tech";
    render(<App source={source()} />);
    const tech = await screen.findByText((_, el) => el?.getAttribute("data-page") === "tech", undefined, {
      timeout: 5000,
    });
    const rows = await waitFor(() => {
      const r = tech.querySelectorAll("[data-table='patterns'] tbody tr");
      expect(r.length).toBe(ui.patterns.catalogue.length);
      return r;
    });
    const off = ui.patterns.catalogue
      .filter((r: { enabled: boolean }) => !r.enabled)
      .map((r: { family: string }) => r.family);
    for (const f of off) {
      const row = [...rows].find((r) => r.getAttribute("data-family") === f)!;
      expect(row.textContent).toMatch(/off in the stream/);
    }
  });
});
