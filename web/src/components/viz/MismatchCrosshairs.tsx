// V1 Puncture Point Mismatch Crosshairs. Five lane columns in the attacker's frame, facing the
// defender's goal (attacker's left flank on the left). Bars up: the attacker's share of final-third
// entries per lane; bars down: the defender's share of entries conceded per lane (same scale, both
// season). A tick on each bar marks the league share. The crosshair sits on a lane only when a
// Verifier-approved matchup claim exists for the pair, and on that claim's own lane.
import { memo } from "react";
import { cx } from "../../lib/cx";
import { num, pct } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { crosshairLane, mirrorLane } from "../../lib/viz";
import type { HeadToHead, TeamProfile } from "../../types/ui";
import { VizFigure } from "./Figure";

const SHORT: Record<string, string> = {
  left_flank: "L flank",
  left_half_space: "L half",
  center: "Centre",
  right_half_space: "R half",
  right_flank: "R flank",
};
const FULL: Record<string, string> = {
  left_flank: "left flank",
  left_half_space: "left half-space",
  center: "centre",
  right_half_space: "right half-space",
  right_flank: "right flank",
};

const W = 500;
const COL = W / 5;
const BAR = 46;

export const MismatchCrosshairs = memo(function MismatchCrosshairs({
  h,
  defender,
  lanes,
  compact = false,
  claimLane,
  claimId,
  legend = true,
}: {
  h: HeadToHead;
  defender: TeamProfile;
  lanes: readonly string[];
  compact?: boolean;
  /** The lane of a stream claim (Live card); defaults to the season claim's lane. */
  claimLane?: string | null;
  claimId?: string;
  /** false: the caller shows one shared legend (the Match Hub's Matchup section) */
  legend?: boolean;
}) {
  const { lang } = useT();
  const att = h.attacker;
  const dfn = h.defender;
  const lane = claimLane !== undefined ? claimLane : crosshairLane(h.claim);
  const up = lanes.map((l) => ({ l, v: h.lanes[l]?.attack_share ?? 0, lg: h.lanes[l]?.league_share ?? 0 }));
  const down = lanes.map((l) => ({
    l,
    v: defender.entry_lanes_conceded[l]?.share ?? 0,
    lg: defender.entry_lanes_conceded[l]?.league ?? 0,
  }));
  const max = Math.max(...up.map((x) => Math.max(x.v, x.lg)), ...down.map((x) => Math.max(x.v, x.lg)), 1);
  const half = compact ? 78 : 104;
  const labelH = 36;
  const top = 34;
  const mid = top + half;
  const H = mid + half + 26 + labelH;
  const y = (v: number) => (half * v) / max;
  const ci = lane ? lanes.indexOf(lane) : -1;
  const summary =
    `${att} attacking ${dfn}. Bars up: ${att}'s share of final-third entries per lane; bars down: ${dfn}'s share of entries conceded. ` +
    (lane
      ? `Crosshair on the ${FULL[lane]} (${att}'s view; ${dfn} calls it the ${FULL[mirrorLane(lane)]}), the lane the verified matchup claim names.`
      : "No verified matchup claim, so no crosshair.");
  return (
    <VizFigure
      viz="crosshairs"
      caption={
        compact ? undefined : (
          <>
            Facing {dfn}'s goal, {att}'s left flank on the left. Up: {att}'s entries per lane. Down: entries {dfn}{" "}
            concedes per lane. White tick: league share.{" "}
            {lane
              ? `The crosshair marks the lane of the verified matchup claim (${dfn} calls it its ${FULL[mirrorLane(lane)]}).`
              : "No verified claim for this pair, so no crosshair."}
          </>
        )
      }
      table={{
        caption: summary,
        head: ["Lane (attacker's view)", `${att} entries`, "League, entries", `${dfn} conceded`, "League, conceded"],
        rows: lanes.map((l, i) => [
          FULL[l] ?? l,
          pct(up[i]!.v, lang),
          pct(up[i]!.lg, lang),
          pct(down[i]!.v, lang),
          pct(down[i]!.lg, lang),
        ]),
      }}
    >
      {legend && (
        <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-ink-2" aria-hidden="true">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm bg-accent" /> {att} entries % (up)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-3 rounded-sm border border-muted bg-[repeating-linear-gradient(45deg,var(--muted-accent)_0_2px,transparent_2px_5px)]" />{" "}
            {dfn} concedes % (down)
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-4 bg-ink" /> league
          </span>
          {lane && (
            <span className="inline-flex items-center gap-1.5 font-semibold text-revise" data-lane-ok="verified-claim">
              <svg viewBox="0 0 12 12" className="h-3 w-3" aria-hidden="true">
                <circle cx="6" cy="6" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" />
              </svg>
              verified claim lane
            </span>
          )}
        </div>
      )}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={summary}
        className={cx("block h-auto w-full", compact ? "max-w-[420px]" : "max-w-[640px]")}
        data-attacker={att}
        data-defender={dfn}
        data-claim-lane={lane ?? ""}
        data-claim-id={claimId}
      >
        <defs>
          <pattern
            id={`hatch-${att}-${dfn}`}
            width="7"
            height="7"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="7" height="7" fill="var(--muted-accent-soft)" />
            <line x1="0" y1="0" x2="0" y2="7" stroke="var(--muted-accent)" strokeWidth="2.6" />
          </pattern>
          <radialGradient id={`glow-${att}-${dfn}`}>
            <stop offset="0" stopColor="var(--revise)" stopOpacity="0.45" />
            <stop offset="1" stopColor="var(--revise)" stopOpacity="0" />
          </radialGradient>
        </defs>
        {ci >= 0 && (
          <g data-crosshair data-lane={lane ?? undefined} className="crosshair">
            <rect
              x={ci * COL + 4}
              y={top - 20}
              width={COL - 8}
              height={2 * half + 40}
              rx="10"
              fill="var(--revise-soft)"
            />
            <circle cx={ci * COL + COL / 2} cy={mid} r={COL * 0.62} fill={`url(#glow-${att}-${dfn})`} />
            <circle cx={ci * COL + COL / 2} cy={mid} r="17" fill="none" stroke="var(--revise)" strokeWidth="3" />
            <line
              x1={ci * COL + COL / 2}
              x2={ci * COL + COL / 2}
              y1={mid - 30}
              y2={mid + 30}
              stroke="var(--revise)"
              strokeWidth="2.5"
            />
            <line
              x1={ci * COL + 14}
              x2={ci * COL + COL - 14}
              y1={mid}
              y2={mid}
              stroke="var(--revise)"
              strokeWidth="2.5"
            />
          </g>
        )}
        <line x1="0" x2={W} y1={mid} y2={mid} stroke="var(--line-strong)" strokeWidth="1.5" />
        {lanes.map((l, i) => {
          const cx0 = i * COL + COL / 2;
          const u = up[i]!;
          const d = down[i]!;
          const hit = i === ci;
          return (
            <g key={l} data-lane={l} data-value={u.v} data-conceded={d.v} data-team={att}>
              <rect
                x={cx0 - BAR / 2}
                y={mid - y(u.v)}
                width={BAR}
                height={y(u.v)}
                rx="4"
                fill={hit ? "var(--revise)" : "var(--accent)"}
                opacity={hit ? 1 : 0.85}
              />
              <rect
                x={cx0 - BAR / 2}
                y={mid}
                width={BAR}
                height={y(d.v)}
                rx="4"
                fill={`url(#hatch-${att}-${dfn})`}
                stroke="var(--muted-accent)"
                strokeWidth="1.5"
                data-team={dfn}
              />
              <line
                x1={cx0 - BAR / 2 - 7}
                x2={cx0 + BAR / 2 + 7}
                y1={mid - y(u.lg)}
                y2={mid - y(u.lg)}
                stroke="var(--ink)"
                strokeWidth="2.5"
              />
              <line
                x1={cx0 - BAR / 2 - 7}
                x2={cx0 + BAR / 2 + 7}
                y1={mid + y(d.lg)}
                y2={mid + y(d.lg)}
                stroke="var(--ink)"
                strokeWidth="2.5"
              />
              <text
                x={cx0}
                y={mid - y(Math.max(u.v, u.lg)) - 8}
                textAnchor="middle"
                className="num"
                fontSize="22"
                fontWeight="700"
                fill={hit ? "var(--revise)" : "var(--ink)"}
              >
                {num(u.v, lang)}
              </text>
              <text
                x={cx0}
                y={mid + y(Math.max(d.v, d.lg)) + 25}
                textAnchor="middle"
                className="num"
                fontSize="21"
                fill="var(--ink-2)"
              >
                {num(d.v, lang)}
              </text>
              <text
                x={cx0}
                y={H - 8}
                textAnchor="middle"
                fontSize="22"
                fontWeight={hit ? 700 : 500}
                fill={hit ? "var(--revise)" : "var(--ink-2)"}
              >
                {SHORT[l]}
              </text>
            </g>
          );
        })}
      </svg>
    </VizFigure>
  );
});
