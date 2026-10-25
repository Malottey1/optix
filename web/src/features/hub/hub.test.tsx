import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { setSetting } from "../../state/settings";
import { capCards, layoutMarks } from "./parts";
import { isPattern, panelMemory, panelPage } from "./InsightsPanel";
import { facingPos, lineupMarkers } from "../../charts/MatchLineups";
import { eventLog, parseMatchFile, xiRows } from "../../data/matches";
import { shownMatchups } from "./MatchupStrips";
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
        // below 1100 px (jsdom has no matchMedia) the insights panel sits under the scoreline
        withMatchup
          ? ["insights", "turning", "lineups", "heat", "matchup", "log"]
          : ["insights", "turning", "lineups", "heat", "log"],
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

  it("a replay link (?t=) opens the log at the first logged event at or after that clock", async () => {
    const file = parseMatchFile(JSON.parse(readFileSync(join(DATA, "matches", "m_002.json"), "utf8")), "m_002");
    const log = eventLog(file);
    const at = log[Math.floor(log.length / 2)]!.clock_sec - 1;
    const want = log.find((e) => e.clock_sec >= at)!;
    window.location.hash = `#/match/m_002?t=${at}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("hub");
    const list = (await waitFor(() => p.querySelector("[role='listbox']"))) as HTMLElement;
    expect(p.querySelector("[data-event-log]")!.getAttribute("data-at-clock")).toBe(String(at));
    expect(list.getAttribute("aria-activedescendant")).toBe(`ev-${want.event_id}`);
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

describe("Match Hub insights panel and lineups", () => {
  it("pages the cards five at a time, the pager reads Page k of n, and a tab change is remembered in memory", async () => {
    window.location.hash = "#/match/m_001";
    render(<App source={source()} matches={matches()} />);
    const p = await page("hub");
    const panel = await waitFor(() => p.querySelector("#insights") as HTMLElement);
    const list = panel.querySelector<HTMLElement>("[data-scroll-region]")!;
    expect(list.tabIndex).toBe(0);
    expect(list.getAttribute("aria-labelledby")).toBe("tab-insights");
    const label = () => panel.querySelector("[data-page-label]")!.textContent;
    const cards = () => list.querySelectorAll("article[data-insight-id]").length;
    expect(cards()).toBeLessThanOrEqual(5);
    expect(label()).toMatch(/^Page 1 of \d+$/);
    const next = [...panel.querySelectorAll("button")].find((b) => /Next/.test(b.textContent ?? ""))!;
    const before = list.querySelector("article")!.getAttribute("data-insight-id");
    fireEvent.click(next);
    expect(label()).toMatch(/^Page 2 of /);
    expect(list.querySelector("article")!.getAttribute("data-insight-id")).not.toBe(before);
    fireEvent.click(panel.querySelector("[data-tab='patterns']")!);
    expect(panelMemory.tab).toBe("patterns");
    expect(label()).toMatch(/^Page 1 of /);
    expect([...list.querySelectorAll("article")].every((a) => a.getAttribute("data-type") === "tactical_pattern")).toBe(
      true,
    );
    fireEvent.click(panel.querySelector("[data-tab='insights']")!);
  });

  it("panelPage splits tabs, filters by family and clamps the page", () => {
    const f = parseMatchFile(JSON.parse(readFileSync(join(DATA, "matches", "m_001.json"), "utf8")), "m_001");
    const cards = f.insights.map(
      (c) => ({ insight_type: c.type, payload: { family: (c as { family?: string }).family } }) as unknown as Insight,
    );
    const ins = panelPage(cards, "insights", "all", 5, 99);
    expect(ins.list.every((c) => !isPattern(c))).toBe(true);
    expect(ins.page).toBe(ins.pages - 1);
    expect(ins.shown.length).toBeLessThanOrEqual(5);
    const pats = panelPage(cards, "patterns", "all", 5, 0);
    expect(pats.list.length + ins.list.length).toBe(cards.length);
  });

  it("the facing pitch mirrors the away XI and no two nodes overlap; markers come from the turning points", () => {
    for (const id of ["m_001", "m_010", "m_025"]) {
      const f = parseMatchFile(JSON.parse(readFileSync(join(DATA, "matches", `${id}.json`), "utf8")), id);
      const pts = [
        ...xiRows(f, "home").map((r) => facingPos(r, "home", true)),
        ...xiRows(f, "away").map((r) => facingPos(r, "away", true)),
      ];
      expect(pts.length).toBe(22);
      for (let i = 0; i < pts.length; i++)
        for (let j = i + 1; j < pts.length; j++)
          expect(Math.hypot(pts[i]!.x - pts[j]!.x, pts[i]!.y - pts[j]!.y)).toBeGreaterThan(10);
      // home on the left half, away on the right half
      expect(xiRows(f, "home").every((r) => facingPos(r, "home", true).x < 52.5)).toBe(true);
      expect(xiRows(f, "away").every((r) => facingPos(r, "away", true).x > 52.5)).toBe(true);
      const mk = lineupMarkers(f, (k) => k);
      const goals = f.turning_points.filter((t) => t.kind === "goal").length;
      expect(
        Object.values(mk)
          .flat()
          .filter((m) => m.icon === "goal").length,
      ).toBe(goals);
    }
  });

  it("a lineup node opens the mini-profile sheet with the ledger link", async () => {
    window.location.hash = "#/match/m_001";
    render(<App source={source()} matches={matches()} />);
    const p = await page("hub");
    const node = await waitFor(() => p.querySelector<HTMLButtonElement>("[data-layout='stacked'] button[data-node]")!);
    const xi = p.querySelectorAll("[data-layout='stacked'] [data-xi='home'] button[data-node]");
    expect([...xi].filter((b) => (b as HTMLButtonElement).tabIndex === 0).length).toBe(1);
    fireEvent.click(node);
    const sheet = await waitFor(() => document.querySelector("#player-sheet") as HTMLElement);
    expect(sheet.querySelector(`a[data-ledger-link='${node.getAttribute("data-node")}']`)).toBeTruthy();
  });
});

describe("Matchup", () => {
  const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
  const rule = ui.teams.matchup_rule;
  it("shows a direction only at the display confidence, and the outlined lane passes the claim's own thresholds", () => {
    let fixtures = 0;
    for (const row of index.fixtures as { id: string }[]) {
      const f = parseMatchFile(JSON.parse(readFileSync(join(DATA, "matches", `${row.id}.json`), "utf8")), row.id);
      const shown = shownMatchups(f, ui.teams);
      if (shown.length) fixtures++;
      for (const { mu, h } of shown) {
        expect(rule.display_confidence).toContain(mu.confidence);
        const l = h.lanes[mu.metrics.lane]!;
        expect(l.attack_pp!).toBeGreaterThan(rule.min_attack_pp);
        expect(l.completion_pp!).toBeGreaterThan(rule.min_completion_pp);
        // the season row and the claim carry the same numbers
        expect([l.attack_share, l.league_share, l.completion, l.league_completion]).toEqual([
          mu.metrics.attack_share,
          mu.metrics.league_share,
          mu.metrics.concede_completion,
          mu.metrics.league_completion,
        ]);
      }
    }
    // the display rule keeps the section to well under 60% of fixtures
    expect(fixtures / index.fixtures.length).toBeLessThan(0.6);
  });

  it("outlines only the claim lane in both strips, and the sentence states the claim's numbers", async () => {
    window.location.hash = "#/match/m_001";
    render(<App source={source()} matches={matches()} />);
    const p = await page("hub");
    const box = await waitFor(() => p.querySelector("[data-matchup]") as HTMLElement);
    const f = parseMatchFile(JSON.parse(readFileSync(join(DATA, "matches", "m_001.json"), "utf8")), "m_001");
    const { mu } = shownMatchups(f, ui.teams)[0]!;
    for (const side of ["attack", "defence"]) {
      const outlines = [...box.querySelectorAll(`svg[data-strip='${side}'] [data-outline]`)];
      expect(outlines.map((o) => o.getAttribute("data-outline"))).toEqual([mu.metrics.lane]);
    }
    const nums = (box.querySelector("[data-matchup-sentence]")!.textContent!.match(/\d+(\.\d+)?/g) ?? []).map(Number);
    expect(nums).toEqual([
      mu.metrics.attack_share,
      mu.metrics.league_share,
      mu.metrics.concede_completion,
      mu.metrics.league_completion,
    ]);
  });
});
