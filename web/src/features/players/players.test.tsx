import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "../../App";
import { MatchFiles } from "../../data/matches";
import { ReplaySource } from "../../data/ReplaySource";
import { setSetting } from "../../state/settings";
import type { PlayerRow } from "../../types/ui";
import { chanceRows, defPoints, parseTeamLists, passRows, shotsFacedRows } from "../../data/matches";
import { drawOrder } from "../../components/viz/PassMap";
import { chancesOf, playLink } from "./ChanceDrawer";
import { divergingValues } from "./PlayerConsole";
import { defenceRows, pointsByType, shotsByResult } from "./PositionPanels";
import { filterPlayers } from "./PlayerDeck";

const DATA = join(__dirname, "..", "..", "..", "public", "data");
const disk = async (url: string) => new Response(readFileSync(join(DATA, url.replace(/^\.\//, "")), "utf8"));
const source = () => new ReplaySource("./", disk);
const matches = () => new MatchFiles("./matches/", disk);
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
const players = ui.players as PlayerRow[];

const page = (name: string) =>
  screen.findByText((_, el) => el?.getAttribute("data-page") === name, undefined, { timeout: 8000 });
const need = <T,>(el: T | null): T => {
  if (!el) throw new Error("not rendered yet");
  return el;
};
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

  it("cards show only badge, name, position and two stats by position, within the card budget", async () => {
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
      // FW/MF goals and assists, DF tackles and interceptions, GK saves and save rate (from the profile)
      const d = row.profile?.defence;
      const k = row.profile?.keeper;
      const want =
        row.position === "DF" && d
          ? [String(d.tackles), String(d.interceptions)]
          : row.position === "GK" && k
            ? [String(k.saves), k.save_pct == null ? "–" : `${k.save_pct}%`]
            : [String(row.goals), String(row.assists)];
      expect([...c.querySelectorAll("dd")].map((d) => d.textContent)).toEqual(want);
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
    const box = await waitFor(() => need(p.querySelector(`[data-context='${check.rule}']`) as HTMLElement | null));
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

  it("shows the pass map (one line per listed pass), the touch map and pattern evidence", async () => {
    const [pid, rows] = Object.entries(
      ui.patterns.players as Record<string, { family: string; evidence: string[] }[]>,
    )[0]!;
    const pl = players.find((x) => x.id === pid)!;
    const want = passRows(lists(pl.team), pid);
    expect(want.length).toBeGreaterThan(0);
    window.location.hash = `#/players/${pid}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    const map = await waitFor(() => need(p.querySelector("[data-viz='pass-map']") as HTMLElement | null), {
      timeout: 8000,
    });
    // one line per pass in the list, key passes drawn last, every line 2 px with a start dot and a head
    const lines = [...map.querySelectorAll("[data-pass]")];
    expect(lines.map((g) => g.getAttribute("data-pass"))).toEqual(drawOrder(want).map((r) => r[0]));
    for (const g of lines) {
      expect(g.querySelector("line")!.getAttribute("stroke-width")).toBe("2");
      expect(g.querySelector("line")!.getAttribute("vector-effect")).toBe("non-scaling-stroke");
      expect(g.querySelectorAll("circle, polygon").length).toBe(2);
    }
    // the one caption line and the three-item legend; no old gradient legend or route toggle
    expect(map.querySelector("[data-role='routes-note']")!.textContent).toBe(
      `Each line is one completed pass. Showing the ${want.length} most progressive.`,
    );
    expect([...map.querySelectorAll("[data-legend-type]")].map((e) => e.getAttribute("data-legend-type"))).toEqual([
      "forward",
      "progressive",
      "key_pass",
    ]);
    expect(p.textContent).not.toMatch(/often central|rarely central|Show all routes/);
    await waitFor(() => expect(p.querySelectorAll("#touch rect[data-bin]").length).toBe(24 * 16), { timeout: 8000 });
    fireEvent.click(p.querySelector(`[data-family='${rows[0]!.family}'] button`)!);
    const sheet = await waitFor(() => need(document.querySelector("#player-evidence") as HTMLElement | null));
    expect([...sheet.querySelectorAll("[data-event-id]")].map((e) => e.getAttribute("data-event-id"))).toEqual(
      rows[0]!.evidence,
    );
  });

  it("the chances tab draws each chance like the drawer: gold set piece, blue open play, a ring on the shot", async () => {
    const pl = players
      .filter((x) => x.profile && x.profile.chances.set_piece > 0 && x.profile.chances.open_play > 0)
      .sort((a, b) => b.profile!.chances.total - a.profile!.chances.total)[0]!;
    const want = chanceRows(lists(pl.team), pl.id);
    window.location.hash = `#/players/${pl.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    await waitFor(() => need(p.querySelector("[data-viz='pass-map']")), { timeout: 8000 });
    fireEvent.click(screen.getByRole("radio", { name: "Chances created" }));
    const map = await waitFor(() => need(p.querySelector("[data-viz='chance-map']") as HTMLElement | null));
    const drawn = [...map.querySelectorAll("[data-chance]")];
    expect(drawn.map((g) => g.getAttribute("data-chance"))).toEqual(want.map((r) => r[0]));
    for (const [g, r] of drawn.map((g, i) => [g, want[i]!] as const)) {
      const colour = g.querySelector("line")!.getAttribute("stroke");
      expect(colour).toBe(r[4] === "open_play" ? "var(--chance-open-play)" : "var(--chance-set-piece)");
      expect(g.querySelector("[data-shot]")!.getAttribute("data-shot")).toBe(r[7] === "goal" ? "goal" : "other");
    }
    const legend = map.querySelector("[data-legend='chances']")!.textContent!;
    expect(legend).toContain(`Open-play chance (${pl.profile!.chances.open_play})`);
    expect(legend).toContain(`Set-piece chance (${pl.profile!.chances.set_piece})`);
    expect(legend).toContain("Resulting shot");
  });

  it("minutes are whole numbers; the context note reads in plain words", async () => {
    const pl = players.find((x) => x.profile && !Number.isInteger(x.profile.minutes))!;
    expect(pl.profile!.minutes_whole).toBe(Math.floor(pl.profile!.minutes + 0.5));
    window.location.hash = `#/players/${pl.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    const stats = p.querySelector("[data-console-stats]")!.textContent!;
    expect(stats).toContain(String(pl.profile!.minutes_whole));
    expect(stats).not.toContain(String(pl.profile!.minutes));
    expect(p.textContent).not.toMatch(/lets out/);
    const withCheck = players.find((x) => x.checks.some((c) => c.fired && c.original))!;
    cleanup();
    window.location.hash = `#/players/${withCheck.id}`;
    render(<App source={source()} matches={matches()} />);
    const q = await page("player");
    await waitFor(() => expect(q.textContent).toContain("What the plain total hides"));
  });

  it("no pattern: a one-line note, and the position panels fill the right column", async () => {
    const withPat = new Set(Object.keys(ui.patterns.players));
    const df = players.find((x) => x.position === "DF" && x.profile?.defence && !withPat.has(x.id))!;
    window.location.hash = `#/players/${df.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    const right = p.querySelector("[data-right-column]")!;
    const note = right.querySelector("[data-patterns='none']")!;
    expect(note.textContent).toBe("No player pattern for this player.");
    expect(p.querySelector("section#patterns")).toBeNull();
    // the lead panel moves up; the map and passing panels sit side by side below
    expect(right.querySelector("[data-position-panels='DF'] #defence")).toBeTruthy();
    expect(right.querySelector("#defence-map, #passing")).toBeNull();
    expect(p.querySelector("#defence-map")).toBeTruthy();
    expect(p.querySelector("#passing")).toBeTruthy();
    cleanup();
    // with a pattern the card stays and the panels sit full width below
    const pid = Object.keys(ui.patterns.players).find((id) => players.find((x) => x.id === id)?.position === "DF");
    if (pid) {
      window.location.hash = `#/players/${pid}`;
      render(<App source={source()} matches={matches()} />);
      const q = await page("player");
      expect(q.querySelector("section#patterns")).toBeTruthy();
      expect(q.querySelector("[data-right-column] [data-position-panels]")).toBeNull();
      expect(q.querySelector("[data-position-panels='DF']")).toBeTruthy();
    }
  }, 15000);

  it("console strings follow the language", async () => {
    window.location.hash = `#/players/${players[0]!.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    act(() => setSetting("lang", "fr"));
    await waitFor(() => expect(p.textContent).toMatch(/Carte des touches/));
    expect(p.textContent).not.toMatch(/Touch map|Passing routes/);
    act(() => setSetting("lang", "en"));
  });

  const lists = (code: string) =>
    parseTeamLists(JSON.parse(readFileSync(join(DATA, "matches", `players-${code.toLowerCase()}.json`), "utf8")), code);
  const busiest = (pos: string) =>
    players.filter((p) => p.position === pos).sort((a, b) => (b.profile?.minutes ?? 0) - (a.profile?.minutes ?? 0))[0]!;

  it("defender panels: rates from the profile, map points match the counts", async () => {
    const df = busiest("DF");
    const rows = defenceRows(df, ui.profiles);
    expect(rows.map((r) => r.rate)).toEqual(ui.profiles.rates);
    for (const r of rows) expect(r.total).toBe(df.profile!.defence![r.rate]);
    const pts = pointsByType(defPoints(lists(df.team), df.id), 4);
    expect(pts.map((x) => x.length)).toEqual([
      df.profile!.defence!.tackles,
      df.profile!.defence!.interceptions,
      df.profile!.defence!.blocks,
      df.profile!.defence!.clearances,
    ]);
    window.location.hash = `#/players/${df.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    await waitFor(() => expect(p.querySelector("[data-viz='defensive-actions']")).toBeTruthy());
    expect(p.querySelectorAll("[data-def-rate]").length).toBe(rows.length);
    expect(p.querySelectorAll("[data-contrib-def]").length).toBe(1);
    expect(p.querySelector("[data-viz='chances-panel']")).toBeNull();
    const map = await waitFor(() => need(p.querySelector("[data-viz='defence-map']") as HTMLElement | null), {
      timeout: 8000,
    });
    const tackles = map.querySelector("[data-point-type='tackle']") as HTMLButtonElement;
    fireEvent.click(tackles);
    expect(tackles.getAttribute("aria-pressed")).toBe("false");
    expect(map.querySelector("[data-points='tackle']")).toBeNull();
    expect(p.querySelectorAll("[data-not-in-data]").length).toBeGreaterThan(0);
    for (const a of p.querySelectorAll("[data-not-in-data] a")) expect(a.getAttribute("href")).toBe("#/tech?s=limits");
  });

  it("goalkeeper panels: shots faced by result match the keeper profile", async () => {
    const gk = busiest("GK");
    const k = gk.profile!.keeper!;
    const shots = shotsFacedRows(lists(gk.team), gk.id);
    const by = shotsByResult(shots);
    expect(shots.length).toBe(k.shots_faced);
    expect(by.saved).toBe(k.saves);
    expect(by.goal).toBe(k.conceded);
    expect(by.goal + by.saved).toBe(k.on_target);
    window.location.hash = `#/players/${gk.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    const map = await waitFor(() => need(p.querySelector("[data-viz='shots-faced']") as HTMLElement | null), {
      timeout: 8000,
    });
    expect(Number(map.querySelector("[data-result='saved']")!.getAttribute("data-count"))).toBe(k.saves);
    expect(p.querySelector("[data-viz='keeper-figures']")!.textContent).toContain(String(k.xg_faced));
    expect(p.querySelector("[data-viz='keeper-distribution']")!.textContent).toContain(String(k.goal_kicks));
  });

  it("chance drawer: tiles, tabs, breakdown and play links to the match at its clock", async () => {
    const fw = players
      .filter((p) => p.position === "FW" || p.position === "MF")
      .sort((a, b) => (b.profile?.chances.total ?? 0) - (a.profile?.chances.total ?? 0))[0]!;
    const c = fw.profile!.chances;
    const all = chanceRows(lists(fw.team), fw.id);
    expect(all.length).toBe(c.total);
    expect(chancesOf(all, "set").length).toBe(c.set_piece);
    expect(chancesOf(all, "open").length).toBe(c.open_play);
    expect(playLink(all[0]!)).toBe(`/match/${all[0]![0].replace(/_e\d+$/, "")}?t=${all[0]![1]}`);
    window.location.hash = `#/players/${fw.id}`;
    render(<App source={source()} matches={matches()} />);
    const p = await page("player");
    fireEvent.click(await waitFor(() => need(p.querySelector("[data-open-chances]") as HTMLElement | null)));
    const sheet = await waitFor(
      () => need(document.querySelector("#chance-evidence [data-chance-drawer]") as HTMLElement | null),
      {
        timeout: 8000,
      },
    );
    expect(sheet.querySelectorAll("[data-chance-row]").length).toBe(c.total);
    expect(sheet.querySelector("[data-breakdown='corner'] dd")!.textContent).toBe(String(c.kinds.corner));
    fireEvent.click(screen.getByRole("radio", { name: "From set pieces" }));
    await waitFor(() => expect(sheet.querySelectorAll("[data-chance-row]").length).toBe(c.set_piece));
    expect(sheet.querySelectorAll("[data-chance-pitch] [data-chance]").length).toBe(c.set_piece);
    // the table shows no coordinates outside View data
    const table = sheet.querySelector("[data-chance-table]")!;
    for (const tr of table.querySelectorAll("tbody tr")) expect(tr.querySelectorAll("td").length).toBe(6);
    expect([...table.querySelectorAll("th")].map((h) => h.textContent)).not.toContain("x0");
  });
});
