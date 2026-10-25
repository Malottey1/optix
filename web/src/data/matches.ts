// The fixture index and the per-match recap files (python -m agents.match_export, copied to
// public/data/matches/ by npm run data). Loaded lazily, one match at a time, each through a shape
// guard; decoded here into the shapes the existing widgets read (Insight, evidence rows). Nothing is
// computed: the decoding only restores ids and names the export compacted.
import type { FixtureIndex } from "../types/generated/fixtures";
import type { Attempt, Card, MatchFile, TurningPoint } from "../types/generated/match";
import type { TeamLists } from "../types/generated/players";
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
    lineups: "object",
  });
  for (const side of ["home", "away"] as const) {
    const l = (o.lineups as Record<string, unknown>)[side] as Record<string, unknown> | undefined;
    if (kind(l) !== "object") throw new ShapeError(f, `lineups.${side}`, "expected object");
    need(f, l!, `lineups.${side}`, { code: "string", xi: "array", label: "string" });
    (l!.xi as unknown[]).forEach((r, i) => {
      if (!Array.isArray(r) || r.length !== 6 || typeof r[0] !== "string" || typeof r[3] !== "number")
        throw new ShapeError(f, `lineups.${side}.xi[${i}]`, "expected [id, shirt, position, line, slot, of]");
    });
  }
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

/** players-heat-<code>.json: season touch maps of one team's players on the match files' grid. */
export interface PlayersHeat extends HeatGridShape {
  /** player id -> [bins] (one "half": the whole season), raw counts */
  players: Record<string, number[][]>;
}
interface HeatGridShape {
  cols: number;
  rows: number;
  x_edges: number[];
  y_edges: number[];
}

export function parsePlayersHeat(raw: unknown, code: string): PlayersHeat {
  const f = `matches/players-heat-${code.toLowerCase()}.json`;
  if (kind(raw) !== "object") throw new ShapeError(f, "heat", `expected object, got ${kind(raw)}`);
  const o = raw as Record<string, unknown>;
  need(f, o, "heat", { cols: "number", rows: "number", x_edges: "array", y_edges: "array", players: "object" });
  const cells = (o.cols as number) * (o.rows as number);
  for (const [pid, bins] of Object.entries(o.players as Record<string, unknown>))
    if (!Array.isArray(bins) || !Array.isArray(bins[0]) || bins[0].length !== cells)
      throw new ShapeError(f, `players.${pid}`, `expected [${cells} bins]`);
  return raw as PlayersHeat;
}

/** players-<code>.json (contracts/players.schema.json): the console's lazy lists for one team. */
export type { TeamLists };
export type ChanceRow = [
  string,
  number,
  number,
  number,
  "corner" | "free_kick" | "throw_in" | "set_piece" | "open_play",
  string,
  number,
  string | null,
  number,
  number,
  number,
  number,
  number,
  number,
];
export type ShotFacedRow = [string, number, number, number, "goal" | "saved" | "blocked" | "off_target", number];
export type DefPoint = [number, number, number];

export function parseTeamLists(raw: unknown, code: string): TeamLists {
  const f = `matches/players-${code.toLowerCase()}.json`;
  if (kind(raw) !== "object") throw new ShapeError(f, "lists", `expected object, got ${kind(raw)}`);
  const o = raw as Record<string, unknown>;
  need(f, o, "lists", { team: "string", point_types: "array", players: "object" });
  if (o.team !== code) throw new ShapeError(f, "lists.team", `expected ${code}, got ${String(o.team)}`);
  const rows: [string, number][] = [
    ["defence", 3],
    ["chances", 14],
    ["shots_faced", 6],
  ];
  for (const [pid, l] of Object.entries(o.players as Record<string, Record<string, unknown>>))
    for (const [k, n] of rows) {
      const v = l[k];
      if (v === undefined) continue;
      if (!Array.isArray(v) || v.some((r) => !Array.isArray(r) || r.length !== n))
        throw new ShapeError(f, `players.${pid}.${k}`, `expected rows of ${n}`);
    }
  return raw as TeamLists;
}

export const chanceRows = (l: TeamLists, pid: string) => (l.players[pid]?.chances ?? []) as unknown as ChanceRow[];
export const shotsFacedRows = (l: TeamLists, pid: string) =>
  (l.players[pid]?.shots_faced ?? []) as unknown as ShotFacedRow[];
export const defPoints = (l: TeamLists, pid: string) => (l.players[pid]?.defence ?? []) as unknown as DefPoint[];
/** The match id of a full event id ("m_012_e00306" -> "m_012"). */
export const matchOfEvent = (eid: string) => eid.replace(/_e\d+$/, "");

export class MatchFiles {
  private index?: Promise<FixtureIndex>;
  private files = new Map<string, Promise<MatchFile>>();
  private heat = new Map<string, Promise<PlayersHeat>>();
  private lists = new Map<string, Promise<TeamLists>>();

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

  /** One team's player touch maps (Player Console). */
  playersHeat(code: string): Promise<PlayersHeat> {
    if (!/^[A-Z]{3}$/.test(code)) return Promise.reject(new Error(`unknown team ${code}`));
    const key = `heat:${code}`;
    let p = this.heat.get(key);
    if (!p) {
      p = this.json(`players-heat-${code.toLowerCase()}.json`).then((raw) => parsePlayersHeat(raw, code));
      this.heat.set(key, p);
      while (this.heat.size > 2) this.heat.delete(this.heat.keys().next().value!);
    }
    return p;
  }

  /** One team's console lists: defensive points, key passes, shots faced (Player Console). */
  teamLists(code: string): Promise<TeamLists> {
    if (!/^[A-Z]{3}$/.test(code)) return Promise.reject(new Error(`unknown team ${code}`));
    let p = this.lists.get(code);
    if (!p) {
      p = this.json(`players-${code.toLowerCase()}.json`).then((raw) => parseTeamLists(raw, code));
      this.lists.set(code, p);
      while (this.lists.size > 2) this.lists.delete(this.lists.keys().next().value!);
    }
    return p;
  }
}

export const matchFiles = new MatchFiles();
