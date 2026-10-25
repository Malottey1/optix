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
  /** The lane the claim object names (claim.zone.lane), attacker's frame. */
  lane: string;
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
  /** the lane claim's own thresholds (engine.matchup) and the hub's display-only confidence rule */
  matchup_rule: { min_attack_pp: number; min_completion_pp: number; display_confidence: string[] };
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
  /** the data's shirt field (players.csv) */
  shirt: number;
  /** season goals and assists (engine.metrics.goals / assists) and starts (lineups.csv) */
  goals: number;
  assists: number;
  starts: number;
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
  /** season profile (agents/player_profiles.py); absent for players with no minutes */
  profile?: PlayerProfile;
}

export type DefRate = "tackles" | "interceptions" | "blocks" | "clearances" | "fouls" | "contributions";
/** Outfield defensive actions. p90 / p100 / peer_pctl are null or absent below the minutes floor. */
export interface DefenceProfile {
  tackles: number;
  tackles_won: number;
  interceptions: number;
  blocks: number;
  clearances: number;
  clearances_head: number;
  fouls: number;
  pressures: number;
  aerials: number;
  aerials_won: number;
  contributions: number;
  entries_faced: number;
  p90: Record<DefRate, number> | null;
  p100: Record<DefRate, number> | null;
  peer_pctl?: Record<DefRate, number>;
}
export interface KeeperProfile {
  shots_faced: number;
  on_target: number;
  saves: number;
  conceded: number;
  xg_faced: number;
  save_pct: number | null;
  conceded_minus_xg: number;
  clean_sheets: number;
  matches: number;
  passes: number;
  pass_completion: number | null;
  long_share: number | null;
  long_m: number;
  goal_kicks: number;
}
export type ChanceKind = "corner" | "free_kick" | "throw_in" | "set_piece" | "open_play";
export interface ChanceSummary {
  total: number;
  set_piece: number;
  open_play: number;
  kinds: Record<ChanceKind, number>;
  xa: number;
  xa_per: number | null;
  progressive: number;
  forward: number;
}
export interface PlayerProfile {
  minutes: number;
  starts: number;
  sub_apps: number;
  sub_minutes: number;
  passing: {
    progressive: number;
    into_final_third: number;
    into_box: number;
    p90: { progressive: number; into_final_third: number; into_box: number } | null;
  };
  chances: ChanceSummary;
  defence?: DefenceProfile;
  keeper?: KeeperProfile;
}
export interface ProfilesMeta {
  min_minutes: number;
  long_pass_m: number;
  rates: DefRate[];
  contributions: string[];
  peers: Partial<Record<"DF" | "MF" | "FW", { n: number; avg_p90: Record<DefRate, number> | null }>>;
  league_chances: { total: number; xa_per: number | null };
}
/** Search index fixture: [id, matchweek, home code, away code, home goals, away goals]. */
export type FixtureEntry = [string, number, string, string, number, number];

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

// ---------- ui.json visuals: plain exports of engine metrics (agents/dashboard_data.visuals_section) ----------

/** [event_id, clock_sec, team, player_id, x, y, xg, result, shot_type], attacker's frame. */
export type ShotRow = [string, number, string, string, number, number, number, string, string];
/** [start_sec, end_sec, seconds, n_events]: one territorial-stress spell (engine.flow.territorial_stress). */
export type StressSpell = [number, number, number, number];
/** [period, minute, start_sec, possession_changes, tempo_var] (engine.flow.rhythm, per period). */
export type RhythmRow = [number, number, number, number, number];
/** [kind, from_zone, to_zone, passes, sum, hot]: kind fwd (sum = xT added), op / sp (sum = xA);
 * hot = passes ending in a high-threat central cell (the cells pass_quality_ratio counts). */
export type RouteKind = "fwd" | "op" | "sp";
export type RouteRow = [RouteKind, number, number, number, number, number];
export interface StateMetric {
  value: number | null;
  league: number | null;
  n: number;
  interval: [number, number] | null;
  confidence: Confidence | null;
}
export type StateName = "leading" | "trailing";
export type StateMetricName = "field_tilt" | "press_intensity";
export interface Visuals {
  shots: ShotRow[];
  /** League share of forward passes that end in a high-threat cell (pass_quality_ratio's 1×). */
  league_hot_share: number;
  stress: Record<string, StressSpell[]>;
  rhythm: RhythmRow[];
  states: Record<string, Record<StateName, Record<StateMetricName, StateMetric>>>;
  state_min_n: number;
  routes: Record<string, RouteRow[]>;
  zones: { thirds: string[]; lanes: string[]; third_x: [number, number] };
}

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
  visuals: Visuals;
  azure_status: AzureStatus[];
  patterns?: PatternsSection;
  lineups: Record<string, Lineup>;
  profiles: ProfilesMeta;
  fixtures: FixtureEntry[];
}

/** One node of the most-used starting XI: listed position and role, line (0 GK .. 3 FW) and slot
 * (left to right inside the line, of `of`). A list, not a tracked shape. */
export interface LineupNode {
  id: string;
  shirt: number;
  position: "GK" | "DF" | "MF" | "FW";
  role: string | null;
  starts: number;
  line: number;
  slot: number;
  of: number;
}
export interface Lineup {
  xi: LineupNode[];
  /** DF-MF-FW counts of the listed positions, e.g. "4-3-3" */
  label: string;
  matches: number;
  next_most_starts: number;
}

/** The tactical pattern catalogue and each team's signature patterns (agents/dashboard_data.py). */
export interface PatternsSection {
  catalogue: PatternEntry[];
  signature: Record<string, SignatureRow[]>;
  /** every family found for a team at least once, with signature = passes the signature rule */
  team_families?: Record<string, (SignatureRow & { signature: boolean })[]>;
  players: Record<
    string,
    { family: string; icon: string; matches: number; team_played: number; /** anchor event ids */ evidence: string[] }[]
  >;
  not_built: { id: string | null; name: string; icon: string | null; status: string }[];
  signature_rule: { min_share: number; min_lift: number };
}

export interface PatternEntry {
  family: string;
  icon: string;
  rule_ids: string[];
  /** false: an experimental family, left out of the stream (its context rule still runs) */
  enabled: boolean;
  status: "validated" | "experimental" | "not measured";
  recall_tuning?: number | null;
  recall_holdout?: number | null;
  fp_tuning?: number | null;
  fp_holdout?: number | null;
  recall_half?: number | null;
  cases_holdout?: number;
}

export interface SignatureRow {
  family: string;
  icon: string;
  matches: number;
  played: number;
  share: number;
  others_share: number;
  /** Wilson 95% interval of share, in % */
  interval?: [number | null, number | null];
}

/** One Microsoft / Azure component and its state, derived from repo facts (agents/azure_status.py). */
export interface AzureStatus {
  id: string;
  name: string;
  tech: string;
  state: "verified live" | "verified by tests" | "verified by CI build/lint" | "built, not verified live" | "not built";
  live: string;
  note: string;
}

/** Everything the pages read, loaded once by a StreamSource. */
export interface MatchBundle {
  insights: Insight[];
  attempts: Record<string, ClaimAttempt>;
  timeline: Timeline;
  ui: UiData;
}
