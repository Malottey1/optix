// The TypeScript twin against the Python golden cases (tests/fixtures/personalize_golden.json,
// written by python -m tools.personalize_golden from engine/personalize.py): the same profile must
// select the same insight ids in the same order, and return the very same objects.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { CONFIG, FAN_CAP, involves, personalize, type Personalizable, type Profile } from "./personalize";

const ROOT = join(__dirname, "..", "..", "..");
const golden = JSON.parse(readFileSync(join(ROOT, "tests", "fixtures", "personalize_golden.json"), "utf8")) as {
  stream: Personalizable[];
  involved: Record<string, string[]>;
  cases: { profile: Profile; ids: string[] }[];
};
const full = readFileSync(join(ROOT, "web", "public", "data", "insights.jsonl"), "utf8")
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l) as Personalizable & { text: unknown; payload: unknown });

describe("personalize (TypeScript twin)", () => {
  it("reads the shared config", () => {
    const disk = JSON.parse(readFileSync(join(ROOT, "contracts", "personalization.json"), "utf8"));
    expect(CONFIG).toEqual(disk);
    expect(FAN_CAP).toBe(5);
  });

  it.each(golden.cases.map((c) => [JSON.stringify(c.profile), c] as const))("selects the Python ids for %s", (_, c) => {
    expect(personalize(golden.stream, c.profile, golden.involved).map((i) => i.insight_id)).toEqual(c.ids);
    // on the full stream objects too, and every output is an input object (no copies, no edits)
    const before = JSON.stringify(full);
    const out = personalize(full, c.profile, golden.involved);
    expect(out.map((i) => i.insight_id)).toEqual(c.ids);
    expect(out.every((o) => full.includes(o))).toBe(true);
    expect(JSON.stringify(full)).toBe(before);
    expect(personalize(full, c.profile, golden.involved)).toEqual(out);
  });

  it("an empty profile is the stream itself; a followed player matches evidence events too", () => {
    expect(personalize(full, {})).toEqual(full);
    expect(personalize(full, null)).toEqual(full);
    const ins = golden.stream.find((i) =>
      (i.evidence_event_ids ?? []).some((e) => golden.involved[e]?.includes("NTG_10")),
    )!;
    expect(involves(ins, "NTG_10", golden.involved)).toBe(true);
    expect(involves({ ...ins, player_ids: [], evidence_event_ids: [] }, "NTG_10", golden.involved)).toBe(false);
  });
});
