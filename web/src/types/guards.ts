// Small runtime shape guards for the data files. They fail loudly with the path of the first
// field that drifted, e.g. "ui.json: teams.teams[2].entry_lanes: expected object, got undefined",
// so a change in the engine's output is caught at load time instead of as a blank widget.
import type { ClaimAttempt, Insight, InsightType, MatchBundle, Timeline, UiData } from "./ui";

export class ShapeError extends Error {
  constructor(file: string, path: string, message: string) {
    super(`${file}: ${path}: ${message}`);
    this.name = "ShapeError";
  }
}

type Kind = "string" | "number" | "boolean" | "object" | "array" | "null";

const kindOf = (v: unknown): string => (v === null ? "null" : Array.isArray(v) ? "array" : typeof v);

class Checker {
  constructor(readonly file: string) {}

  is(v: unknown, path: string, ...kinds: Kind[]): void {
    const k = kindOf(v);
    if (!kinds.includes(k as Kind)) throw new ShapeError(this.file, path, `expected ${kinds.join(" or ")}, got ${k}`);
  }

  obj(v: unknown, path: string): Record<string, unknown> {
    this.is(v, path, "object");
    return v as Record<string, unknown>;
  }

  arr(v: unknown, path: string): unknown[] {
    this.is(v, path, "array");
    return v as unknown[];
  }

  fields(v: unknown, path: string, spec: Record<string, Kind | Kind[]>): Record<string, unknown> {
    const o = this.obj(v, path);
    for (const [k, kinds] of Object.entries(spec)) {
      this.is(o[k], `${path}.${k}`, ...(Array.isArray(kinds) ? kinds : [kinds]));
    }
    return o;
  }

  fail(path: string, message: string): never {
    throw new ShapeError(this.file, path, message);
  }
}

export const INSIGHT_TYPES: readonly InsightType[] = [
  "matchup_mismatch",
  "perimeter_lock",
  "threat_pass",
  "momentum_shift",
  "turning_point",
  "rhythm_wave",
  "volume_vs_value",
  "set_piece_inflation",
  "player_focus",
  "milestone",
  "red_card_segment",
  "pounce_sequence",
  "underperformance_stack",
  "recap_line",
  "tactical_pattern",
];

/** One line of insights.jsonl, checked against the required fields of contracts/insight.schema.json. */
export function parseInsight(raw: unknown, path = "insight"): Insight {
  const c = new Checker("insights.jsonl");
  const o = c.fields(raw, path, {
    insight_id: "string",
    match_id: "string",
    clock: "object",
    insight_type: "string",
    teams: "object",
    claim_id: "string",
    evidence_event_ids: "array",
    payload: "object",
    text: "object",
  });
  c.fields(o.clock, `${path}.clock`, { start_sec: "number", duration_sec: "number" });
  if (!INSIGHT_TYPES.includes(o.insight_type as InsightType))
    c.fail(`${path}.insight_type`, `unknown type ${String(o.insight_type)}`);
  c.fields(o.teams, `${path}.teams`, { primary: "string" });
  const ev = c.arr(o.evidence_event_ids, `${path}.evidence_event_ids`);
  if (!ev.length) c.fail(`${path}.evidence_event_ids`, "must list at least one event");
  ev.forEach((e, i) => c.is(e, `${path}.evidence_event_ids[${i}]`, "string"));
  const text = c.fields(o.text, `${path}.text`, { template_key: "string", params: "object", rendered: "object" });
  const en = c.obj((text.rendered as Record<string, unknown>).en, `${path}.text.rendered.en`);
  c.is(en.casual, `${path}.text.rendered.en.casual`, "string");
  const pts = (o.payload as Record<string, unknown>).points;
  if (pts !== undefined) {
    c.arr(pts, `${path}.payload.points`).forEach((p, i) =>
      c.fields(p, `${path}.payload.points[${i}]`, { event_id: "string", x: "number", y: "number" }),
    );
  }
  return raw as Insight;
}

export function parseAttempt(raw: unknown, path = "attempt"): ClaimAttempt {
  const c = new Checker("claims.jsonl");
  const o = c.fields(raw, path, { claim: "object", revision_of: ["string", "null"], trigger_clock: "number" });
  const claim = c.fields(o.claim, `${path}.claim`, {
    claim_id: "string",
    metric: "string",
    scope: "string",
    value: "object",
    verification: "object",
    template_key: "string",
    evidence_event_ids: "array",
  });
  c.fields(claim.verification, `${path}.claim.verification`, {
    status: "string",
    rule_ids: "array",
    attempt: "number",
  });
  return raw as ClaimAttempt;
}

export function parseTimeline(raw: unknown): Timeline {
  const c = new Checker("timeline.json");
  const o = c.fields(raw, "timeline", {
    match_id: "string",
    duration_sec: "number",
    home: "object",
    away: "object",
    goals: "array",
    momentum: "array",
    periods: "array",
    players: "object",
  });
  for (const side of ["home", "away"]) c.fields(o[side], `timeline.${side}`, { code: "string", name: "string" });
  (o.goals as unknown[]).forEach((g, i) =>
    c.fields(g, `timeline.goals[${i}]`, {
      clock_sec: "number",
      score_home: "number",
      score_away: "number",
      team: "string",
    }),
  );
  (o.momentum as unknown[]).forEach((m, i) => {
    const a = c.arr(m, `timeline.momentum[${i}]`);
    c.is(a[0], `timeline.momentum[${i}][0]`, "number");
    c.is(a[1], `timeline.momentum[${i}][1]`, "number");
  });
  (o.periods as unknown[]).forEach((p, i) =>
    c.fields(p, `timeline.periods[${i}]`, { period: "number", start_sec: "number", end_sec: "number" }),
  );
  return raw as Timeline;
}

export function parseUi(raw: unknown): UiData {
  const c = new Checker("ui.json");
  const o = c.fields(raw, "ui", {
    match_id: "string",
    season: "object",
    teams: "object",
    players: "array",
    ledger: "object",
    rewrites: "object",
    reasons: "object",
    evidence: "object",
    measured: "array",
    track: "array",
    visuals: "object",
    azure_status: "array",
    lineups: "object",
  });
  for (const [code, lu] of Object.entries(o.lineups as Record<string, unknown>)) {
    const l = c.fields(lu, `lineups.${code}`, { xi: "array", label: "string", matches: "number" });
    const xi = l.xi as unknown[];
    if (xi.length !== 11) c.fail(`lineups.${code}.xi`, `expected 11 players, got ${xi.length}`);
    xi.forEach((n, i) =>
      c.fields(n, `lineups.${code}.xi[${i}]`, {
        id: "string",
        shirt: "number",
        position: "string",
        line: "number",
        slot: "number",
        of: "number",
      }),
    );
  }
  const teams = c.fields(o.teams, "teams", {
    teams: "array",
    head_to_head: "array",
    lanes: "array",
    matches: "number",
  });
  (teams.teams as unknown[]).forEach((t, i) => {
    const p = `teams.teams[${i}]`;
    const tt = c.fields(t, p, {
      code: "string",
      name: "string",
      labels: "array",
      entry_lanes: "object",
      entry_lanes_conceded: "object",
      completion_conceded: "object",
      soft_lane: ["object", "null"],
      matches: "number",
    });
    (tt.labels as unknown[]).forEach((l, j) =>
      c.fields(l, `${p}.labels[${j}]`, {
        id: "string",
        label: "string",
        rule: "string",
        direction: "string",
        n: "number",
      }),
    );
    for (const lane of teams.lanes as string[])
      c.obj((tt.entry_lanes as Record<string, unknown>)[lane], `${p}.entry_lanes.${lane}`);
  });
  (teams.head_to_head as unknown[]).forEach((h, i) =>
    c.fields(h, `teams.head_to_head[${i}]`, {
      attacker: "string",
      defender: "string",
      lanes: "object",
      top: ["string", "null"],
      claim: ["object", "null"],
    }),
  );
  (o.players as unknown[]).forEach((p, i) =>
    c.fields(p, `players[${i}]`, {
      id: "string",
      name: "string",
      team: "string",
      involvement: "number",
      forward_passes: "number",
      chances: "number",
      checks: "array",
      shirt: "number",
      goals: "number",
      assists: "number",
      starts: "number",
    }),
  );
  const ledger = c.fields(o.ledger, "ledger", {
    rows: "array",
    counts: "object",
    total: "number",
    attempts: "number",
    blocked_attempts: "number",
  });
  (ledger.rows as unknown[]).forEach((r, i) =>
    c.fields(r, `ledger.rows[${i}]`, { claim_id: "string", clock_sec: "number", outcome: "string", rule_ids: "array" }),
  );
  for (const [id, rw] of Object.entries(o.rewrites as Record<string, unknown>)) {
    c.fields(rw, `rewrites.${id}`, { rule_ids: "array", original: "object", original_template: "string" });
  }
  c.obj((o.reasons as Record<string, unknown>).en, "reasons.en");
  (o.measured as unknown[]).forEach((r, i) =>
    c.fields(r, `measured[${i}]`, {
      file: "string",
      title: "string",
      intro: "string",
      tables: "array",
      notes: "array",
    }),
  );
  (o.azure_status as unknown[]).forEach((r, i) =>
    c.fields(r, `azure_status[${i}]`, {
      id: "string",
      name: "string",
      tech: "string",
      state: "string",
      live: "string",
      note: "string",
    }),
  );
  const vis = c.fields(o.visuals, "visuals", {
    shots: "array",
    league_hot_share: "number",
    stress: "object",
    rhythm: "array",
    states: "object",
    state_min_n: "number",
    routes: "object",
    zones: "object",
  });
  (vis.shots as unknown[]).forEach((s, i) => {
    const a = c.arr(s, `visuals.shots[${i}]`);
    if (a.length !== 9) c.fail(`visuals.shots[${i}]`, `expected 9 fields, got ${a.length}`);
    c.is(a[6], `visuals.shots[${i}][6]`, "number");
  });
  for (const [code, spells] of Object.entries(vis.stress as Record<string, unknown>)) {
    c.arr(spells, `visuals.stress.${code}`).forEach((s, i) => {
      const a = c.arr(s, `visuals.stress.${code}[${i}]`);
      a.forEach((x, j) => c.is(x, `visuals.stress.${code}[${i}][${j}]`, "number"));
    });
  }
  (vis.rhythm as unknown[]).forEach((r, i) => {
    const a = c.arr(r, `visuals.rhythm[${i}]`);
    a.forEach((x, j) => c.is(x, `visuals.rhythm[${i}][${j}]`, "number"));
  });
  for (const [code, st] of Object.entries(vis.states as Record<string, unknown>)) {
    for (const b of ["leading", "trailing"]) {
      const row = c.obj((st as Record<string, unknown>)[b], `visuals.states.${code}.${b}`);
      for (const m of ["field_tilt", "press_intensity"])
        c.fields(row[m], `visuals.states.${code}.${b}.${m}`, { value: ["number", "null"], n: "number" });
    }
  }
  for (const [pid, rows] of Object.entries(vis.routes as Record<string, unknown>)) {
    c.arr(rows, `visuals.routes.${pid}`).forEach((r, i) => {
      const a = c.arr(r, `visuals.routes.${pid}[${i}]`);
      if (!["fwd", "op", "sp"].includes(a[0] as string))
        c.fail(`visuals.routes.${pid}[${i}][0]`, `unknown kind ${String(a[0])}`);
    });
  }
  const track = o.track as unknown[];
  if (track.length) c.arr(track[0], "track[0]");
  return raw as UiData;
}

export function parseJsonl<T>(text: string, file: string, parse: (raw: unknown, path: string) => T): T[] {
  return text
    .split("\n")
    .map((l, i) => [l, i] as const)
    .filter(([l]) => l.trim())
    .map(([l, i]) => {
      let v: unknown;
      try {
        v = JSON.parse(l);
      } catch (e) {
        throw new ShapeError(file, `line ${i + 1}`, `not JSON (${(e as Error).message})`);
      }
      return parse(v, `line ${i + 1}`);
    });
}

/** Cross-file checks: every id a page links to must exist. */
export function checkBundle(b: MatchBundle): MatchBundle {
  for (const ins of b.insights) {
    if (!b.attempts[ins.claim_id])
      throw new ShapeError("claims.jsonl", ins.insight_id, `no attempt for claim ${ins.claim_id}`);
  }
  if (b.ui.match_id !== b.timeline.match_id) {
    throw new ShapeError("ui.json", "match_id", `${b.ui.match_id} does not match timeline ${b.timeline.match_id}`);
  }
  return b;
}
