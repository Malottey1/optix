// The TypeScript twin of engine/personalize.py, reading the same contracts/personalization.json.
// It filters, ranks and caps the verified stream and returns the very same insight objects: it never
// changes a number or a claim sentence. lib/personalize.test.ts runs the Python golden cases
// (tests/fixtures/personalize_golden.json) and asserts the same selected ids in the same order.
import CONFIG_JSON from "../../../contracts/personalization.json";

export type Mode = "fan" | "analyst";
export type MetricId = "momentum" | "xg" | "rhythm" | "stress";

export interface MetricConfig {
  icon: string;
  families: string[];
  series: "timeline.momentum" | "ui.visuals.shots" | "ui.visuals.rhythm" | "ui.visuals.stress";
  final: boolean;
}

export interface PersonalizationConfig {
  version: number;
  default_mode: Mode;
  modes: Record<Mode, { max_cards: number | null; page_size: number }>;
  fan_priority: string[];
  metrics: Record<MetricId, MetricConfig>;
  glossary: Record<string, string>;
  not_offered: Record<string, string>;
}

export const CONFIG = CONFIG_JSON as PersonalizationConfig;
export const MODES = Object.keys(CONFIG.modes) as Mode[];
export const METRICS = Object.keys(CONFIG.metrics) as MetricId[];
export const FAN_CAP = CONFIG.modes.fan.max_cards ?? Infinity;

/** The fields personalization reads (a full Insight has them all). */
export interface Personalizable {
  insight_id: string;
  insight_type: string;
  clock: { start_sec: number };
  teams: { primary: string };
  player_ids?: readonly string[] | null;
  evidence_event_ids?: readonly string[] | null;
}

export interface Profile {
  mode?: string | null;
  language?: string | null;
  clubs?: readonly string[] | string | null;
  players?: readonly string[] | string | null;
  metric?: string | null;
}

export type Involved = Readonly<Record<string, readonly string[]>>;

const list = (v: readonly string[] | string | null | undefined): string[] =>
  v == null ? [] : typeof v === "string" ? [v] : v.filter((x) => typeof x === "string");

export const isMode = (v: unknown): v is Mode => MODES.includes(v as Mode);
export const isMetric = (v: unknown): v is MetricId => METRICS.includes(v as MetricId);

/** True when `player` is on the insight (player_ids) or on one of its evidence events. */
export function involves(ins: Personalizable, player: string, involved: Involved = {}): boolean {
  if ((ins.player_ids ?? []).includes(player)) return true;
  return (ins.evidence_event_ids ?? []).some((e) => (involved[e] ?? []).includes(player));
}

type Key = (number | string | boolean)[];
const cmp = (a: Key, b: Key) => {
  for (let i = 0; i < a.length; i++) {
    const x = a[i]!;
    const y = b[i]!;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
};
const sortBy = <T,>(xs: readonly T[], key: (x: T) => Key) =>
  xs
    .map((x, i) => ({ x, k: [...key(x), i] }))
    .sort((a, b) => cmp(a.k, b.k))
    .map((r) => r.x);

export function fanRank(ins: Personalizable, clubs: readonly string[] = []): Key {
  const prio = CONFIG.fan_priority;
  const p = prio.indexOf(ins.insight_type);
  return [!clubs.includes(ins.teams.primary), p < 0 ? prio.length : p, ins.clock.start_sec, ins.insight_id];
}

/** The viewer's insights: the same objects as in `stream`, filtered, ranked and capped. */
export function personalize<T extends Personalizable>(
  stream: readonly T[],
  profile: Profile | null = null,
  involved: Involved = {},
): T[] {
  const p = profile ?? {};
  const mode = isMode(p.mode) ? p.mode : null;
  const metric = isMetric(p.metric) ? p.metric : null;
  const clubs = list(p.clubs);
  const players = list(p.players);
  let out = [...stream];
  if (players.length) out = out.filter((i) => involves(i, players[0]!, involved));
  if (metric) {
    const fams = CONFIG.metrics[metric].families;
    out = out.filter((i) => fams.includes(i.insight_type));
  }
  if (mode === "fan") out = sortBy(out, (i) => fanRank(i, clubs)).slice(0, FAN_CAP);
  else if (clubs.length) out = sortBy(out, (i) => [i.clock.start_sec, !clubs.includes(i.teams.primary)]);
  return out;
}
