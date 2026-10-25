import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { parseInsight } from "../types/guards";
import { MatchFiles, eventLog, evidenceRows, expandCard, expandEid, parseFixtures, parseMatchFile } from "./matches";

const DIR = join(__dirname, "..", "..", "public", "data", "matches");
const read = (f: string) => JSON.parse(readFileSync(join(DIR, f), "utf-8"));

describe("match files", () => {
  const index = parseFixtures(read("index.json"));

  it("the index lists every file, showcase first, and only played matches", () => {
    const files = readdirSync(DIR).filter((f) => f.startsWith("m_"));
    expect(new Set(index.fixtures.map((f) => `${f.id}.json`))).toEqual(new Set(files));
    expect(index.fixtures[0]!.status).toBe("live");
    expect(index.fixtures.slice(1).every((f) => f.status === "final")).toBe(true);
  });

  it("every recap card decodes to a valid insight whose evidence the drawer can list", () => {
    for (const f of index.fixtures.slice(1, 8)) {
      const file = parseMatchFile(read(`${f.id}.json`), f.id);
      const rows = evidenceRows(file);
      for (const c of file.insights) {
        const ins = parseInsight(expandCard(file, c));
        expect(ins.match_id).toBe(f.id);
        for (const e of ins.evidence_event_ids) expect(rows[e], `${f.id} ${e}`).toBeDefined();
      }
      expect(eventLog(file).length).toBe(file.events.rows.length);
    }
  });

  it("restores compact event ids", () => {
    expect(expandEid("m_001", 936)).toBe("m_001_e00936");
    expect(expandEid("m_001", "m_002_e00004")).toBe("m_002_e00004");
  });

  it("rejects a file for another match and unknown ids", async () => {
    expect(() => parseMatchFile(read("m_001.json"), "m_002")).toThrow(/expected m_002/);
    const src = new MatchFiles("./", async () => new Response("{}"));
    await expect(src.match("../ui")).rejects.toThrow(/unknown match/);
  });
});
