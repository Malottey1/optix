// The engine's momentum, one value per minute (home positive), drawn up to the clock. d3 is used
// for scales and the path only; the chart is plain SVG. The curve re-renders once per match minute
// and the playhead moves through a ref.
import { scaleLinear } from "d3-scale";
import { area, curveMonotoneX, line } from "d3-shape";
import { memo, useMemo, useRef } from "react";
import { TeamDot } from "../../components/ui/badge";
import { Panel } from "../../components/ui/card";
import { useData } from "../../data/context";
import { clock, num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { useReplayFrame } from "../../state/replay";
import { useMomentumAt } from "./Scoreboard";

const W = 320;
const H = 96;
const MID = H / 2;

const Curve = memo(function Curve({ upto }: { upto: number }) {
  const m = useData();
  const tl = m.timeline;
  const x = useMemo(() => scaleLinear().domain([0, tl.duration_sec]).range([0, W]), [tl.duration_sec]);
  const y = useMemo(
    () =>
      scaleLinear()
        .domain([-100, 100])
        .range([H - 4, 4]),
    [],
  );
  const pts = tl.momentum.filter(([s]) => s <= upto);
  const ar = area<[number, number]>()
    .x((d) => x(d[0]))
    .y0(MID)
    .y1((d) => y(d[1]))
    .curve(curveMonotoneX);
  const ln = line<[number, number]>()
    .x((d) => x(d[0]))
    .y((d) => y(d[1]))
    .curve(curveMonotoneX);
  const a = pts.length > 1 ? (ar(pts) ?? "") : "";
  const l = pts.length > 1 ? (ln(pts) ?? "") : "";
  return (
    <g>
      {a && <path d={a} fill="var(--home)" opacity="0.32" clipPath="url(#mom-top)" />}
      {a && <path d={a} fill="var(--away)" opacity="0.32" clipPath="url(#mom-bot)" />}
      {l && (
        <path
          d={l}
          fill="none"
          stroke="var(--ink-2)"
          strokeWidth="1.4"
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
        />
      )}
      {pts.map(([s, v]) => (
        <circle key={s} data-minute-sec={s} data-value={v} cx={x(s)} cy={y(v)} r="0" />
      ))}
    </g>
  );
});

export function MomentumChart({ className }: { className?: string }) {
  const m = useData();
  const tl = m.timeline;
  const [sec] = useMomentumAt();
  const head = useRef<SVGLineElement>(null);
  useReplayFrame(
    (s) => {
      const px = ((Math.min(s.t, tl.duration_sec) / (tl.duration_sec || 1)) * W).toFixed(1);
      head.current?.setAttribute("x1", px);
      head.current?.setAttribute("x2", px);
    },
    [tl.duration_sec],
  );
  const X = (s: number) => (s / (tl.duration_sec || 1)) * W;
  return (
    <svg
      id="momentum-chart"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={className ?? "block h-24 w-full"}
      aria-hidden="true"
    >
      <defs>
        <clipPath id="mom-top">
          <rect x="0" y="0" width={W} height={MID} />
        </clipPath>
        <clipPath id="mom-bot">
          <rect x="0" y={MID} width={W} height={MID} />
        </clipPath>
      </defs>
      <rect x="0" y="0" width={W} height={MID} fill="var(--home-soft)" opacity="0.25" />
      <rect x="0" y={MID} width={W} height={MID} fill="var(--away-soft)" opacity="0.25" />
      <line
        x1="0"
        x2={W}
        y1={MID}
        y2={MID}
        stroke="var(--line-strong)"
        strokeWidth="1"
        vectorEffect="non-scaling-stroke"
      />
      {tl.periods.slice(1).map((p) => (
        <line
          key={p.period}
          x1={X(p.start_sec)}
          x2={X(p.start_sec)}
          y1="0"
          y2={H}
          stroke="var(--line-strong)"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
          strokeDasharray="3 3"
        />
      ))}
      <Curve upto={sec} />
      {tl.goals.map((g) => (
        <line
          key={g.event_id}
          data-event-id={g.event_id}
          x1={X(g.clock_sec)}
          x2={X(g.clock_sec)}
          y1={m.sideOf(g.team) === "home" ? 0 : H - 10}
          y2={m.sideOf(g.team) === "home" ? 10 : H}
          stroke={m.sideOf(g.team) === "home" ? "var(--home)" : "var(--away)"}
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
        />
      ))}
      <line ref={head} y1="0" y2={H} stroke="var(--accent)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function Momentum() {
  const m = useData();
  const { t, lang } = useT();
  const tl = m.timeline;
  const [, v] = useMomentumAt();
  const lead = v > 0 ? tl.home.code : v < 0 ? tl.away.code : null;
  const p2 = tl.periods[1];
  return (
    <Panel id="momentum" title={t("momentum")} subtitle={t("momentum_note")}>
      <div className="flex items-end justify-between gap-3">
        <div className="display text-[40px] font-bold leading-none text-ink" data-testid="momentum-value">
          {num(Math.abs(v), lang)}
        </div>
        <div className="pb-1 text-right text-[13px] font-semibold text-ink-2">
          {lead ? (
            <span className="inline-flex items-center gap-1.5">
              <TeamDot side={v > 0 ? "home" : "away"} />
              {lead} {t("pulling")}
            </span>
          ) : (
            t("level")
          )}
        </div>
      </div>
      <div className="mt-3 overflow-hidden rounded-lg border border-line">
        <MomentumChart />
      </div>
      <div className="mt-1.5 flex justify-between text-[11.5px] text-ink-3">
        <span className="num">{clock(0)}</span>
        {p2 && <span className="num">{clock(p2.start_sec, tl.periods)}</span>}
        <span className="num">{clock(tl.duration_sec, tl.periods)}</span>
      </div>
    </Panel>
  );
}
