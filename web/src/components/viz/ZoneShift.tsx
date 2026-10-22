// V10 Zonal Grid Shift Matrix. The showcase match's on-ball events of one team (the `track`: event
// locations in the acting team's attacking frame, not tracking), counted per zone (3 thirds × 5
// lanes) in each half. Each cell shows the change in the team's share of its events there, second
// half minus first, in percentage points: purple where the share fell, green where it rose, and the
// signed number in the cell so colour is never the only carrier. On-ball share is not possession
// time, and a shift describes where the team's actions happened, not why.
import { useState } from "react";
import { num, signed } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { divColor, zoneShares } from "../../lib/viz";
import type { Period, TrackEntry } from "../../types/ui";
import { Segmented } from "../ui/segmented";
import { VizFigure } from "./Figure";

const PX = 1.05;
const PY = 0.68;
const THIRD_NAME = ["own third", "middle third", "final third"];
const LANE_NAME = ["left flank", "left half-space", "centre", "right half-space", "right flank"];

/** Displayed values: shares as a percentage to 1 dp, the shift in points to 1 dp. */
export const pct1 = (v: number) => Math.round(v * 1000) / 10;

export function zoneShift(
  track: readonly TrackEntry[],
  team: string,
  periods: readonly Period[],
  thirdX: readonly [number, number],
) {
  const [p1, p2] = periods;
  const a = zoneShares(track, team, p1!.start_sec, p1!.end_sec, thirdX);
  const b = zoneShares(track, team, p2!.start_sec, p2!.end_sec, thirdX);
  const cells = a.shares.map((s1, z) => ({ z, first: s1, second: b.shares[z]!, shift: pct1(b.shares[z]! - s1) }));
  return { cells, n1: a.n, n2: b.n };
}

export function ZoneShift({
  track,
  periods,
  thirdX,
  codes,
  initial,
}: {
  track: readonly TrackEntry[];
  periods: readonly Period[];
  thirdX: [number, number];
  codes: string[];
  initial: string;
}) {
  const { lang } = useT();
  const [team, setTeam] = useState(initial);
  if (periods.length < 2) return <p className="text-[13px] text-ink-3">Not available in this dataset: one period only.</p>;
  const { cells, n1, n2 } = zoneShift(track, team, periods, thirdX);
  const maxAbs = Math.max(1, ...cells.map((c) => Math.abs(c.shift)));
  const top = [...cells].sort((x, y) => y.shift - x.shift)[0]!;
  const xs = [0, thirdX[0], thirdX[1], 100];
  const name = (z: number) => `${LANE_NAME[z % 5]}, ${THIRD_NAME[Math.floor(z / 5)]}`;
  return (
    <VizFigure
      viz="zone-shift"
      caption={
        <>
          {team}&apos;s on-ball events in the showcase match: <span className="num">{num(n1, lang)}</span> in the first
          half, <span className="num">{num(n2, lang)}</span> in the second. Each cell: change in the share of those events
          in that zone, second half minus first, in points. Attacking left to right. Event locations, not tracking; a
          shift is not a cause.
        </>
      }
      table={{
        caption: `${team}: share of on-ball events per zone, first and second half`,
        head: ["Zone", "First half %", "Second half %", "Change (points)"],
        rows: cells.map((c) => [
          name(c.z),
          num(pct1(c.first), lang),
          num(pct1(c.second), lang),
          signed(c.shift, lang),
        ]),
      }}
    >
      <Segmented
        label="Team"
        name="zone-team"
        value={team}
        onChange={setTeam}
        options={codes.map((c) => ({ value: c, label: c }))}
        className="mb-3"
      />
      <svg
        viewBox="-1 -1 107 77"
        role="img"
        aria-label={`${team}: largest rise in the ${name(top.z)}, ${signed(top.shift, lang)} points from the first half to the second.`}
        className="block h-auto w-full max-w-[560px]"
        data-team={team}
        data-n1={n1}
        data-n2={n2}
      >
        <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" rx="1" />
        {cells.map((c) => {
          const third = Math.floor(c.z / 5);
          const lane = c.z % 5;
          const x0 = xs[third]! * PX;
          const w = (xs[third + 1]! - xs[third]!) * PX;
          const y0 = lane * 20 * PY;
          return (
            <g key={c.z} data-zone={c.z} data-value={c.shift}>
              <title>{`${name(c.z)}: ${num(pct1(c.first), lang)}% → ${num(pct1(c.second), lang)}%`}</title>
              <rect
                x={x0 + 0.4}
                y={y0 + 0.4}
                width={w - 0.8}
                height={20 * PY - 0.8}
                rx="0.8"
                fill={divColor(c.shift / maxAbs)}
                opacity="0.9"
              />
              <text
                x={x0 + w / 2}
                y={y0 + 10 * PY + 1.6}
                textAnchor="middle"
                fontSize="4.4"
                fontWeight="700"
                fill="var(--ink)"
                stroke="var(--bg)"
                strokeWidth="0.5"
                paintOrder="stroke"
              >
                {signed(c.shift, lang)}
              </text>
            </g>
          );
        })}
        <g fill="none" stroke="var(--pitch-line)" strokeWidth="0.3" aria-hidden="true">
          <rect x="0" y="0" width="105" height="68" />
          <line x1={52.5} x2={52.5} y1="0" y2="68" />
          <rect x={84 * PX} y={22 * PY} width={16 * PX} height={56 * PY} />
          <rect x="0" y={22 * PY} width={16 * PX} height={56 * PY} />
        </g>
        <text x="52.5" y="74" textAnchor="middle" fontSize="4.2" fill="var(--ink-2)" aria-hidden="true">
          attacking →
        </text>
      </svg>
      <div className="mt-2 flex items-center gap-2 text-[11.5px] text-ink-3" aria-hidden="true">
        <span>share fell</span>
        <span
          className="h-2 w-28 rounded-full"
          style={{ background: `linear-gradient(90deg, ${divColor(-1)}, ${divColor(0)}, ${divColor(1)})` }}
        />
        <span>share rose</span>
      </div>
    </VizFigure>
  );
}
