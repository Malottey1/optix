// V2 Shot-Clustering Scatter Blocks. The attacking end in the attacker's orientation (goal at the
// top). Each shot is a square centred on its event location whose AREA is proportional to its xG
// (side = K·√xG). Outcome is carried by the fill pattern, not colour alone: goal solid, saved half
// fill, blocked hatched, off target outline only. The caption gives shots, total xG and xG per shot
// for exactly the shots drawn.
import { memo } from "react";
import { cx } from "../../lib/cx";
import { clock, num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { shotBlockSide, sum } from "../../lib/viz";
import type { Period, ShotRow } from "../../types/ui";
import { VizFigure } from "./Figure";

const PX = 1.05; // pitch length units per data unit (105 m)
const PY = 0.68; // pitch width units per data unit (68 m)
/** Side, in metres, of a block worth 1.0 xG. */
export const K_SIDE = 18;

type Outcome = "goal" | "saved" | "blocked" | "off";
const outcomeOf = (r: string): Outcome =>
  r === "goal" ? "goal" : r === "saved" ? "saved" : r === "blocked" ? "blocked" : "off";
const OUTCOME_LABEL: Record<Outcome, string> = { goal: "Goal", saved: "Saved", blocked: "Blocked", off: "Off target" };

export interface ShotStats {
  shots: number;
  xg: number;
  perShot: number | null;
}
/** Display rounding matches the stream's xg claims: total to 2 dp, per shot to 3 dp. */
export function shotStats(shots: readonly ShotRow[]): ShotStats {
  const total = sum(shots.map((s) => s[6]));
  return {
    shots: shots.length,
    xg: Math.round(total * 100) / 100,
    perShot: shots.length ? Math.round((total / shots.length) * 1000) / 1000 : null,
  };
}

function Block({ s, color, uid }: { s: ShotRow; color: string; uid: string }) {
  const [id, , team, , x, y, xg, result] = s;
  const side = shotBlockSide(xg, K_SIDE);
  const cx0 = y * PY;
  const cy0 = (100 - x) * PX;
  const o = outcomeOf(result);
  const fill = o === "goal" ? color : o === "saved" ? color : o === "blocked" ? `url(#shot-hatch-${uid})` : "none";
  return (
    <rect
      data-event-id={id}
      data-team={team}
      data-value={xg}
      data-outcome={o}
      x={cx0 - side / 2}
      y={cy0 - side / 2}
      width={side}
      height={side}
      rx={Math.min(0.6, side / 6)}
      fill={fill}
      fillOpacity={o === "saved" ? 0.45 : o === "goal" ? 0.95 : 1}
      stroke={color}
      strokeWidth={o === "goal" ? 0.55 : 0.4}
    />
  );
}

export const ShotBlocks = memo(function ShotBlocks({
  shots,
  team,
  color,
  periods,
  windowLabel,
  compact = false,
  claimId,
}: {
  shots: readonly ShotRow[];
  team: string;
  color: string;
  periods: readonly Period[];
  windowLabel: string;
  compact?: boolean;
  claimId?: string;
}) {
  const { lang } = useT();
  const st = shotStats(shots);
  const uid = `${team}-${claimId ?? "panel"}${compact ? "-c" : ""}`;
  const minX = Math.min(66.7, ...shots.map((s) => s[4] - 3));
  const depth = (100 - minX) * PX;
  const vb = `-1 -4 ${68 + 2} ${depth + 5}`;
  const summary =
    `${team} shots ${windowLabel}: ${st.shots} shots, ${num(st.xg, lang)} expected goals` +
    (st.perShot != null ? `, ${num(st.perShot, lang)} per shot.` : ".") +
    " Each block's area is proportional to the shot's xG.";
  return (
    <VizFigure
      viz="shot-blocks"
      caption={
        <span data-role="shot-caption">
          <b className="num font-semibold text-ink-2" data-shots={st.shots}>
            {num(st.shots, lang)}
          </b>{" "}
          shots ·{" "}
          <b className="num font-semibold text-ink-2" data-xg={st.xg}>
            {num(st.xg, lang)}
          </b>{" "}
          xG · <b className="num font-semibold text-ink-2">{st.perShot == null ? "–" : num(st.perShot, lang)}</b> xG per
          shot{compact ? "" : `, ${windowLabel}. Block area ∝ xG.`}
        </span>
      }
      table={{
        caption: summary,
        head: ["Time", "xG", "Outcome"],
        rows: shots.map((s) => [clock(s[1], periods), num(s[6], lang), OUTCOME_LABEL[outcomeOf(s[7])]]),
      }}
    >
      <svg
        viewBox={vb}
        role="img"
        aria-label={summary}
        className={cx("block h-auto w-full rounded-lg bg-[var(--pitch)]", compact ? "max-h-[220px]" : "max-h-[340px]")}
        preserveAspectRatio="xMidYMin meet"
        data-team={team}
        data-claim-id={claimId}
        data-shots={st.shots}
        data-xg={st.xg}
      >
        <defs>
          <pattern
            id={`shot-hatch-${uid}`}
            width="1.4"
            height="1.4"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line x1="0" y1="0" x2="0" y2="1.4" stroke={color} strokeWidth="0.55" />
          </pattern>
        </defs>
        <g fill="none" stroke="var(--pitch-line)" strokeWidth="0.3">
          <rect x="0" y="0" width="68" height={depth} />
          <rect x={22 * PY} y="0" width={(78 - 22) * PY} height={16 * PX} />
          <rect x={(50 - 13.4) * PY} y="0" width={26.8 * PY} height={5.5} />
          <line x1={(50 - 5.4) * PY} x2={(50 + 5.4) * PY} y1="-1.2" y2="-1.2" strokeWidth="1" stroke="var(--ink-2)" />
          <circle cx={50 * PY} cy={11} r="0.35" fill="var(--pitch-line)" />
          <line x1="0" x2="68" y1={(100 - 66.7) * PX} y2={(100 - 66.7) * PX} strokeDasharray="0.8 0.8" />
        </g>
        {shots.map((s) => (
          <Block key={s[0]} s={s} color={color} uid={uid} />
        ))}
      </svg>
      {!compact && <ShotLegend color={color} uid={uid} />}
    </VizFigure>
  );
});

/** Outcome legend: the fill pattern of each outcome, so colour is never the only carrier. */
export function ShotLegend({ color, uid }: { color: string; uid: string }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2" aria-hidden="true">
      {(["goal", "saved", "blocked", "off"] as Outcome[]).map((o) => (
        <li key={o} className="inline-flex items-center gap-1.5">
          <svg viewBox="0 0 10 10" className="h-3 w-3">
            <defs>
              <pattern
                id={`lg-hatch-${uid}`}
                width="2.5"
                height="2.5"
                patternUnits="userSpaceOnUse"
                patternTransform="rotate(45)"
              >
                <line x1="0" y1="0" x2="0" y2="2.5" stroke={color} strokeWidth="1" />
              </pattern>
            </defs>
            <rect
              x="1"
              y="1"
              width="8"
              height="8"
              fill={o === "blocked" ? `url(#lg-hatch-${uid})` : o === "off" ? "none" : color}
              fillOpacity={o === "saved" ? 0.45 : 1}
              stroke={color}
              strokeWidth="1.2"
            />
          </svg>
          {OUTCOME_LABEL[o]}
        </li>
      ))}
    </ul>
  );
}
