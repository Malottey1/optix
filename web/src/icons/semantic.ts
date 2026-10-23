// Which icon stands for which thing in the data: insight types and claim metrics, lanes (attacker's
// view, engine/zones.py), event types and style labels. docs/icons-plan.md has the same tables.
import type { IconName } from "./names";

export const LANE_ICON: Record<string, IconName> = {
  left_flank: "lane-left-flank",
  left_half_space: "lane-left-half-space",
  center: "lane-centre",
  right_half_space: "lane-right-half-space",
  right_flank: "lane-right-flank",
};
export const laneIcon = (lane: string | null | undefined): IconName => LANE_ICON[lane ?? ""] ?? "lane-centre";

const METRIC_ICON: Record<string, IconName> = {
  xg: "metric-xg",
  xt_added: "metric-xt",
  field_tilt: "metric-field-tilt",
  momentum: "metric-momentum",
  rhythm_index: "metric-rhythm",
  ppda: "pressure",
  forward_passes: "pass",
  chances_created: "pass",
  milestone_count: "trace-to-data",
};

const TYPE_ICON: Record<string, IconName> = {
  perimeter_lock: "metric-field-tilt",
  threat_pass: "metric-xt",
  momentum_shift: "metric-momentum",
  turning_point: "metric-momentum",
  rhythm_wave: "metric-rhythm",
  volume_vs_value: "pass",
  set_piece_inflation: "corner",
  player_focus: "players",
};

/** Icon of an insight card: the lane for matchups, the type where it has one, else the claim's metric. */
export function insightIcon(type: string, metric?: string | null, lane?: string | null): IconName {
  if (type === "matchup_mismatch") return laneIcon(lane);
  return TYPE_ICON[type] ?? METRIC_ICON[metric ?? ""] ?? "evidence-drawer";
}

const EVENT_ICON: Record<string, IconName> = {
  pass: "pass",
  shot: "shot",
  tackle: "tackle",
  interception: "interception",
  pressure: "pressure",
  foul: "foul",
  possession_change: "possession-change",
  ball_recovery: "possession-change",
  substitution: "substitution",
  save: "goal",
};

/** Icon of an event type, or null when the sheet has none (carry, duel, block, clearance, ...). */
export function eventIcon(type: string, outcome?: string | null): IconName | null {
  if (type === "card") return outcome === "red" || outcome === "second_yellow" ? "red-card" : "yellow-card";
  if (type === "shot" && outcome === "goal") return "goal";
  return EVENT_ICON[type] ?? null;
}

/** Icon of a Team Board style label (engine/style_labels.py) by its direction against the league. */
export function styleLabelIcon(id: string, direction: string): IconName {
  switch (id) {
    case "tempo":
      return "metric-rhythm";
    case "press":
      return direction === "above" ? "style-high-press" : "pressure";
    case "directness":
      return direction === "above" ? "style-direct-play" : direction === "below" ? "style-patient-possession" : "pass";
    case "territory":
      return direction === "below" ? "style-low-block" : "metric-field-tilt";
    case "counter":
      return "possession-change";
    default:
      return "verdict-context";
  }
}

/** Icon for the lane a team attacks from most: wing play on a flank, central play in the centre. */
export function attackLaneIcon(lane: string): IconName {
  if (lane === "left_flank" || lane === "right_flank") return "style-wing-play";
  if (lane === "center") return "style-central-play";
  return laneIcon(lane);
}
