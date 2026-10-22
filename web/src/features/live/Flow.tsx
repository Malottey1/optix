// V5 Territorial Stress gauges and V6 Rhythm Pulse, both from ui.json visuals (engine/flow.py).
// The drawings render once; the playhead, the fill levels and the value text move through refs on
// each replay frame (useReplayFrame), so a tick never re-renders the tree.
import { scaleLinear } from "d3-scale";
import { area, curveLinear } from "d3-shape";
import { memo, useMemo, useRef } from "react";
import { TeamDot } from "../../components/ui/badge";
import { Panel } from "../../components/ui/card";
import { VizFigure } from "../../components/viz/Figure";
import { useData } from "../../data/context";
import { clock, num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { stressAt } from "../../lib/viz";
import { useReplayFrame } from "../../state/replay";
import type { RhythmRow } from "../../types/ui";

/** Minutes and seconds of a duration, written like the match clock (traceable as mm:ss). */
const mmss = (sec: number) => {
  const s = Math.max(0, Math.round(sec));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

// ---------- V5 ----------

const GH = 150;

export function StressGauges() {
  const m = useData();
  const tl = m.timeline;
  const v = m.ui.visuals;
  const teams = [tl.home, tl.away];
  // Each team's gauge: the OPPONENT's spells in this team's half (engine.flow.territorial_stress).
  const spells = useMemo(
    () => teams.map((t) => v.stress[(t.code === tl.home.code ? tl.away : tl.home).code] ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [v, tl],
  );
  const totals = spells.map((s) => stressAt(s, Infinity));
  const max = Math.max(...totals, 1);
  const fills = useRef<(SVGRectElement | null)[]>([]);
  const texts = useRef<(HTMLElement | null)[]>([]);
  useReplayFrame(
    (s) => {
      spells.forEach((sp, i) => {
        const val = stressAt(sp, s.t);
        const h = (GH * val) / max;
        fills.current[i]?.setAttribute("y", String(GH - h));
        fills.current[i]?.setAttribute("height", String(h));
        const el = texts.current[i];
        if (el) {
          el.textContent = mmss(val);
          el.dataset.value = String(val);
        }
      });
    },
    [spells, max],
  );
  return (
    <Panel
      id="stress"
      title="Pinned in own half"
      subtitle="Time the opponent kept the ball in this team's half without losing it (the engine's territorial-stress spells), adding up as the match plays."
    >
      <VizFigure
        viz="stress-gauges"
        table={{
          caption: "Full-match time pinned in own half, per team",
          head: ["Team", "Time pinned (mm:ss)", "Spells"],
          rows: teams.map((t, i) => [t.code, mmss(totals[i]!), spells[i]!.length]),
        }}
      >
        <div className="grid grid-cols-2 gap-4">
          {teams.map((t, i) => {
            const side = i === 0 ? "home" : "away";
            return (
              <div key={t.code} className="flex items-end gap-3" data-team={t.code} data-gauge>
                <svg
                  viewBox={`0 0 36 ${GH + 2}`}
                  className="h-[132px] w-8 shrink-0"
                  role="img"
                  aria-label={`${t.code} pinned in own half, filling up to the playhead; full match ${mmss(totals[i]!)}`}
                >
                  <rect
                    x="4"
                    y="1"
                    width="28"
                    height={GH}
                    rx="14"
                    fill="var(--surface-3)"
                    stroke="var(--line-strong)"
                  />
                  <clipPath id={`gauge-clip-${t.code}`}>
                    <rect x="4" y="1" width="28" height={GH} rx="14" />
                  </clipPath>
                  <g clipPath={`url(#gauge-clip-${t.code})`}>
                    <rect
                      ref={(el) => {
                        fills.current[i] = el;
                      }}
                      x="4"
                      y={GH}
                      width="28"
                      height="0"
                      fill={side === "home" ? "var(--home)" : "var(--away)"}
                    />
                  </g>
                  {[0.25, 0.5, 0.75].map((f) => (
                    <line key={f} x1="4" x2="12" y1={1 + GH * f} y2={1 + GH * f} stroke="var(--bg)" strokeWidth="1.5" />
                  ))}
                </svg>
                <div className="min-w-0 pb-1">
                  <p className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink-2">
                    <TeamDot side={side} />
                    {t.code}
                  </p>
                  <p
                    className="display mt-1 text-[30px] font-bold leading-none text-ink"
                    data-role="stress-value"
                    ref={(el) => {
                      texts.current[i] = el;
                    }}
                  >
                    00:00
                  </p>
                  <p className="mt-1 text-[11.5px] text-ink-3">
                    of <span className="num">{mmss(totals[i]!)}</span> full match
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </VizFigure>
      <p className="mt-3 text-[12px] leading-relaxed text-ink-3">
        Event-based: a spell ends when the pinned team touches the ball. Territory is not threat; read it with the
        Perimeter Lock.
      </p>
    </Panel>
  );
}

// ---------- V6 ----------

const RW = 640;
const RH = 92;
const RMID = RH / 2;

type Pt = [number, number];

const Wave = memo(function Wave({ rows, x, amp }: { rows: RhythmRow[]; x: (s: number) => number; amp: number }) {
  const pts: Pt[] = rows.map((r) => [r[2] + 30, r[3]]);
  const ar = area<Pt>()
    .x((d) => x(d[0]))
    .y0((d) => RMID + d[1] * amp)
    .y1((d) => RMID - d[1] * amp)
    .curve(curveLinear);
  return <path d={ar(pts) ?? ""} />;
});

export function RhythmPulse() {
  const m = useData();
  const tl = m.timeline;
  const rows = m.ui.visuals.rhythm;
  const { lang } = useT();
  const peak = Math.max(...rows.map((r) => r[3]), 1);
  const x = useMemo(() => scaleLinear().domain([0, tl.duration_sec]).range([0, RW]), [tl.duration_sec]);
  const amp = (RMID - 6) / peak;
  const periods = [...new Set(rows.map((r) => r[0]))];
  const clip = useRef<SVGRectElement>(null);
  const head = useRef<SVGLineElement>(null);
  useReplayFrame(
    (s) => {
      const px = x(Math.min(s.t, tl.duration_sec)).toFixed(1);
      clip.current?.setAttribute("width", px);
      head.current?.setAttribute("x1", px);
      head.current?.setAttribute("x2", px);
    },
    [x, tl.duration_sec],
  );
  const peakRow = rows.find((r) => r[3] === peak);
  return (
    <Panel
      id="rhythm"
      title="Rhythm"
      subtitle="Possession changes per minute: tall, jagged peaks are transition chaos; a flat line is one side keeping the ball."
    >
      <VizFigure
        viz="rhythm-pulse"
        caption={
          <>
            Peak <b className="num font-semibold text-ink-2">{num(peak, lang)}</b> changes in a minute
            {peakRow ? (
              <>
                {" "}
                at <span className="num">{clock(peakRow[2], tl.periods)}</span>
              </>
            ) : null}
            . Height is the count, mirrored around the centre line.
          </>
        }
        table={{
          caption: "Possession changes per minute (engine.flow.rhythm)",
          head: ["Minute starting", "Possession changes"],
          rows: rows.map((r) => [clock(r[2], tl.periods), r[3]]),
        }}
      >
        <svg
          viewBox={`0 0 ${RW} ${RH}`}
          preserveAspectRatio="none"
          className="block h-[92px] w-full rounded-lg border border-line bg-surface-1"
          role="img"
          aria-label={`Rhythm: possession changes per minute through the match, peak ${peak} in a minute.`}
          data-peak={peak}
        >
          <defs>
            <clipPath id="rhythm-played">
              <rect ref={clip} x="0" y="0" width="0" height={RH} />
            </clipPath>
          </defs>
          <line x1="0" x2={RW} y1={RMID} y2={RMID} stroke="var(--line-strong)" vectorEffect="non-scaling-stroke" />
          <g fill="var(--muted-accent)" clipPath="url(#rhythm-played)">
            {periods.map((p) => (
              <Wave key={p} rows={rows.filter((r) => r[0] === p)} x={x} amp={amp} />
            ))}
          </g>
          {tl.periods.slice(1).map((p) => (
            <line
              key={p.period}
              x1={x(p.start_sec)}
              x2={x(p.start_sec)}
              y1="0"
              y2={RH}
              stroke="var(--line-strong)"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {rows.map((r) => (
            <circle
              key={`${r[0]}-${r[1]}`}
              data-minute-sec={r[2]}
              data-value={r[3]}
              cx={x(r[2] + 30)}
              cy={RMID}
              r="0"
            />
          ))}
          <line
            ref={head}
            x1="0"
            x2="0"
            y1="0"
            y2={RH}
            stroke="var(--accent)"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      </VizFigure>
    </Panel>
  );
}

/** A small rhythm strip for a rhythm card: the payload's own series (the claim's 15 minutes). */
export function RhythmMini({ series, label }: { series: readonly number[]; label: string }) {
  const peak = Math.max(...series, 1);
  const w = 150;
  const h = 34;
  const step = w / Math.max(1, series.length - 1);
  const pts: Pt[] = series.map((v, i) => [i * step, v]);
  const a = area<Pt>()
    .x((d) => d[0])
    .y0((d) => h / 2 + (d[1] * (h / 2 - 2)) / peak)
    .y1((d) => h / 2 - (d[1] * (h / 2 - 2)) / peak)
    .curve(curveLinear)(pts);
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="block h-9 w-full"
      role="img"
      aria-label={label}
      data-viz="rhythm-mini"
    >
      <line x1="0" x2={w} y1={h / 2} y2={h / 2} stroke="var(--line-strong)" vectorEffect="non-scaling-stroke" />
      <path d={a ?? ""} fill="var(--muted-accent)" opacity="0.85" />
    </svg>
  );
}
