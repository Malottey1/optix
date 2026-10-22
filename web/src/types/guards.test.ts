import { describe, expect, it } from "vitest";
import { parseInsight, parseJsonl, parseUi, ShapeError } from "./guards";

const insight = {
  insight_id: "ins_0001",
  match_id: "m",
  clock: { start_sec: 6, duration_sec: 15 },
  insight_type: "threat_pass",
  teams: { primary: "AUR" },
  claim_id: "c1",
  evidence_event_ids: ["e1"],
  payload: { points: [{ event_id: "e1", x: 1, y: 2 }] },
  text: { template_key: "k", params: {}, rendered: { en: { casual: "x", analyst: "y" } } },
};

describe("shape guards", () => {
  it("accepts an insight that follows the contract", () => {
    expect(parseInsight(insight).insight_id).toBe("ins_0001");
  });

  it("names the first field that drifted", () => {
    const bad = { ...insight, clock: { start_sec: "6", duration_sec: 15 } };
    expect(() => parseInsight(bad)).toThrow(ShapeError);
    expect(() => parseInsight(bad)).toThrow("insights.jsonl: insight.clock.start_sec: expected number, got string");
    expect(() => parseInsight({ ...insight, insight_type: "prediction" })).toThrow(/unknown type/);
    expect(() => parseInsight({ ...insight, evidence_event_ids: [] })).toThrow(/at least one event/);
  });

  it("reports the line of a broken JSONL row", () => {
    expect(() => parseJsonl(`${JSON.stringify(insight)}\n{oops`, "insights.jsonl", parseInsight)).toThrow(
      /line 2: not JSON/,
    );
  });

  it("fails loudly when ui.json loses a section", () => {
    expect(() => parseUi({ match_id: "m" })).toThrow("ui.json: ui.season: expected object, got undefined");
  });
});
