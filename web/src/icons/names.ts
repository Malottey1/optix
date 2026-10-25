// The 56 icon names: the 54 of the Optix icon sheet plus fixtures and search, drawn later for the nav
// in the same style; by group (docs/icons.md).
export const ICON_GROUPS = {
  navigation: ["live", "home", "fixtures", "teams", "players", "tech", "settings", "search"],
  playback: ["play", "pause", "restart", "speed", "scrub"],
  events: [
    "pass",
    "shot",
    "goal",
    "tackle",
    "interception",
    "pressure",
    "possession-change",
    "foul",
    "yellow-card",
    "red-card",
    "substitution",
    "corner",
  ],
  lanes: ["lane-left-flank", "lane-left-half-space", "lane-centre", "lane-right-half-space", "lane-right-flank"],
  verdicts: [
    "verdict-passed",
    "verdict-revised",
    "verdict-blocked",
    "verdict-context",
    "evidence-drawer",
    "trace-to-data",
  ],
  styles: [
    "style-high-press",
    "style-low-block",
    "style-patient-possession",
    "style-direct-play",
    "style-wing-play",
    "style-central-play",
  ],
  metrics: [
    "metric-xg",
    "metric-xt",
    "metric-field-tilt",
    "metric-momentum",
    "metric-territorial-stress",
    "metric-rhythm",
  ],
  patterns: [
    "pattern-bait-switch",
    "pattern-cutback",
    "pattern-flank-isolation",
    "pattern-elastic-low-block",
    "pattern-counter-press",
    "pattern-rest-defence",
    "pattern-starved-finisher",
    "pattern-tactical-fouling",
  ],
} as const;

export type IconGroup = keyof typeof ICON_GROUPS;
export type IconName = (typeof ICON_GROUPS)[IconGroup][number];
export const ICON_NAMES = Object.values(ICON_GROUPS).flat() as IconName[];
