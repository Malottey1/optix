// HeatPitch: where a team's on-ball events happened, as a heat map. Native SVG, one rect per bin
// of the export's zone-aligned 24 x 16 grid (data-bin = bin index, data-count = raw events), drawn
// in true pitch geometry, smoothed for display only (lib/heat.ts), pitch lines on top, an
// attacking-direction arrow and a numeric legend. Volume mode: one hue, smoothed events per % of
// the pitch. Change mode: second half minus first, diverging blue (fell) / orange (rose), symmetric
// around zero. A closed "View data" holds the 15-zone table; one sentence names the largest rise and
// fall of the zone share. Event locations, not tracking; a change is described, never explained.
import { useId, useMemo, useState } from "react";
import { PX, PY, PitchLines } from "../components/pitch/Pitch";
import { Segmented } from "../components/ui/segmented";
import { num, signed } from "../lib/format";
import { type HeatGrid, density, zoneChange, zoneFromBins } from "../lib/heat";
import { type Key, useT } from "../lib/i18n";

export type HeatMode = "volume" | "change";
export type HeatHalf = "1" | "2" | "both";

const THIRD_KEYS: Key[] = ["third_own", "third_middle", "third_final"];
const LANE_KEYS: Key[] = ["lane_lf", "lane_lhs", "lane_c", "lane_rhs", "lane_rf"];
const MAX_OPACITY = 0.92;

/** 1 dp, as the legend and table show values. */
export const round1 = (v: number) => Math.round(v * 10) / 10;
const pct1 = (v: number) => Math.round(v * 1000) / 10;

const fill = (s: string, vars: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

/** The values a map shows for a team, mode and half; `scale` is the legend's top (1 dp). */
export function heatValues(grid: HeatGrid, halves: readonly (readonly number[])[], mode: HeatMode, half: HeatHalf) {
  const [a = [], b = []] = halves;
  const counts =
    mode === "change"
      ? b.map((v, i) => v - a[i]!)
      : half === "1" || halves.length < 2
        ? a
        : half === "2"
          ? b
          : a.map((v, i) => v + b[i]!);
  let values: number[];
  if (mode === "change") {
    const d1 = density(grid, a);
    values = density(grid, b).map((v, i) => v - d1[i]!);
  } else values = density(grid, counts);
  const top = Math.max(0, ...values.map((v) => Math.abs(v)));
  return { counts, values, scale: round1(top) };
}

export function HeatPitch({
  grid,
  teams,
  codes,
  initialTeam,
  initialMode = "volume",
  label,
  compact = false,
}: {
  grid: HeatGrid;
  /** team code -> [first-half bins, second-half bins] (raw counts) */
  teams: Record<string, number[][]>;
  codes: string[];
  initialTeam?: string;
  initialMode?: HeatMode;
  /** what the events are, for the accessible name, e.g. "showcase match" */
  label?: string;
  /** player touch map: no team toggle */
  compact?: boolean;
}) {
  const { t, lang } = useT();
  const uid = useId().replace(/:/g, "");
  const [team, setTeam] = useState(initialTeam ?? codes[0]!);
  const [mode, setMode] = useState<HeatMode>(initialMode);
  const [half, setHalf] = useState<HeatHalf>("both");
  const halves = useMemo(() => teams[team] ?? [], [teams, team]);
  const twoHalves = halves.length >= 2;
  const m = twoHalves ? mode : "volume";
  // values recomputed only when the inputs change (smoothing is a few thousand multiplications)
  const { counts, values, scale } = useMemo(() => heatValues(grid, halves, m, half), [grid, halves, m, half]);
  const zones = useMemo(
    () => (twoHalves ? zoneChange(halves[0]!, halves[1]!, grid.cols) : null),
    [twoHalves, halves, grid.cols],
  );
  const first = twoHalves ? zoneFromBins(halves[0]!, grid.cols) : null;
  const second = twoHalves ? zoneFromBins(halves[1]!, grid.cols) : null;
  const zoneName = (z: number) => `${t(LANE_KEYS[z % 5]!)}, ${t(THIRD_KEYS[Math.floor(z / 5)]!)}`;
  const what =
    m === "change" ? t("heat_change") : half === "1" ? t("half_one") : half === "2" ? t("half_two") : t("half_both");
  const sentence =
    zones &&
    fill(t("heat_summary"), {
      team,
      rise: zoneName(zones.rise),
      rv: signed(zones.change[zones.rise]!, lang),
      fall: zoneName(zones.fall),
      fv: signed(zones.change[zones.fall]!, lang),
    });

  const color = (v: number) => (m === "volume" ? "var(--heat-seq)" : v >= 0 ? "var(--heat-rise)" : "var(--heat-fall)");
  const opacity = (v: number) => (scale > 0 ? Math.min(1, Math.abs(v) / scale) * MAX_OPACITY : 0);

  return (
    <figure data-viz="heat" data-team={team} data-mode={m} data-half={half} className="m-0 min-w-0">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {!compact && codes.length > 1 && (
          <Segmented
            label={t("heat_team")}
            name="heat-team"
            value={team}
            onChange={setTeam}
            options={codes.map((c) => ({ value: c, label: c }))}
          />
        )}
        {twoHalves && (
          <Segmented
            label={t("heat_mode")}
            name="heat-mode"
            value={m}
            onChange={(v) => setMode(v)}
            options={[
              { value: "volume", label: t("heat_volume") },
              { value: "change", label: t("heat_change") },
            ]}
          />
        )}
        {twoHalves && m === "volume" && (
          <Segmented
            label={t("heat_half")}
            name="heat-half"
            value={half}
            onChange={(v) => setHalf(v)}
            options={[
              { value: "1", label: t("half_one") },
              { value: "2", label: t("half_two") },
              { value: "both", label: t("half_both") },
            ]}
          />
        )}
      </div>
      <svg
        viewBox="-1 -1 107 76"
        className="block h-auto w-full"
        role="img"
        aria-label={fill(t("heat_aria"), { team, what: label ? `${label}, ${what}` : what })}
      >
        <defs>
          <clipPath id={`${uid}-clip`}>
            <rect x="0" y="0" width="105" height="68" />
          </clipPath>
          <filter id={`${uid}-soft`} x="-5%" y="-5%" width="110%" height="110%">
            <feGaussianBlur stdDeviation="1.1" />
          </filter>
          <marker
            id={`${uid}-arrow`}
            viewBox="0 0 10 10"
            refX="8"
            refY="5"
            markerWidth="4"
            markerHeight="4"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="var(--ink-3)" />
          </marker>
        </defs>
        <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
        <g clipPath={`url(#${uid}-clip)`}>
          <g filter={`url(#${uid}-soft)`}>
            {values.map((v, b) => {
              const row = Math.floor(b / grid.cols);
              const col = b % grid.cols;
              const x0 = grid.x_edges[col]! * PX;
              const y0 = grid.y_edges[row]! * PY;
              return (
                <rect
                  key={b}
                  data-bin={b}
                  data-count={counts[b]}
                  x={x0}
                  y={y0}
                  width={grid.x_edges[col + 1]! * PX - x0 + 0.05}
                  height={grid.y_edges[row + 1]! * PY - y0 + 0.05}
                  fill={color(v)}
                  fillOpacity={opacity(v)}
                />
              );
            })}
          </g>
        </g>
        <PitchLines ground={false} />
        <line
          x1="40"
          y1="72"
          x2="65"
          y2="72"
          stroke="var(--ink-3)"
          strokeWidth="0.5"
          markerEnd={`url(#${uid}-arrow)`}
        />
      </svg>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[12px] text-ink-3">
        <span>{t("heat_attacking")} →</span>
        <Legend mode={m} scale={scale} uid={uid} />
      </div>
      {sentence && <figcaption className="mt-2 text-[13px] leading-snug text-ink-2">{sentence}</figcaption>}
      {first && second && zones && (
        <details className="mt-2 text-[12px] text-ink-3">
          <summary className="cursor-pointer select-none py-1 font-semibold text-ink-2">{t("view_data")}</summary>
          <p className="mb-1">{t("heat_proxy")}</p>
          <div className="overflow-x-auto">
            <table data-heat-table={team} className="w-full min-w-[320px] border-collapse text-left">
              <thead>
                <tr>
                  <th scope="col" className="py-1 pr-2">
                    {t("tbl_zone")}
                  </th>
                  <th scope="col" className="py-1 pr-2 text-right">
                    {t("tbl_first_pct")}
                  </th>
                  <th scope="col" className="py-1 pr-2 text-right">
                    {t("tbl_second_pct")}
                  </th>
                  <th scope="col" className="py-1 text-right">
                    {t("tbl_change_pts")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {first.shares.map((s, z) => (
                  <tr key={z} className="border-t border-line">
                    <th scope="row" className="py-1 pr-2 font-normal">
                      {zoneName(z)}
                    </th>
                    <td className="num py-1 pr-2 text-right">{num(pct1(s), lang)}</td>
                    <td className="num py-1 pr-2 text-right">{num(pct1(second.shares[z]!), lang)}</td>
                    <td className="num py-1 text-right">{signed(zones.change[z]!, lang)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </figure>
  );
}

function Legend({ mode, scale, uid }: { mode: HeatMode; scale: number; uid: string }) {
  const { t, lang } = useT();
  const id = `${uid}-legend`;
  return (
    <span className="inline-flex items-center gap-2" data-heat-legend={mode}>
      <span>{mode === "volume" ? t("heat_legend_volume") : t("heat_legend_change")}</span>
      <span className="num">{mode === "volume" ? num(0, lang) : signed(-scale, lang)}</span>
      <svg width="72" height="10" aria-hidden="true">
        <defs>
          <linearGradient id={id}>
            {mode === "volume" ? (
              <>
                <stop offset="0%" stopColor="var(--heat-seq)" stopOpacity="0" />
                <stop offset="100%" stopColor="var(--heat-seq)" stopOpacity={MAX_OPACITY} />
              </>
            ) : (
              <>
                <stop offset="0%" stopColor="var(--heat-fall)" stopOpacity={MAX_OPACITY} />
                <stop offset="50%" stopColor="var(--heat-fall)" stopOpacity="0" />
                <stop offset="50%" stopColor="var(--heat-rise)" stopOpacity="0" />
                <stop offset="100%" stopColor="var(--heat-rise)" stopOpacity={MAX_OPACITY} />
              </>
            )}
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="72" height="10" rx="2" fill="var(--pitch)" />
        <rect x="0" y="0" width="72" height="10" rx="2" fill={`url(#${id})`} />
      </svg>
      <span className="num">{mode === "volume" ? num(scale, lang) : signed(scale, lang)}</span>
    </span>
  );
}
