// V4 Segmented Threat Velocity Arrows. A player's passes grouped by start zone and end zone (3
// thirds × 5 lanes, attacker's frame, attacking left to right) and drawn as arrows between zone
// centres. Width ∝ √passes (area tracks the count); colour on a grey → green sequential scale:
// forward passes = the route's pass quality (share ending in a high-threat central cell over the
// league share, the engine's pass_quality_ratio per route); chances = xA per chance. The scale's top
// is twice the league value, so the league average sits mid-scale and players are comparable.
// By default only the TOP_ROUTES busiest routes are drawn, with a slight bend and a fixed offset to
// the right of travel (so a route and its reverse never sit on top of each other); "Show all routes"
// draws the full set. The hidden table always lists every route.
import { memo, useState } from "react";
import { cx } from "../../lib/cx";
import { num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { arrowWidth, qualityRatio, routeGroups, seqColor, zoneCenter, type RouteGroup } from "../../lib/viz";
import type { RouteRow } from "../../types/ui";
import { VizFigure } from "./Figure";

const PX = 1.05;
const PY = 0.68;
/** Forward-pass routes need at least this many passes to be drawn (chance routes are all drawn). */
export const MIN_ROUTE_PASSES = 2;
/** Routes drawn by default (the busiest, by pass count). */
export const TOP_ROUTES = 8;
/** Bend of a route (share of its length) and its offset to the right of travel, in pitch units. */
const BEND = 0.05;
const LANE_OFFSET = 1.1;

export type RouteMode = "fwd" | "chances";

const ZONE_NAME = (z: number) => {
  const third = ["own third", "middle third", "final third"][Math.floor(z / 5)];
  const lane = ["left flank", "left half-space", "centre", "right half-space", "right flank"][z % 5];
  return `${lane}, ${third}`;
};

/** Display rounding: xA per chance to 3 dp, pass quality to 2 dp (as the deck shows it). */
export const per3 = (v: number) => Math.round(v * 1000) / 1000;
export const ratio2 = (v: number) => Math.round(v * 100) / 100;

/** The value a route is coloured by: pass quality (fwd) or xA per chance (op, sp). */
export const routeValue = (g: RouteGroup, leagueHotShare: number) =>
  g.kind === "fwd" ? qualityRatio(g.hot, g.passes, leagueHotShare) : g.perPass;
const shown = (g: RouteGroup, v: number) => (g.kind === "fwd" ? ratio2(v) : per3(v));

export function visibleRoutes(rows: readonly RouteRow[], mode: RouteMode): RouteGroup[] {
  const g = routeGroups(rows, mode);
  return mode === "fwd" ? g.filter((r) => r.passes >= MIN_ROUTE_PASSES) : g;
}

/** The routes drawn by default: the TOP_ROUTES busiest of the full drawable set. */
export const topRoutes = (rows: readonly RouteRow[], mode: RouteMode) => visibleRoutes(rows, mode).slice(0, TOP_ROUTES);

/** A route's path: start and end moved LANE_OFFSET to the right of travel, bent by BEND. */
export function routePath(ax: number, ay: number, bx: number, by: number) {
  const dx = bx - ax;
  const dy = by - ay;
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const [sx, sy, ex, ey] = [ax + nx * LANE_OFFSET, ay + ny * LANE_OFFSET, bx + nx * LANE_OFFSET, by + ny * LANE_OFFSET];
  const mx = (sx + ex) / 2 + nx * len * BEND;
  const my = (sy + ey) / 2 + ny * len * BEND;
  const r = (v: number) => Math.round(v * 100) / 100;
  return `M${r(sx)},${r(sy)} Q${r(mx)},${r(my)} ${r(ex)},${r(ey)}`;
}

function Arrow({
  g,
  maxN,
  top,
  thirdX,
  uid,
  leagueHotShare,
}: {
  g: RouteGroup;
  maxN: number;
  top: number;
  thirdX: [number, number];
  uid: string;
  leagueHotShare: number;
}) {
  const v = routeValue(g, leagueHotShare);
  const a = zoneCenter(g.from, thirdX);
  const b = zoneCenter(g.to, thirdX);
  const w = arrowWidth(g.passes, maxN, 0.7, 4.2);
  const color = seqColor(top > 0 ? v / top : 0);
  const dash = g.kind === "sp" ? "2.2 1.4" : undefined;
  const ax = a.x * PX;
  const ay = a.y * PY;
  const bx = b.x * PX;
  const by = b.y * PY;
  const title = `${g.passes} ${g.kind === "fwd" ? "forward passes" : g.kind === "sp" ? "set-piece chances" : "open-play chances"} from ${ZONE_NAME(g.from)} to ${ZONE_NAME(g.to)}: ${g.kind === "fwd" ? `pass quality ${shown(g, v)}×` : `${shown(g, v)} xA per chance`}`;
  const common = {
    "data-kind": g.kind,
    "data-from": g.from,
    "data-to": g.to,
    "data-value": g.passes,
    "data-quality": shown(g, v),
  };
  if (g.from === g.to) {
    return (
      <g {...common} data-route>
        <title>{title}</title>
        <circle
          cx={ax}
          cy={ay}
          r={2.4 + w / 2}
          fill="none"
          stroke={color}
          strokeWidth={w}
          strokeDasharray={dash}
          opacity="0.9"
        />
      </g>
    );
  }
  return (
    <g {...common} data-route>
      <title>{title}</title>
      <path
        d={routePath(ax, ay, bx, by)}
        fill="none"
        stroke={color}
        strokeWidth={w}
        strokeLinecap="round"
        strokeDasharray={dash}
        markerEnd={`url(#route-head-${uid})`}
        opacity="0.92"
      />
    </g>
  );
}

export const PassRoutes = memo(function PassRoutes({
  rows,
  mode,
  leagueHotShare,
  leagueXa,
  thirdX,
  player,
  compact = false,
}: {
  rows: readonly RouteRow[];
  mode: RouteMode;
  /** League share of forward passes ending in a high-threat cell (pass quality 1×). */
  leagueHotShare: number;
  /** League xA per chance (sum over every player's chance routes). */
  leagueXa: number;
  thirdX: [number, number];
  player: string;
  compact?: boolean;
}) {
  const { lang } = useT();
  const [showAll, setShowAll] = useState(false);
  const full = visibleRoutes(rows, mode);
  const groups = showAll ? full : full.slice(0, TOP_ROUTES);
  const all = routeGroups(rows, mode);
  const total = all.reduce((s, g) => s + g.passes, 0);
  const shownPasses = groups.reduce((s, g) => s + g.passes, 0);
  const hot = all.reduce((s, g) => s + g.hot, 0);
  const xa = all.reduce((s, g) => s + g.perPass * g.passes, 0);
  const overall = mode === "fwd" ? ratio2(qualityRatio(hot, total, leagueHotShare)) : per3(total ? xa / total : 0);
  const league = mode === "fwd" ? 1 : per3(leagueXa);
  const maxN = Math.max(1, ...groups.map((g) => g.passes));
  const top = mode === "fwd" ? 2 : 2 * leagueXa;
  const uid = `${player}-${mode}${compact ? "-c" : ""}`;
  const unit = mode === "fwd" ? "× pass quality" : "xA per chance";
  const what = mode === "fwd" ? "forward passes" : "chances created";
  const summary = `${player}: ${total} ${what}; ${overall}${mode === "fwd" ? "× pass quality" : " xA per chance"} (league ${league}${mode === "fwd" ? "×" : ""}).`;
  return (
    <VizFigure
      viz="pass-routes"
      caption={
        <>
          <b className="num font-semibold text-ink-2">
            {num(overall, lang)}
            {mode === "fwd" ? "×" : ""}
          </b>{" "}
          {mode === "fwd" ? "pass quality" : unit}, league{" "}
          <span className="num">
            {num(league, lang)}
            {mode === "fwd" ? "×" : ""}
          </span>
          .{" "}
          {compact ? null : (
            <>
              Width: number of passes.{" "}
              {mode === "fwd"
                ? "Colour: how often the route ends in a high-threat central cell, grey rarely, green often."
                : "Colour: xA per chance, grey low, green high."}{" "}
              {mode === "fwd" ? null : "Dashed: set piece; solid: open play. "}
              {showAll || full.length <= TOP_ROUTES ? "All" : "The busiest"}{" "}
              <span className="num">{num(groups.length, lang)}</span> routes
              {mode === "fwd" ? (
                <>
                  {" "}
                  with at least <span className="num">{num(MIN_ROUTE_PASSES, lang)}</span> passes
                </>
              ) : null}{" "}
              (<span className="num">{num(shownPasses, lang)}</span> of <span className="num">{num(total, lang)}</span>
              ).
              <span className="sr-only"> The table lists every route.</span>
            </>
          )}
        </>
      }
      table={{
        caption: summary,
        head: ["Route", "Passes", mode === "fwd" ? "Pass quality (×)" : "xA per chance", "Kind"],
        rows: all.map((g) => [
          `${ZONE_NAME(g.from)} → ${ZONE_NAME(g.to)}`,
          g.passes,
          num(shown(g, routeValue(g, leagueHotShare)), lang),
          g.kind === "fwd" ? "forward pass" : g.kind === "sp" ? "set piece" : "open play",
        ]),
      }}
    >
      <svg
        viewBox="-2 -2 109 72"
        role="img"
        aria-label={summary}
        className={cx("block h-auto w-full rounded-lg bg-[var(--pitch)]", compact ? "max-w-[420px]" : "max-w-[640px]")}
        data-player={player}
        data-mode={mode}
        data-routes={groups.length}
        data-total-routes={full.length}
        data-view={showAll ? "all" : "top"}
      >
        <defs>
          <marker
            id={`route-head-${uid}`}
            viewBox="0 0 10 10"
            refX="2"
            refY="5"
            markerWidth="4.2"
            markerHeight="4.2"
            markerUnits="userSpaceOnUse"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 z" fill="var(--ink)" stroke="var(--bg)" strokeWidth="0.8" />
          </marker>
        </defs>
        <g fill="none" stroke="var(--pitch-line)" strokeWidth="0.3">
          <rect x="0" y="0" width="105" height="68" />
          <line x1={52.5} x2={52.5} y1="0" y2="68" />
          <rect x={84 * PX} y={22 * PY} width={16 * PX} height={56 * PY} />
          <rect x="0" y={22 * PY} width={16 * PX} height={56 * PY} />
          {thirdX.map((x) => (
            <line
              key={x}
              x1={x * PX}
              x2={x * PX}
              y1="0"
              y2="68"
              strokeDasharray="0.8 0.8"
              stroke="var(--pitch-faint)"
            />
          ))}
          {[20, 40, 60, 80].map((y) => (
            <line
              key={y}
              x1="0"
              x2="105"
              y1={y * PY}
              y2={y * PY}
              strokeDasharray="0.8 0.8"
              stroke="var(--pitch-faint)"
            />
          ))}
        </g>
        {[...groups].reverse().map((g) => (
          <Arrow
            key={`${g.kind}-${g.from}-${g.to}`}
            g={g}
            maxN={maxN}
            top={top}
            thirdX={thirdX}
            uid={uid}
            leagueHotShare={leagueHotShare}
          />
        ))}
      </svg>
      {full.length > TOP_ROUTES && (
        <button
          type="button"
          aria-pressed={showAll}
          onClick={() => setShowAll((v) => !v)}
          data-role="route-toggle"
          className="mt-2 inline-flex min-h-9 items-center rounded-lg border border-line-strong bg-surface-2 px-3 text-[12.5px] font-semibold text-ink-2 hover:bg-surface-3 hover:text-ink"
        >
          {showAll ? (
            <>
              Show the busiest <span className="num ml-1">{num(TOP_ROUTES, lang)}</span>
            </>
          ) : (
            <>
              Show all routes (<span className="num">{num(full.length, lang)}</span>)
            </>
          )}
        </button>
      )}
      {!compact && (
        <div className="mt-2 flex items-center gap-2 text-[11.5px] text-ink-3" aria-hidden="true">
          <span>{mode === "fwd" ? "rarely central" : "low xA"}</span>
          <span
            className="h-2 w-28 rounded-full"
            style={{ background: `linear-gradient(90deg, ${seqColor(0)}, ${seqColor(0.5)}, ${seqColor(1)})` }}
          />
          <span>{mode === "fwd" ? "often central" : "high xA"}</span>
        </div>
      )}
    </VizFigure>
  );
});

/** League xA per chance, over every player's chance routes. */
export function leagueXaPerChance(routes: Record<string, RouteRow[]>): number {
  let n = 0;
  let s = 0;
  for (const rows of Object.values(routes))
    for (const r of rows)
      if (r[0] !== "fwd") {
        n += r[3];
        s += r[4];
      }
  return n ? s / n : 0;
}
