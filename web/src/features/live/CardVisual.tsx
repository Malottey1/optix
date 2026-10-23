// The one visual an insight card carries, chosen by the claim behind it: the lane crosshairs for a
// matchup claim (V1, on the claim's own lane), the shot blocks for an xG claim (V2, exactly the
// shots in the claim's window and team) and the rhythm strip for a rhythm claim (V6, the payload's
// own series), and for a tactical pattern its evidence as arrows or a route of event nodes (the
// deep block: the other side's shot blocks in its window). Other cards point at the Focus Pitch.
import { MismatchCrosshairs } from "../../components/viz/MismatchCrosshairs";
import { PatternRoute } from "../../components/viz/PatternRoute";
import { ShotBlocks } from "../../components/viz/ShotBlocks";
import { useData } from "../../data/context";
import { clock } from "../../lib/format";
import { shotsIn } from "../../lib/viz";
import type { Insight } from "../../types/ui";
import { RhythmMini } from "./Flow";
import { statusOf } from "./shared";

export function CardVisual({ ins }: { ins: Insight }) {
  const m = useData();
  const final = m.chain(ins.claim_id).at(-1)?.claim;
  if (!final) return null;
  const blocked = statusOf(m, ins) === "blocked";
  if (ins.insight_type === "matchup_mismatch") {
    const att = ins.teams.primary;
    const dfn = ins.teams.secondary;
    const h = m.ui.teams.head_to_head.find((x) => x.attacker === att && x.defender === dfn);
    const defender = m.ui.teams.teams.find((t) => t.code === dfn);
    if (!h || !defender) return null;
    return (
      <div className="mt-3" data-card-visual="crosshairs">
        <MismatchCrosshairs
          h={h}
          defender={defender}
          lanes={m.ui.teams.lanes}
          compact
          claimLane={blocked ? null : (final.zone?.lane ?? null)}
          claimId={ins.claim_id}
        />
      </div>
    );
  }
  if (final.metric === "xg" && final.subject.kind === "team" && final.window) {
    const team = final.subject.team_code ?? ins.teams.primary;
    const w = final.window;
    const shots = shotsIn(m.ui.visuals.shots, team, w.from_sec, w.to_sec);
    return (
      <div className="mt-3" data-card-visual="shot-blocks">
        <ShotBlocks
          shots={shots}
          team={team}
          color={m.sideOf(team) === "home" ? "var(--home)" : "var(--away)"}
          periods={m.timeline.periods}
          windowLabel={`${clock(w.from_sec, m.timeline.periods)}–${clock(w.to_sec, m.timeline.periods)}`}
          compact
          claimId={ins.claim_id}
        />
      </div>
    );
  }
  if (ins.insight_type === "tactical_pattern") {
    const family = ins.payload.family ?? null;
    const w = ins.payload.window;
    if (family === "pat_elastic_low_block" && w && ins.teams.secondary) {
      // the shots the claim counts, in exactly its window: for the deep block itself, the other
      // side's shots; for a territory claim its rule rewrote, the territory holder's own shots
      const team = ins.payload.claim_metric === "pat_elastic_low_block" ? ins.teams.secondary : ins.teams.primary;
      return (
        <div className="mt-3" data-card-visual="shot-blocks">
          <ShotBlocks
            shots={shotsIn(m.ui.visuals.shots, team, w.from_sec, w.to_sec)}
            team={team}
            color={m.sideOf(team) === "home" ? "var(--home)" : "var(--away)"}
            periods={m.timeline.periods}
            windowLabel={`${clock(w.from_sec, m.timeline.periods)}–${clock(w.to_sec, m.timeline.periods)}`}
            compact
            claimId={ins.claim_id}
          />
        </div>
      );
    }
    return (
      <div className="mt-3" data-card-visual="pattern">
        <PatternRoute
          family={family}
          points={ins.payload.points ?? []}
          rows={m.ui.evidence}
          periods={m.timeline.periods}
          color={m.sideOf(ins.teams.primary) === "home" ? "var(--home)" : "var(--away)"}
          claimId={ins.claim_id}
        />
      </div>
    );
  }
  if (ins.insight_type === "rhythm_wave" && ins.payload.series?.length) {
    return (
      <div className="mt-3" data-card-visual="rhythm">
        <RhythmMini
          series={ins.payload.series}
          label="Possession changes per minute over the claim's window, oldest on the left"
        />
      </div>
    );
  }
  return null;
}
