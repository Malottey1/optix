// V8 Radial Percentile Pizza. One slice per involvement, pass-quality or chance metric; each slice's
// radius is the player's percentile against the comparison group (outfield players with at least
// MIN_PASSES passes). Slices run clockwise from 12 o'clock in the order of the list beside them; the
// list carries the label, the percentile and the raw value, so colour is never the only carrier.
import { memo } from "react";
import { num, pct } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { percentile, sliceArc } from "../../lib/viz";
import type { PlayerRow } from "../../types/ui";
import { VizFigure } from "./Figure";

export const MIN_PASSES = 100;

type Group = "volume" | "quality" | "source";
export const SLICES: { key: keyof PlayerRow; label: string; group: Group }[] = [
  { key: "involvement", label: "Involvement", group: "volume" },
  { key: "forward_passes", label: "Forward passes", group: "volume" },
  { key: "pass_completion", label: "Pass completion", group: "quality" },
  { key: "pass_quality_ratio", label: "Pass quality", group: "quality" },
  { key: "chances_open_play", label: "Chances, open play", group: "quality" },
  { key: "wide_share", label: "Forward passes ending wide", group: "source" },
  { key: "chances_set_piece", label: "Chances, set piece", group: "source" },
];
const FILL: Record<Group, string> = {
  volume: "var(--muted-accent)",
  quality: "var(--accent)",
  source: "var(--revise)",
};
const GROUP_NAME: Record<Group, string> = { volume: "volume", quality: "quality", source: "where it comes from" };

/** The comparison group: outfield players with at least MIN_PASSES passes. */
export const comparisonGroup = (players: readonly PlayerRow[]) =>
  players.filter((p) => p.position !== "GK" && p.passes >= MIN_PASSES);

/** Percentiles rounded to whole numbers, as displayed. */
export function pizzaValues(p: PlayerRow, group: readonly PlayerRow[]) {
  return SLICES.map((s) => {
    const raw = p[s.key] as number | null;
    const v = percentile(
      group.map((g) => g[s.key] as number | null),
      raw,
    );
    return { ...s, raw, pctl: v == null ? null : Math.round(v) };
  });
}

const fmtRaw = (key: keyof PlayerRow, v: number | null, lang: Parameters<typeof num>[1]) =>
  v == null
    ? "–"
    : key === "pass_completion" || key === "wide_share"
      ? pct(v, lang)
      : key === "pass_quality_ratio"
        ? `${num(v, lang)}×`
        : num(v, lang);

export const PercentilePizza = memo(function PercentilePizza({
  p,
  players,
}: {
  p: PlayerRow;
  players: readonly PlayerRow[];
}) {
  const { lang } = useT();
  const group = comparisonGroup(players);
  const vals = pizzaValues(p, group);
  const C = 100;
  const R0 = 14;
  const R1 = 92;
  const inGroup = group.some((g) => g.id === p.id);
  return (
    <VizFigure
      viz="pizza"
      caption={
        <>
          Percentile against <span className="num">{num(group.length, lang)}</span> outfield players with at least{" "}
          <span className="num">{num(MIN_PASSES, lang)}</span> passes (season totals; the data has no minutes, so not
          per ninety).{inGroup ? "" : " This player is outside that group, so read the slices with care."}
        </>
      }
      table={{
        caption: `${p.name}: percentile per metric`,
        head: ["Metric", "Value", "Percentile"],
        rows: vals.map((v) => [v.label, fmtRaw(v.key, v.raw, lang), v.pctl == null ? "–" : num(v.pctl, lang)]),
      }}
    >
      <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-[minmax(0,220px)_minmax(0,1fr)]">
        <svg
          viewBox="0 0 200 200"
          role="img"
          aria-label={`${p.name}: percentiles, ${vals.map((v) => `${v.label} ${v.pctl ?? "none"}`).join(", ")}`}
          className="mx-auto block h-auto w-full max-w-[220px]"
          data-player={p.id}
        >
          {[25, 50, 75, 100].map((r) => (
            <circle
              key={r}
              cx={C}
              cy={C}
              r={R0 + ((R1 - R0) * r) / 100}
              fill="none"
              stroke="var(--line)"
              strokeDasharray={r === 50 ? "3 3" : undefined}
            />
          ))}
          {vals.map((v, i) => (
            <path
              key={v.key}
              d={sliceArc(C, C, R0, R0 + ((R1 - R0) * (v.pctl ?? 0)) / 100, i, vals.length)}
              fill={FILL[v.group]}
              opacity={0.9}
              data-metric={v.key}
              data-value={v.pctl ?? ""}
            />
          ))}
          {vals.map((v, i) => {
            const a = (2 * Math.PI * (i + 0.5)) / vals.length - Math.PI / 2;
            return (
              <text
                key={v.key}
                x={C + (R1 + 2) * Math.cos(a)}
                y={C + (R1 + 2) * Math.sin(a) + 4}
                textAnchor="middle"
                fontSize="11"
                fontWeight="700"
                fill="var(--ink-2)"
                aria-hidden="true"
              >
                {String.fromCharCode(65 + i)}
              </text>
            );
          })}
        </svg>
        <ol className="m-0 grid list-none grid-cols-1 gap-1 p-0 text-[12.5px]" data-role="pizza-list">
          {vals.map((v, i) => (
            <li key={v.key} className="flex items-center gap-2" data-metric={v.key} data-percentile={v.pctl ?? ""}>
              <span
                className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-[11px] font-bold text-bg"
                style={{ background: FILL[v.group] }}
                aria-hidden="true"
              >
                {String.fromCharCode(65 + i)}
              </span>
              <span className="min-w-0 flex-1 truncate text-ink-2" title={GROUP_NAME[v.group]}>
                {v.label}
              </span>
              <span className="num text-ink-3">{fmtRaw(v.key, v.raw, lang)}</span>
              <b className="num w-10 text-right font-semibold text-ink">{v.pctl == null ? "–" : num(v.pctl, lang)}</b>
            </li>
          ))}
        </ol>
      </div>
      <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-ink-3" aria-hidden="true">
        {(Object.keys(FILL) as Group[]).map((g) => (
          <span key={g} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: FILL[g] }} />
            {GROUP_NAME[g]}
          </span>
        ))}
        <span>Dashed ring: 50th percentile.</span>
      </p>
    </VizFigure>
  );
});
