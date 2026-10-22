// V3 Game-State Style Coordinate Swaps. Each team is drawn twice, trailing (hollow ring) and
// leading (filled diamond), joined by an arrow from trailing to leading: how its style moves once
// it goes ahead. x = field tilt (share of the match's final-third passes), y = press intensity
// (pressure events per opponent pass), both from the engine's season style profile per game-state
// bracket. A state is drawn only if both metrics have at least `min_n` observations. The grid has
// no tick numbers on purpose (every number on screen must come from the data): the exact values
// are in the cards under the chart and in the hidden table.
import { scaleLinear } from "d3-scale";
import { useState } from "react";
import { cx } from "../../lib/cx";
import { num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import type { StateMetric, StateName, Visuals } from "../../types/ui";
import { Segmented } from "../ui/segmented";
import { VizFigure } from "./Figure";

const W = 520;
const H = 300;
const M = { l: 36, r: 18, t: 16, b: 36 };

/** Displayed values: tilt as a percentage to 1 dp, press to 3 dp (documented in docs/visuals.md). */
export const tiltPct = (v: number) => Math.round(v * 1000) / 10;
export const press3 = (v: number) => Math.round(v * 1000) / 1000;

const enough = (s: Record<string, StateMetric>, minN: number) =>
  s.field_tilt!.value != null &&
  s.press_intensity!.value != null &&
  s.field_tilt!.n >= minN &&
  s.press_intensity!.n >= minN;

export function StateSwaps({ visuals, codes, initial }: { visuals: Visuals; codes: string[]; initial: string }) {
  const { lang } = useT();
  const [sel, setSel] = useState(initial);
  const minN = visuals.state_min_n;
  const pts = codes.map((code) => {
    const st = visuals.states[code]!;
    const get = (b: StateName) =>
      enough(st[b], minN) ? { x: st[b].field_tilt.value!, y: st[b].press_intensity.value! } : null;
    return { code, trailing: get("trailing"), leading: get("leading"), st };
  });
  const xs = pts.flatMap((p) => [p.trailing?.x, p.leading?.x]).filter((v): v is number => v != null);
  const ys = pts.flatMap((p) => [p.trailing?.y, p.leading?.y]).filter((v): v is number => v != null);
  const x = scaleLinear()
    .domain([Math.min(...xs) - 0.03, Math.max(...xs) + 0.03])
    .range([M.l, W - M.r]);
  const y = scaleLinear()
    .domain([0, Math.max(...ys) * 1.12])
    .range([H - M.b, M.t]);
  const cur = pts.find((p) => p.code === sel)!;
  // point labels near an edge are anchored inwards so they stay inside the plot
  const anchor = (px: number) => (px < M.l + 70 ? "start" : px > W - M.r - 70 ? "end" : "middle");
  const labelX = (px: number) => (px < M.l + 70 ? px - 8 : px > W - M.r - 70 ? px + 8 : px);
  const tickX = x.ticks(5);
  const tickY = y.ticks(4);
  const describe = (p: (typeof pts)[number]) =>
    p.trailing && p.leading
      ? `${p.code}: trailing tilt ${num(tiltPct(p.trailing.x), lang)}%, press ${num(press3(p.trailing.y), lang)}; leading tilt ${num(tiltPct(p.leading.x), lang)}%, press ${num(press3(p.leading.y), lang)}`
      : `${p.code}: not enough data in one state`;
  return (
    <VizFigure
      viz="state-swaps"
      caption={
        <>
          Ring: trailing. Diamond: leading. The arrow shows how the team's play moves once it goes ahead. Season data,
          the team's own score state; a state needs at least <span className="num">{num(minN, lang)}</span> observations
          per metric. Descriptive only: a shift is not a cause.
        </>
      }
      table={{
        caption: "Field tilt and press intensity when trailing and when leading",
        head: ["Team", "Trailing tilt %", "Trailing press", "Leading tilt %", "Leading press"],
        rows: pts.map((p) => [
          p.code,
          p.trailing ? num(tiltPct(p.trailing.x), lang) : "not enough data",
          p.trailing ? num(press3(p.trailing.y), lang) : "not enough data",
          p.leading ? num(tiltPct(p.leading.x), lang) : "not enough data",
          p.leading ? num(press3(p.leading.y), lang) : "not enough data",
        ]),
      }}
    >
      <Segmented
        label="Highlight a team"
        name="state-team"
        value={sel}
        onChange={setSel}
        options={codes.map((c) => ({ value: c, label: c }))}
        className="mb-3"
      />
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Field tilt against press intensity, trailing and leading. ${describe(cur)}.`}
        className="block h-auto w-full max-w-[640px]"
      >
        <defs>
          <marker id="swap-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--accent)" />
          </marker>
          <marker
            id="swap-arrow-dim"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="var(--ink-3)" />
          </marker>
        </defs>
        {tickX.map((t) => (
          <g key={`x${t}`}>
            <line x1={x(t)} x2={x(t)} y1={M.t} y2={H - M.b} stroke="var(--line)" />
          </g>
        ))}
        {tickY.map((t) => (
          <g key={`y${t}`}>
            <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} stroke="var(--line)" />
          </g>
        ))}
        <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" fontSize="19" fill="var(--ink-2)">
          Field tilt → more territory
        </text>
        <text
          x={18}
          y={(M.t + H - M.b) / 2}
          textAnchor="middle"
          fontSize="19"
          fill="var(--ink-2)"
          transform={`rotate(-90 18 ${(M.t + H - M.b) / 2})`}
        >
          Press intensity →
        </text>
        {pts.map((p) => {
          const on = p.code === sel;
          if (!p.trailing || !p.leading) return null;
          const [a, b] = [p.trailing, p.leading];
          const dx = x(b.x) - x(a.x);
          const dy = y(b.y) - y(a.y);
          const len = Math.hypot(dx, dy) || 1;
          const pad = 9;
          return (
            <g key={p.code} data-team={p.code} data-state-swap opacity={on ? 1 : 0.55}>
              <line
                x1={x(a.x) + (dx / len) * pad}
                y1={y(a.y) + (dy / len) * pad}
                x2={x(b.x) - (dx / len) * pad}
                y2={y(b.y) - (dy / len) * pad}
                stroke={on ? "var(--accent)" : "var(--ink-3)"}
                strokeWidth={on ? 3 : 1.6}
                markerEnd={`url(#${on ? "swap-arrow" : "swap-arrow-dim"})`}
              />
              <circle
                cx={x(a.x)}
                cy={y(a.y)}
                r="6.5"
                fill="var(--surface-1)"
                stroke={on ? "var(--accent)" : "var(--ink-3)"}
                strokeWidth="2.5"
                data-state="trailing"
                data-value={a.x}
              />
              <rect
                x={x(b.x) - 6}
                y={y(b.y) - 6}
                width="12"
                height="12"
                transform={`rotate(45 ${x(b.x)} ${y(b.y)})`}
                fill={on ? "var(--accent)" : "var(--ink-3)"}
                data-state="leading"
                data-value={b.x}
              />
            </g>
          );
        })}
        {cur.trailing && cur.leading && (
          <g aria-hidden="true">
            <text
              x={labelX(x(cur.leading.x))}
              y={y(cur.leading.y) + (cur.leading.y < cur.trailing.y ? 30 : -16)}
              textAnchor={anchor(x(cur.leading.x))}
              fontSize="20"
              fontWeight="700"
              fill="var(--accent)"
            >
              {cur.code} leading
            </text>
            <text
              x={labelX(x(cur.trailing.x))}
              y={y(cur.trailing.y) + (cur.trailing.y <= cur.leading.y ? 30 : -16)}
              textAnchor={anchor(x(cur.trailing.x))}
              fontSize="19"
              fill="var(--ink-2)"
            >
              trailing
            </text>
          </g>
        )}
      </svg>
      <dl className={cx("mt-3 grid grid-cols-2 gap-3 text-[13px] sm:grid-cols-4")} data-role="state-values">
        {(["trailing", "leading"] as StateName[]).flatMap((b) => {
          const p = b === "trailing" ? cur.trailing : cur.leading;
          return [
            <div key={`${b}-t`} className="rounded-lg border border-line bg-surface-2 px-3 py-2">
              <dt className="text-[11.5px] text-ink-3">{b === "trailing" ? "Trailing" : "Leading"} · tilt</dt>
              <dd className="num m-0 text-[17px] font-semibold text-ink">
                {p ? `${num(tiltPct(p.x), lang)}%` : "not enough data"}
              </dd>
            </div>,
            <div key={`${b}-p`} className="rounded-lg border border-line bg-surface-2 px-3 py-2">
              <dt className="text-[11.5px] text-ink-3">{b === "trailing" ? "Trailing" : "Leading"} · press</dt>
              <dd className="num m-0 text-[17px] font-semibold text-ink">
                {p ? num(press3(p.y), lang) : "not enough data"}
              </dd>
            </div>,
          ];
        })}
      </dl>
    </VizFigure>
  );
}
