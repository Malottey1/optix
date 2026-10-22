// V2 on the Live Center: each team's shots up to the playhead as xG blocks. The panel re-renders
// only when a shot is added (the selector returns the number of shots so far, not the clock).
import { Panel } from "../../components/ui/card";
import { ShotBlocks, ShotLegend } from "../../components/viz/ShotBlocks";
import { useData } from "../../data/context";
import { lastAtOrBefore } from "../../data/model";
import { clock } from "../../lib/format";
import { useReplay } from "../../state/replay";

export function LiveShots() {
  const m = useData();
  const tl = m.timeline;
  const all = m.ui.visuals.shots;
  const n = useReplay((s) => lastAtOrBefore(all, s.t, (x) => x[1]) + 1);
  const upto = n > 0 ? all[n - 1]![1] : 0;
  const shown = all.slice(0, n);
  return (
    <Panel
      id="live-shots"
      title="Shot quality"
      subtitle="Every shot so far; a block's area is its xG, so ten tiny blocks can weigh less than one big one."
    >
      <div className="grid grid-cols-2 gap-3">
        {[tl.home, tl.away].map((t, i) => (
          <div key={t.code} className="min-w-0" data-team={t.code}>
            <p className="mb-1.5 text-[12.5px] font-semibold text-ink-2">{t.code}</p>
            <ShotBlocks
              shots={shown.filter((s) => s[2] === t.code)}
              team={t.code}
              color={i === 0 ? "var(--home)" : "var(--away)"}
              periods={tl.periods}
              windowLabel={`up to ${clock(upto, tl.periods)}`}
              compact
            />
          </div>
        ))}
      </div>
      <ShotLegend color="var(--ink-2)" uid="live" />
    </Panel>
  );
}
