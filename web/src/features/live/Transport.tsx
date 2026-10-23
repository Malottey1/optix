// Play / pause / restart, the match-clock scrubber (Radix Slider) with goal and insight markers,
// and the replay speed. The slider re-renders on a two-second grid of match time, not per frame.
import * as Slider from "@radix-ui/react-slider";
import { memo } from "react";
import { Icon } from "../../icons";
import { Button } from "../../components/ui/button";
import { Segmented } from "../../components/ui/segmented";
import { useData } from "../../data/context";
import { clock } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { SPEEDS, seek, setPlaying, setSpeed, useReplay, type Speed } from "../../state/replay";
import { statusOf } from "./shared";

const STATUS_FILL = {
  published: "var(--pass)",
  published_with_context: "var(--muted-accent)",
  revised: "var(--revise)",
  blocked: "var(--block)",
} as const;

/** Goal and insight ticks under the track (decorative: the feed and the clock carry the content). */
const Markers = memo(function Markers() {
  const m = useData();
  const d = m.timeline.duration_sec || 1;
  const x = (s: number) => `${(100 * s) / d}%`;
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-full">
      {m.timeline.periods.slice(1).map((p) => (
        <span
          key={p.period}
          className="absolute top-[3px] h-[22px] w-px bg-line-strong"
          style={{ left: x(p.start_sec) }}
        />
      ))}
      {m.insights.map((ins) => (
        <span
          key={ins.insight_id}
          data-insight-id={ins.insight_id}
          className="absolute bottom-0 h-[5px] w-[3px] -translate-x-1/2 rounded-full"
          style={{ left: x(ins.clock.start_sec), background: STATUS_FILL[statusOf(m, ins)] }}
        />
      ))}
      {m.timeline.goals.map((g) => (
        <span
          key={g.event_id}
          data-event-id={g.event_id}
          className="absolute top-0 h-[7px] w-[7px] -translate-x-1/2 rounded-full ring-2 ring-surface-1"
          style={{ left: x(g.clock_sec), background: m.sideOf(g.team) === "home" ? "var(--home)" : "var(--away)" }}
        />
      ))}
    </div>
  );
});

function Scrubber() {
  const m = useData();
  const { t } = useT();
  const tl = m.timeline;
  const sec = useReplay((s) => Math.floor(s.t / 2) * 2);
  return (
    <div className="relative min-w-0 flex-1 py-1">
      <Slider.Root
        className="relative flex h-7 w-full touch-none select-none items-center"
        min={0}
        max={tl.duration_sec}
        step={1}
        value={[sec]}
        onValueChange={([v]) => seek(v ?? 0)}
        aria-label={t("scrub")}
      >
        <Slider.Track className="relative h-[5px] grow overflow-hidden rounded-full bg-surface-4">
          <Slider.Range className="absolute h-full rounded-full bg-accent/80" />
        </Slider.Track>
        <Slider.Thumb
          aria-label={t("scrub")}
          aria-valuetext={clock(sec, tl.periods)}
          className="block h-[18px] w-[18px] rounded-full border-[3px] border-accent bg-ink shadow-[0_0_0_4px_rgba(55,230,168,0.15)] focus-visible:outline-2 focus-visible:outline-offset-2"
        />
      </Slider.Root>
      <Markers />
    </div>
  );
}

export function Transport() {
  const { t } = useT();
  const playing = useReplay((s) => s.playing);
  const speed = useReplay((s) => s.speed);
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-2xl border border-line bg-surface-1 px-3 py-2.5 elev-1 sm:flex-nowrap sm:px-4">
      <Button
        id="play"
        variant="primary"
        aria-pressed={playing}
        onClick={() => setPlaying(!playing)}
        className="min-w-[112px]"
      >
        <Icon name={playing ? "pause" : "play"} size={16} />
        <span>{playing ? t("pause") : t("play")}</span>
      </Button>
      <Button
        size="icon"
        aria-label={t("restart")}
        onClick={() => {
          setPlaying(false);
          seek(0);
        }}
      >
        <Icon name="restart" size={18} />
      </Button>
      <div className="order-last flex w-full items-center gap-2 sm:order-none sm:w-auto sm:flex-1">
        <Icon name="scrub" size={16} className="text-ink-3" />
        <div className="min-w-0 flex-1">
          <Scrubber />
        </div>
      </div>
      <div className="ml-auto flex items-center gap-2 sm:ml-0">
        <Icon name="speed" size={16} className="text-ink-3" />
        <Segmented<Speed>
          label={t("speed")}
          name="speed"
          value={speed}
          onChange={setSpeed}
          options={(Object.keys(SPEEDS) as Speed[]).map((k) => ({ value: k, label: t(k) }))}
        />
      </div>
    </div>
  );
}
