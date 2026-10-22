// Hand-typed shapes of the engine's dashboard files (agents/dashboard_data.py, agents/run_match.py).
// The stream items and claim objects use the types generated from contracts/ (src/types/generated).
import type { IntermediateClaimObject } from "./generated/claim";
import type { TimedInsightOverlayStreamItem } from "./generated/insight";

export type Insight = TimedInsightOverlayStreamItem;
export type InsightType = Insight["insight_type"];
export type Claim = IntermediateClaimObject;

export const LANGS = ["en", "es", "fr"] as const;
export type Lang = (typeof LANGS)[number];
export type Tone = "analyst" | "casual";
/** language -> tone -> sentence, as the Narrative agent rendered it (number-guarded). */
export type Rendered = Record<string, { analyst?: string; casual?: string } | undefined>;
export type Confidence = "low" | "medium" | "high";

/** One verification attempt of a claim (out/claims.jsonl). */
export interface ClaimAttempt {
  claim: Claim;
  revision_of: string | null;
  strategy: string | null;
  trigger_clock: number;
}

// ---------- out/timeline.json ----------

export interface TeamRef {
  code: string;
  id: string;
  name: string;
}
export interface Goal {
  clock_sec: number;
  event_id: string;
  player_id: string;
  score_home: number;
  score_away: number;
  team: string;
}
export interface Period {
  period: number;
  start_sec: number;
  end_sec: number;
}
export interface Timeline {
  match_id: string;
  duration_sec: number;
  home: TeamRef;
  away: TeamRef;
  goals: Goal[];
  /** [clock_sec, momentum]: the engine's momentum per minute, home positive. */
  momentum: [number, number][];
  periods: Period[];
  players: Record<string, { name: string; shirt: string; team: string }>;
}

// ---------- out/ui.json ----------

export interface MetricRow {
  value: number | null;
  league: number | null;
  effect: number | null;
  unit: string;
  interval: [number, number] | null;
  confidence: Confidence | null;
  n: number;
}
export interface StyleLabel extends MetricRow {
  id: string;
  metric: string;
  label: string;
  direction: string;
  rule: string;
}
export interface LaneShare {
  share: number | null;
  league: number | null;
  effect: number | null;
  confidence: Confidence | null;
  n: number;
}
export interface LaneCompletion {
  rate: number | null;
  league: number | null;
  effect: number | null;
  confidence: Confidence | null;
  attempted: number;
}
export interface SoftLane {
  lane: string;
  rate: number;
  league: number;
  effect: number;
  confidence: Confidence;
  attempted: number;
}
export interface TeamProfile {
  id: string;
  code: string;
  name: string;
  labels: StyleLabel[];
  entry_lanes: Record<string, LaneShare>;
  entry_lanes_conceded: Record<string, LaneShare>;
  completion_conceded: Record<string, LaneCompletion>;
  soft_lane: SoftLane | null;
  matches: number;
}
export interface H2HLane {
  attack_share: number | null;
  league_share: number | null;
  attack_pp: number | null;
  completion: number | null;
  league_completion: number | null;
  completion_pp: number | null;
  mismatch_pp: number | null;
  confidence: Confidence | null;
}
export interface H2HClaim {
  status: string;
  rule_ids: string[];
  template_key: string;
  confidence: Confidence | null;
  evidence_event_ids: string[];
  text: Record<string, { analyst: string; casual: string }> | null;
}
export interface HeadToHead {
  attacker: string;
  defender: string;
  n_attack: number;
  n_concede: number;
  lanes: Record<string, H2HLane>;
  top: string | null;
  claim: H2HClaim | null;
}
export interface TeamsSection {
  teams: TeamProfile[];
  head_to_head: HeadToHead[];
  lanes: string[];
  matches: number;
  dataset: string;
}

export interface PlayerCheck {
  metric: string;
  rule: string;
  fired: boolean;
  status: string;
  rule_ids: string[];
  amount: number;
  evidence_event_ids: string[];
  text: Record<string, { analyst: string; casual: string }>;
  original?: Record<string, { analyst: string; casual: string }>;
  context_note?: string | null;
  params?: Record<string, number>;
}
export interface PlayerRow {
  id: string;
  name: string;
  team: string;
  position: string;
  involvement: number;
  team_share: number | null;
  passes: number;
  pass_completion: number | null;
  forward_passes: number;
  wide_share: number | null;
  pass_quality_ratio: number | null;
  chances: number;
  chances_open_play: number;
  chances_set_piece: number;
  checks: PlayerCheck[];
}

export type LedgerOutcome = "passed" | "passed_with_context" | "revised" | "blocked";
export interface LedgerRow {
  insight_id: string | null;
  claim_id: string;
  clock_sec: number;
  insight_type: InsightType | null;
  metric: string;
  team: string | null;
  outcome: LedgerOutcome;
  rule_ids: string[];
  attempts: number;
  statuses: string[];
  template_keys: string[];
  context_note: string | null;
}
export interface Ledger {
  rows: LedgerRow[];
  counts: Record<LedgerOutcome, number>;
  total: number;
  attempts: number;
  blocked_attempts: number;
}
export interface Rewrite {
  rule_ids: string[];
  revision_hint: Record<string, string[]>;
  original: Record<string, { analyst: string; casual: string }>;
  original_template: string;
  final_template: string;
  strategy: string | null;
}
export interface EvidenceRow {
  event_id: string;
  match_id: string;
  clock_sec: number;
  period: number;
  team: string;
  player: string | null;
  related_player: string | null;
  event_type: string;
  outcome: string | null;
  x: number | null;
  y: number | null;
  x_end: number | null;
  y_end: number | null;
}
export interface ReportTable {
  heading: string;
  headers: string[];
  rows: string[][];
}
export interface Report {
  file: string;
  title: string;
  intro: string;
  tables: ReportTable[];
  notes: { heading: string; text: string }[];
}
/** [clock_sec, x, y, team code]: an on-ball event location in the acting team's attacking frame. */
export type TrackEntry = [number, number, number, string];

export interface UiData {
  match_id: string;
  season: { dataset: string; matches: number; teams: number };
  teams: TeamsSection;
  players: PlayerRow[];
  ledger: Ledger;
  rewrites: Record<string, Rewrite>;
  reasons: Record<string, Record<string, string>>;
  evidence: Record<string, EvidenceRow>;
  measured: Report[];
  track: TrackEntry[];
}

/** Everything the pages read, loaded once by a StreamSource. */
export interface MatchBundle {
  insights: Insight[];
  attempts: Record<string, ClaimAttempt>;
  timeline: Timeline;
  ui: UiData;
}
