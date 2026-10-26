// "Player so far" against counts recomputed in Python straight from data/showcase
// (tests/fixtures/player_so_far_golden.json, python -m tools.personalize_golden).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import type { ShotRow } from "../types/ui";
import { involvedFromEvents, parseEventFile, soFarFromEvents } from "./events";

const ROOT = join(__dirname, "..", "..", "..");
const DATA = join(ROOT, "web", "public", "data");
const file = parseEventFile(
  JSON.parse(readFileSync(join(DATA, "matches", "events-m_showcase.json"), "utf8")),
  "m_showcase",
);
const shots = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8")).visuals.shots as ShotRow[];
const golden = JSON.parse(readFileSync(join(ROOT, "tests", "fixtures", "player_so_far_golden.json"), "utf8")) as {
  cases: { player: string; clock: number; counts: Record<string, number> }[];
};

describe("player so far", () => {
  it.each(golden.cases.map((c) => [`${c.player}@${c.clock}`, c] as const))("matches the Python recount %s", (_, c) => {
    const got = soFarFromEvents(file, shots, c.player, c.clock);
    expect({ ...got, goals: undefined }).toEqual({ ...c.counts, goals: undefined });
  });

  it("maps every event id to its players", () => {
    const inv = involvedFromEvents(file);
    expect(Object.keys(inv).length).toBe(file.rows.length);
    expect(inv["m_showcase_e00402"]).toContain("AUR_09");
    expect(() => parseEventFile({ match_id: "m_001" }, "m_showcase")).toThrow();
  });
});
