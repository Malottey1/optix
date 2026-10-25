// The fixture index and the per-match recap files (python -m agents.match_export, copied to
// public/data/matches/ by npm run data). Loaded lazily, one match at a time, each through a shape
// guard; decoded here into the shapes the existing widgets read (Insight, evidence rows). Nothing is
// computed: the decoding only restores ids and names the export compacted.
import type { FixtureIndex } from "../types/generated/fixtures";
import type { Attempt, Card, MatchFile, TurningPoint } from "../types/generated/match";
import { ShapeError } from "../types/guards";
import type { EvidenceRow, Insight } from "../types/ui";

export type { Attempt, Card, FixtureIndex, MatchFile, TurningPoint };
export type Fixture = FixtureIndex["fixtures"][number];

export const SHOWCASE_ID = "m_showcase";
const POINT_KEYS = ["event_id", "kind", "value", "x", "y", "x_end", "y_end"] as const;

type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

const kind = (v: unknown) => (v === null ? "null" : Array.isArray(v) ? "array" : typeof v);

function need(file: string, o: Record<string, unknown>, path: string, spec: Record<string, string>) {
  for (const [k, want] of Object.entries(spec)) {
    const got = kind(o[k]);
    if (!want.split("|").includes(got)) throw new ShapeError(file, `${path}.${k}`, `expected ${want}, got ${got}`);
  }
}

export function parseFixtures(raw: unknown): FixtureIndex {
  const f = "matches/index.json";
  if (kind(raw) !== "object") throw new ShapeError(f, "index", `expected object, got ${kind(raw)}`);
  const o = raw as Record<string, unknown>;
  need(f, o, "index", { dataset: "string", teams: "object", heat: "object", fixtures: "array" });
  (o.fixtures as unknown[]).forEach((r, i) => {
    if (kind(r) !== "object") throw new ShapeError(f, `fixtures[${i}]`, "expected object");
    need(f, r as Record<string, unknown>, `fixtures[${i}]`, {
      id: "string",
      status: "string",
      matchweek: "number",
      home: "string",
      away: "string",
      score: "array",
      insights: "number",
      patterns: "number",
      matchup: "boolean",
    });
  });
  return raw as FixtureIndex;
}

export function parseMatchFile(raw: unknown, id: string): MatchFile {
  const f = `matches/${id}.json`;
  if (kind(raw) !== "object") throw new ShapeError(f, "match", `expected object, got ${kind(raw)}`);
  const o = raw as Record<string, unknown>;
  need(f, o, "match", {
    match_id: "string",
    status: "string",
    stream: "string",
    header: "object",
    periods: "array",
    turning_points: "array",
    insights: "array",
    claims: "array",
    heat: "object",
    events: "object",
    evidence: "object",
    players: "object",
  });
  if (o.match_id !== id) throw new ShapeError(f, "match.match_id", `expected ${id}, got ${String(o.match_id)}`);
  const heat = o.heat as Record<string, unknown>;
  need(f, heat, "heat", { cols: "number", rows: "number", x_edges: "array", y_edges: "array", teams: "object" });
  const cells = (heat.cols as number) * (heat.rows as number);
  for (const [code, halves] of Object.entries(heat.teams as Record<string, unknown>)) {
    (halves as unknown[]).forEach((b, h) => {
      if (!Array.isArray(b) || b.length !== cells)
        throw new ShapeError(f, `heat.teams.${code}[${h}]`, `expected ${cells} bins`);
    });
  }
  const claims = new Set((o.claims as Attempt[]).map((c) => c.claim_id));
  (o.insights as Card[]).forEach((c, i) => {
    if (!claims.has(c.claim)) throw new ShapeError(f, `insights[${i}]`, `no attempt for claim ${c.claim}`);
  });
  return raw as MatchFile;
}

/** Full event id from the file's compact form (an event number of this match, or a full id). */
export const expandEid = (matchId: string, v: number | string): string =>
  typeof v === "number" ? `${matchId}_e${String(v).padStart(5, "0")}` : v;

/** A recap card back in the insights.jsonl shape (agents/match_export.py expand_insight). */
export function expandCard(file: MatchFile, c: Card): Insight {
  const id = file.match_id;
  const attempt = [...file.claims].reverse().find((a) => a.claim_id === c.claim)!;
  const payload = { ...(c.payload as Record<string, unknown>) };
  if (Array.isArray(payload.points))
    payload.points = (payload.points as unknown[][]).map((p) =>
      Object.fromEntries(
        POINT_KEYS.map((k, j) => [k, k === "event_id" ? expandEid(id, p[j] as number | string) : p[j]]),
      ),
    );
  return {
    claim_id: c.claim,
    clock: { duration_sec: c.d, emitted_latency_ms: null, start_sec: c.t },
    context_chip: c.chip,
    evidence_event_ids: attempt.evidence.map((e) => expandEid(id, e)),
    insight_id: c.id,
    insight_type: c.type,
    match_id: id,
    payload,
    player_ids: c.players,
    teams: { primary: c.teams[0], secondary: c.teams[1] },
    text: c.text,
    verification_status: c.status,
  } as unknown as Insight;
}

export interface LogEvent {
  event_id: string;
  clock_sec: number;
  team: string | null;
  player_id: string | null;
  event_type: string;
  outcome: string | null;
  related_player_id: string | null;
}

/** The compact event log as rows (types and outcomes decoded from their index tables). */
export function eventLog(file: MatchFile): LogEvent[] {
  const ev = file.events;
  return ev.rows.map((r) => {
    const [eid, clock, team, pid, t, o, rel] = r as [
      number | string,
      number,
      string | null,
      string | null,
      number,
      number | null,
      string | null,
    ];
    return {
      event_id: expandEid(file.match_id, eid),
      clock_sec: clock,
      team,
      player_id: pid,
      event_type: ev.types[t]!,
      outcome: o === null ? null : ev.outcomes[o]!,
      related_player_id: rel,
    };
  });
}

/** Evidence rows for the drawer (EvidenceRow shape): this match's log plus rows from other matches. */
export function evidenceRows(file: MatchFile): Record<string, EvidenceRow> {
  const name = (p: string | null) => (p && file.players[p] ? String(file.players[p]![0]) : null);
  const out: Record<string, EvidenceRow> = {};
  const period = (t: number) => file.periods.find((p) => t >= p.start_sec && t <= p.end_sec)?.period ?? 1;
  const row = (e: LogEvent, match: string): EvidenceRow =>
    ({
      event_id: e.event_id,
      match_id: match,
      clock_sec: e.clock_sec,
      period: match === file.match_id ? period(e.clock_sec) : null,
      team: e.team,
      player: name(e.player_id),
      related_player: name(e.related_player_id),
      event_type: e.event_type,
      outcome: e.outcome,
      x: null,
      y: null,
      x_end: null,
      y_end: null,
    }) as unknown as EvidenceRow;
  for (const e of eventLog(file)) out[e.event_id] = row(e, file.match_id);
  for (const r of file.evidence.rows as unknown[][]) {
    const [match, eid, clock, team, pid, type, outcome, rel] = r as [
      string,
      string,
      number,
      string | null,
      string | null,
      string,
      string | null,
      string | null,
    ];
    out[eid] = row(
      { event_id: eid, clock_sec: clock, team, player_id: pid, event_type: type, outcome, related_player_id: rel },
      match,
    );
  }
  return out;
}

export class MatchFiles {
  private index?: Promise<FixtureIndex>;
  private files = new Map<string, Promise<MatchFile>>();

  constructor(
    private readonly base = "./data/matches/",
    private readonly fetchImpl: Fetch = (i, init) => fetch(i, init),
  ) {}

  private async json(name: string): Promise<unknown> {
    const r = await this.fetchImpl(this.base + name, { cache: "no-cache" });
    if (!r.ok) throw new Error(`matches/${name}: HTTP ${r.status}`);
    return r.json();
  }

  fixtures(): Promise<FixtureIndex> {
    this.index ??= this.json("index.json").then(parseFixtures);
    return this.index;
  }

  /** One match file; only the last few stay cached, so a long browse holds little memory. */
  match(id: string): Promise<MatchFile> {
    if (!/^m_[a-z0-9_]+$/.test(id)) return Promise.reject(new Error(`unknown match ${id}`));
    let p = this.files.get(id);
    if (!p) {
      p = this.json(`${id}.json`).then((raw) => parseMatchFile(raw, id));
      this.files.set(id, p);
      while (this.files.size > 4) this.files.delete(this.files.keys().next().value!);
    }
    return p;
  }
}

export const matchFiles = new MatchFiles();
