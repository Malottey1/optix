// Player focus data. The showcase's compact event file (events-m_showcase.json, agents/showcase_events.py)
// is fetched only when a viewer follows a player in the live hub. Every "Player so far" number is a
// count of those events up to the replay clock (xG: the sum of the player's shots in ui.json, rounded
// as the shot captions are); tests/fixtures/player_so_far_golden.json holds the same counts
// recomputed in Python straight from data/showcase. A played match's file has a thinned log (passes
// omitted), so its card counts shots, goals, cards and substitutions only.
import type { Involved } from "../lib/personalize";
import type { ShotRow } from "../types/ui";
import { eventLog, type MatchFile } from "./matches";

export interface EventFile {
  match_id: string;
  cols: string[];
  types: string[];
  outcomes: string[];
  players: string[];
  rows: (number | null)[][];
}

export function parseEventFile(raw: unknown, id: string): EventFile {
  const f = raw as EventFile;
  if (!f || f.match_id !== id || !Array.isArray(f.rows) || !Array.isArray(f.cols))
    throw new Error(`events-${id}.json: not an event file`);
  return f;
}

const col = (f: EventFile) => {
  const i = (k: string) => f.cols.indexOf(k);
  return {
    n: i("n"),
    clock: i("clock_sec"),
    type: i("type"),
    player: i("player"),
    related: i("related"),
    key: i("key"),
  };
};

/** Event id -> the ids of its player and related player. */
export function involvedFromEvents(f: EventFile): Record<string, string[]> {
  const c = col(f);
  const out: Record<string, string[]> = {};
  for (const r of f.rows) {
    const ids = [r[c.player], r[c.related]].filter((v): v is number => v != null).map((v) => f.players[v]!);
    out[`${f.match_id}_e${String(r[c.n]).padStart(5, "0")}`] = ids;
  }
  return out;
}

/** The same map from a played match's log and evidence rows. */
export function involvedFromLog(file: MatchFile): Involved {
  const out: Record<string, string[]> = {};
  for (const e of eventLog(file)) out[e.event_id] = [e.player_id, e.related_player_id].filter((p): p is string => !!p);
  for (const r of file.evidence.rows as unknown[][]) {
    const [, eid, , , pid, , , rel] = r as [
      string,
      string,
      number,
      string | null,
      string | null,
      string,
      unknown,
      string | null,
    ];
    out[eid] = [pid, rel].filter((p): p is string => !!p);
  }
  return out;
}

export interface SoFar {
  passes: number | null;
  shots: number;
  xg: number | null;
  key_passes: number | null;
  goals: number | null;
  cards: number;
  subs: number;
}

/** Counts for one player up to clock t from the showcase event file and the shots list. */
export function soFarFromEvents(f: EventFile, shots: readonly ShotRow[], pid: string, t: number): SoFar {
  const c = col(f);
  const pi = f.players.indexOf(pid);
  const type = (r: (number | null)[]) => f.types[r[c.type]!];
  const upto = f.rows.filter((r) => r[c.clock]! <= t);
  const mine = upto.filter((r) => r[c.player] === pi);
  const xg = shots.filter((s) => s[3] === pid && s[1] <= t).reduce((a, s) => a + s[6], 0);
  return {
    passes: mine.filter((r) => type(r) === "pass").length,
    shots: mine.filter((r) => type(r) === "shot").length,
    xg: Math.round(xg * 100) / 100,
    key_passes: mine.filter((r) => r[c.key] === 1).length,
    goals: null,
    cards: mine.filter((r) => type(r) === "card").length,
    subs: upto.filter((r) => type(r) === "substitution" && (r[c.player] === pi || r[c.related] === pi)).length,
  };
}

/** Counts for one player up to clock t from a played match's thinned log and turning points. */
export function soFarFromLog(file: MatchFile, pid: string, t: number): SoFar {
  const log = eventLog(file).filter((e) => e.clock_sec <= t);
  const mine = log.filter((e) => e.player_id === pid);
  return {
    passes: null,
    shots: mine.filter((e) => e.event_type === "shot").length,
    xg: null,
    key_passes: null,
    goals: file.turning_points.filter((p) => p.kind === "goal" && p.player_id === pid && p.clock_sec <= t).length,
    cards: mine.filter((e) => e.event_type === "card").length,
    subs: log.filter((e) => e.event_type === "substitution" && (e.player_id === pid || e.related_player_id === pid))
      .length,
  };
}
