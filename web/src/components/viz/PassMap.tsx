// The Player Console's pass map and chance map (V4, redrawn). Pass map: one thin line per completed
// pass, the player's most progressive forward passes from the team's players-<code>.json (the export
// keeps the TOP_PASSES that gained the most ground), coloured by type: forward, progressive, key
// pass; key passes are drawn last, on top. Chance map: one line per key pass, set piece in gold and
// open play in blue, ending in a ring on the shot it set up (filled for a goal), the same style as
// the chance evidence drawer. Coordinates are only in the hidden table.
import type { ChanceRow, PassRow } from "../../data/matches";
import { num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import { PitchLines } from "../pitch/Pitch";
import { VizFigure } from "./Figure";
import { PassLine } from "./PassLines";

export const PASS_TYPES = ["forward", "progressive", "key_pass"] as const;
export const PASS_COLOR = ["var(--pass-forward)", "var(--pass-progressive)", "var(--pass-key)"] as const;
const PASS_KEY: Key[] = ["pm_forward", "pm_progressive", "pm_key"];
export const chanceColor = (kind: ChanceRow[4]) =>
  kind === "open_play" ? "var(--chance-open-play)" : "var(--chance-set-piece)";

const fill = (s: string, vars: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

/** Draw order: forward, then progressive, then key passes on top (stable inside a type). */
export const drawOrder = (rows: readonly PassRow[]) => [...rows].sort((a, b) => a[5] - b[5]);

function Pitch({ label, children, data }: { label: string; children: React.ReactNode; data: Record<string, string> }) {
  return (
    <svg
      viewBox="-2 -2 109 72"
      role="img"
      aria-label={label}
      className="block h-auto w-full max-w-[640px] rounded-lg"
      {...data}
    >
      <PitchLines />
      {children}
    </svg>
  );
}

/** A legend swatch: a short line with its start dot and arrowhead (or the shot ring). */
function Swatch({ color, ring }: { color: string; ring?: boolean }) {
  return (
    <svg viewBox="0 0 22 10" className="h-2.5 w-[22px] shrink-0" aria-hidden="true">
      {ring ? (
        <circle cx="11" cy="5" r="3.6" fill="none" stroke={color} strokeWidth="1.5" />
      ) : (
        <>
          <circle cx="2" cy="5" r="1.6" fill={color} />
          <line x1="2" y1="5" x2="15" y2="5" stroke={color} strokeWidth="2" />
          <polygon points="21,5 15,1.8 15,8.2" fill={color} />
        </>
      )}
    </svg>
  );
}

export function PassMap({ rows, player, name }: { rows: readonly PassRow[]; player: string; name: string }) {
  const { t, lang } = useT();
  const counts = PASS_TYPES.map((_, i) => rows.filter((r) => r[5] === i).length);
  const label = `${name}: ${fill(t("pp_routes_note"), { n: String(rows.length) })}`;
  return (
    <VizFigure
      viz="pass-map"
      caption={<span data-role="routes-note">{fill(t("pp_routes_note"), { n: num(rows.length, lang) })}</span>}
      table={{
        caption: label,
        head: [t("pm_type"), t("pm_x0"), t("pm_y0"), t("pm_x1"), t("pm_y1")],
        rows: rows.map((r) => [t(PASS_KEY[r[5]] ?? "pm_forward"), r[1], r[2], r[3], r[4]]),
      }}
    >
      <Pitch label={label} data={{ "data-player": player, "data-passes": String(rows.length) }}>
        {drawOrder(rows).map((r) => (
          <g key={r[0]} data-pass={r[0]} data-type={PASS_TYPES[r[5]]}>
            <PassLine x0={r[1]} y0={r[2]} x1={r[3]} y1={r[4]} color={PASS_COLOR[r[5]] ?? PASS_COLOR[0]} />
          </g>
        ))}
      </Pitch>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2" data-legend="pass-types">
        {PASS_TYPES.map((k, i) => (
          <li key={k} className="inline-flex items-center gap-1.5" data-legend-type={k} data-count={counts[i]}>
            <Swatch color={PASS_COLOR[i]!} />
            {t(PASS_KEY[i]!)}
          </li>
        ))}
      </ul>
    </VizFigure>
  );
}

/** The chance lines alone (the console's chances tab and the evidence drawer). */
export function ChanceLines({ rows }: { rows: readonly ChanceRow[] }) {
  return rows.map((r) => (
    <g key={r[0]} data-chance={r[0]} data-kind={r[4]}>
      <PassLine
        x0={r[8]}
        y0={r[9]}
        x1={r[10]}
        y1={r[11]}
        color={chanceColor(r[4])}
        shot={r[7] === "goal" ? "goal" : "other"}
      />
    </g>
  ));
}

/** Open play, set piece (with their counts) and the resulting shot ring. */
export function ChanceLegend({ rows }: { rows: readonly ChanceRow[] }) {
  const { t, lang } = useT();
  const op = rows.filter((r) => r[4] === "open_play").length;
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2" data-legend="chances">
      <li className="inline-flex items-center gap-1.5" data-legend-type="open_play">
        <Swatch color="var(--chance-open-play)" />
        {fill(t("ch_leg_op"), { n: num(op, lang) })}
      </li>
      <li className="inline-flex items-center gap-1.5" data-legend-type="set_piece">
        <Swatch color="var(--chance-set-piece)" />
        {fill(t("ch_leg_sp"), { n: num(rows.length - op, lang) })}
      </li>
      <li className="inline-flex items-center gap-1.5">
        <Swatch color="var(--ink-2)" ring />
        {t("ch_legend_shot")}
      </li>
    </ul>
  );
}

export function ChanceMap({ rows, player, name }: { rows: readonly ChanceRow[]; player: string; name: string }) {
  const { t } = useT();
  const label = `${name}: ${t("route_chances")} ${rows.length}`;
  return (
    <VizFigure
      viz="chance-map"
      table={{
        caption: label,
        head: [t("ch_type"), t("pm_x0"), t("pm_y0"), t("pm_x1"), t("pm_y1")],
        rows: rows.map((r) => [t(`ch_kind_${r[4]}` as Key), r[8], r[9], r[10], r[11]]),
      }}
    >
      <Pitch label={label} data={{ "data-player": player, "data-chances": String(rows.length) }}>
        <ChanceLines rows={rows} />
      </Pitch>
      <ChanceLegend rows={rows} />
    </VizFigure>
  );
}
