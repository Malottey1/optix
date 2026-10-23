// name -> icon component. Every icon is a few paths, so the whole set is one small module
// (the bundle gate measures it; see docs/icons.md).
import type { IconName } from "./names";
import { LiveIcon } from "./glyphs/live";
import { HomeIcon } from "./glyphs/home";
import { TeamsIcon } from "./glyphs/teams";
import { PlayersIcon } from "./glyphs/players";
import { TechIcon } from "./glyphs/tech";
import { SettingsIcon } from "./glyphs/settings";
import { PlayIcon } from "./glyphs/play";
import { PauseIcon } from "./glyphs/pause";
import { RestartIcon } from "./glyphs/restart";
import { SpeedIcon } from "./glyphs/speed";
import { ScrubIcon } from "./glyphs/scrub";
import { PassIcon } from "./glyphs/pass";
import { ShotIcon } from "./glyphs/shot";
import { GoalIcon } from "./glyphs/goal";
import { TackleIcon } from "./glyphs/tackle";
import { InterceptionIcon } from "./glyphs/interception";
import { PressureIcon } from "./glyphs/pressure";
import { PossessionChangeIcon } from "./glyphs/possession-change";
import { FoulIcon } from "./glyphs/foul";
import { YellowCardIcon } from "./glyphs/yellow-card";
import { RedCardIcon } from "./glyphs/red-card";
import { SubstitutionIcon } from "./glyphs/substitution";
import { CornerIcon } from "./glyphs/corner";
import { LaneLeftFlankIcon } from "./glyphs/lane-left-flank";
import { LaneLeftHalfSpaceIcon } from "./glyphs/lane-left-half-space";
import { LaneCentreIcon } from "./glyphs/lane-centre";
import { LaneRightHalfSpaceIcon } from "./glyphs/lane-right-half-space";
import { LaneRightFlankIcon } from "./glyphs/lane-right-flank";
import { VerdictPassedIcon } from "./glyphs/verdict-passed";
import { VerdictRevisedIcon } from "./glyphs/verdict-revised";
import { VerdictBlockedIcon } from "./glyphs/verdict-blocked";
import { VerdictContextIcon } from "./glyphs/verdict-context";
import { EvidenceDrawerIcon } from "./glyphs/evidence-drawer";
import { TraceToDataIcon } from "./glyphs/trace-to-data";
import { StyleHighPressIcon } from "./glyphs/style-high-press";
import { StyleLowBlockIcon } from "./glyphs/style-low-block";
import { StylePatientPossessionIcon } from "./glyphs/style-patient-possession";
import { StyleDirectPlayIcon } from "./glyphs/style-direct-play";
import { StyleWingPlayIcon } from "./glyphs/style-wing-play";
import { StyleCentralPlayIcon } from "./glyphs/style-central-play";
import { MetricXgIcon } from "./glyphs/metric-xg";
import { MetricXtIcon } from "./glyphs/metric-xt";
import { MetricFieldTiltIcon } from "./glyphs/metric-field-tilt";
import { MetricMomentumIcon } from "./glyphs/metric-momentum";
import { MetricTerritorialStressIcon } from "./glyphs/metric-territorial-stress";
import { MetricRhythmIcon } from "./glyphs/metric-rhythm";
import { PatternBaitSwitchIcon } from "./glyphs/pattern-bait-switch";
import { PatternCutbackIcon } from "./glyphs/pattern-cutback";
import { PatternFlankIsolationIcon } from "./glyphs/pattern-flank-isolation";
import { PatternElasticLowBlockIcon } from "./glyphs/pattern-elastic-low-block";
import { PatternCounterPressIcon } from "./glyphs/pattern-counter-press";
import { PatternRestDefenceIcon } from "./glyphs/pattern-rest-defence";
import { PatternStarvedFinisherIcon } from "./glyphs/pattern-starved-finisher";
import { PatternTacticalFoulingIcon } from "./glyphs/pattern-tactical-fouling";

export const ICONS: Record<IconName, () => React.JSX.Element> = {
  live: LiveIcon,
  home: HomeIcon,
  teams: TeamsIcon,
  players: PlayersIcon,
  tech: TechIcon,
  settings: SettingsIcon,
  play: PlayIcon,
  pause: PauseIcon,
  restart: RestartIcon,
  speed: SpeedIcon,
  scrub: ScrubIcon,
  pass: PassIcon,
  shot: ShotIcon,
  goal: GoalIcon,
  tackle: TackleIcon,
  interception: InterceptionIcon,
  pressure: PressureIcon,
  "possession-change": PossessionChangeIcon,
  foul: FoulIcon,
  "yellow-card": YellowCardIcon,
  "red-card": RedCardIcon,
  substitution: SubstitutionIcon,
  corner: CornerIcon,
  "lane-left-flank": LaneLeftFlankIcon,
  "lane-left-half-space": LaneLeftHalfSpaceIcon,
  "lane-centre": LaneCentreIcon,
  "lane-right-half-space": LaneRightHalfSpaceIcon,
  "lane-right-flank": LaneRightFlankIcon,
  "verdict-passed": VerdictPassedIcon,
  "verdict-revised": VerdictRevisedIcon,
  "verdict-blocked": VerdictBlockedIcon,
  "verdict-context": VerdictContextIcon,
  "evidence-drawer": EvidenceDrawerIcon,
  "trace-to-data": TraceToDataIcon,
  "style-high-press": StyleHighPressIcon,
  "style-low-block": StyleLowBlockIcon,
  "style-patient-possession": StylePatientPossessionIcon,
  "style-direct-play": StyleDirectPlayIcon,
  "style-wing-play": StyleWingPlayIcon,
  "style-central-play": StyleCentralPlayIcon,
  "metric-xg": MetricXgIcon,
  "metric-xt": MetricXtIcon,
  "metric-field-tilt": MetricFieldTiltIcon,
  "metric-momentum": MetricMomentumIcon,
  "metric-territorial-stress": MetricTerritorialStressIcon,
  "metric-rhythm": MetricRhythmIcon,
  "pattern-bait-switch": PatternBaitSwitchIcon,
  "pattern-cutback": PatternCutbackIcon,
  "pattern-flank-isolation": PatternFlankIsolationIcon,
  "pattern-elastic-low-block": PatternElasticLowBlockIcon,
  "pattern-counter-press": PatternCounterPressIcon,
  "pattern-rest-defence": PatternRestDefenceIcon,
  "pattern-starved-finisher": PatternStarvedFinisherIcon,
  "pattern-tactical-fouling": PatternTacticalFoulingIcon,
};
