// Position-aware Player Console panels, all from ui.json players[].profile (agents/player_profiles.py)
// and the team's lazy players-<code>.json lists. Defenders: defensive actions (season totals, per
// ninety, per hundred opposition final-third entries, percentile among same-position players with
// at least the minutes floor, drawn as bars around the peer median), the defensive action map and
// progressive passing. Goalkeepers: the shot-faced map in the keeper's frame, shot stopping and
// distribution. Where the event data cannot show something, a "Not available in event data" note
// links to the Tech page limits; nothing is filled with a zero.
import { useState } from "react";
import { Link } from "react-router";
import { PitchLines, PX, PY } from "../../components/pitch/Pitch";
import { defPoints, shotsFacedRows, type DefPoint, type ShotFacedRow, type TeamLists } from "../../data/matches";
import { useTeamLists } from "../../data/matchContext";
import { Icon, type IconName } from "../../icons";
import { cx } from "../../lib/cx";
import { num, pct } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import type { DefRate, PlayerRow, ProfilesMeta } from "../../types/ui";
import { fill } from "../hub/parts";

/** Tile: label under a large number. */
export function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex min-w-0 flex-col-reverse rounded-xl bg-surface-2 px-3 py-2.5">
      <dt className="mt-1 text-[11.5px] leading-tight text-ink-3">
        {label}
        {sub && <span className="mt-0.5 block text-[11px]">{sub}</span>}
      </dt>
      <dd className="display num m-0 text-[22px] font-bold leading-none text-ink">{value}</dd>
    </div>
  );
}

/** "Not available in event data" for one topic, linking to the Tech page limits. */
export function NotInData({ topic }: { topic: Key }) {
  const { t } = useT();
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-ink-3" data-not-in-data={topic}>
      <span className="font-semibold text-ink-2">{t(topic)}:</span>
      <span>{t("pp_na")}.</span>
      <Link to="/tech?s=limits" className="font-semibold text-accent hover:underline">
        {t("pp_na_link")} →
      </Link>
    </p>
  );
}

const RATE_KEY: Record<DefRate, Key> = {
  tackles: "def_tackles",
  interceptions: "def_interceptions",
  blocks: "def_blocks",
  clearances: "def_clearances",
  fouls: "def_fouls",
  contributions: "def_contributions",
};

/** The rows of the defensive actions panel (pure, unit-tested): totals, rates and peer percentile. */
export function defenceRows(p: PlayerRow, meta: ProfilesMeta) {
  const d = p.profile?.defence;
  if (!d) return [];
  return meta.rates.map((r) => ({
    rate: r,
    total: d[r],
    p90: d.p90?.[r] ?? null,
    p100: d.p100?.[r] ?? null,
    pctl: d.peer_pctl?.[r] ?? null,
  }));
}

export function DefensiveActions({ p, meta }: { p: PlayerRow; meta: ProfilesMeta }) {
  const { t, lang } = useT();
  const rows = defenceRows(p, meta);
  const pos = p.position as "DF" | "MF" | "FW";
  const peers = meta.peers[pos];
  const rated = rows.some((r) => r.p90 != null);
  return (
    <figure className="m-0" data-viz="defensive-actions" data-player={p.id}>
      <div className="overflow-x-auto" tabIndex={0} data-scroll-region aria-label={t("def_title")}>
        <table className="w-full min-w-[420px] border-collapse text-[12.5px]">
          <thead>
            <tr className="text-left text-[11px] font-semibold text-ink-3">
              <th scope="col" className="py-1.5 pr-2 font-semibold">
                <span className="sr-only">{t("def_title")}</span>
              </th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">
                {t("def_total")}
              </th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">
                {t("def_p90")}
              </th>
              <th scope="col" className="px-1 py-1.5 text-right font-semibold">
                {t("def_p100")}
              </th>
              <th scope="col" className="w-[34%] py-1.5 pl-2 font-semibold">
                {t("def_pctl")}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.rate} data-def-rate={r.rate} data-pctl={r.pctl ?? undefined} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-2 text-left font-semibold text-ink">
                  {t(RATE_KEY[r.rate])}
                </th>
                <td className="num px-1 py-1.5 text-right text-ink">{num(r.total, lang)}</td>
                <td className="num px-1 py-1.5 text-right text-ink-2">{num(r.p90, lang)}</td>
                <td className="num px-1 py-1.5 text-right text-ink-2">{num(r.p100, lang)}</td>
                <td className="py-1.5 pl-2">
                  <span className="flex items-center gap-2">
                    <span className="relative h-2.5 min-w-0 flex-1 rounded-full bg-surface-2" aria-hidden="true">
                      <span className="absolute inset-y-0 left-1/2 w-px bg-ink-3" />
                      {r.pctl != null && (
                        <span
                          className="absolute inset-y-0 rounded-full"
                          style={{
                            left: r.pctl >= 50 ? "50%" : `${r.pctl}%`,
                            width: `${Math.abs(r.pctl - 50)}%`,
                            background: r.pctl >= 50 ? "var(--heat-rise)" : "var(--heat-fall)",
                          }}
                        />
                      )}
                    </span>
                    <span className="num w-7 shrink-0 text-right font-semibold text-ink">{num(r.pctl, lang)}</span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="mt-2 flex flex-col gap-1 text-[11.5px] text-ink-3">
        {rated && peers ? (
          <span>
            {fill(t("pp_peers"), { pos: t(`pos_${pos}` as Key), n: num(meta.min_minutes, lang) })} (
            <span className="num">{num(peers.n, lang)}</span>). {t("def_bars_note")}
          </span>
        ) : (
          <span>{fill(t("def_floor"), { n: num(meta.min_minutes, lang) })}</span>
        )}
        <span data-contrib-def>{t("def_contrib_def")}</span>
      </figcaption>
    </figure>
  );
}

const POINT_ICON: Record<string, IconName> = {
  tackle: "tackle",
  interception: "interception",
  block: "shot",
  clearance: "possession-change",
};
const POINT_COLOR = ["var(--accent)", "var(--home)", "var(--revise)", "var(--away)"];
const POINT_COUNT: Record<string, DefRate> = {
  tackle: "tackles",
  interception: "interceptions",
  block: "blocks",
  clearance: "clearances",
};

function Marker({ kind, x, y, color }: { kind: number; x: number; y: number; color: string }) {
  const s = 1.3;
  if (kind === 0) return <circle cx={x} cy={y} r={s} fill={color} />;
  if (kind === 1) return <rect x={x - s} y={y - s} width={2 * s} height={2 * s} fill={color} />;
  if (kind === 2)
    return <path d={`M${x},${y - s * 1.3} L${x + s * 1.2},${y + s} L${x - s * 1.2},${y + s} z`} fill={color} />;
  return (
    <path
      d={`M${x - s},${y - s} L${x + s},${y + s} M${x + s},${y - s} L${x - s},${y + s}`}
      stroke={color}
      strokeWidth={0.7}
    />
  );
}

/** Points per type index (pure, unit-tested; must equal the profile counts). */
export const pointsByType = (pts: readonly DefPoint[], n: number) =>
  Array.from({ length: n }, (_, i) => pts.filter((q) => q[2] === i));

export function DefenceMap({ p, lists }: { p: PlayerRow; lists: TeamLists }) {
  const { t, lang } = useT();
  const types = lists.point_types as string[];
  const [on, setOn] = useState<boolean[]>(() => types.map(() => true));
  const pts = defPoints(lists, p.id);
  const d = p.profile?.defence;
  const per = pointsByType(pts, types.length);
  return (
    <figure className="m-0" data-viz="defence-map" data-player={p.id}>
      <div role="group" aria-label={t("def_map_types")} className="mb-2 flex flex-wrap gap-1.5">
        {types.map((k, i) => (
          <button
            key={k}
            type="button"
            aria-pressed={on[i]}
            data-point-type={k}
            onClick={() => setOn((v) => v.map((b, j) => (j === i ? !b : b)))}
            className={cx(
              "inline-flex min-h-[32px] items-center gap-1.5 rounded-full border px-3 text-[12px] font-semibold",
              on[i] ? "border-accent-line text-ink" : "border-line text-ink-3 opacity-70",
            )}
          >
            <svg viewBox="-2 -2 4 4" className="h-3 w-3" aria-hidden="true">
              <Marker kind={i} x={0} y={0} color={POINT_COLOR[i]!} />
            </svg>
            <Icon name={POINT_ICON[k] ?? "tackle"} size={14} />
            {t(RATE_KEY[POINT_COUNT[k] ?? "tackles"])}
            <span className="num text-ink-3">{num(d?.[POINT_COUNT[k] ?? "tackles"] ?? per[i]!.length, lang)}</span>
          </button>
        ))}
      </div>
      <svg
        viewBox="-2 -2 109 72"
        role="img"
        aria-label={`${p.name}: ${t("def_map")}, ${types.map((k, i) => `${t(RATE_KEY[POINT_COUNT[k] ?? "tackles"])} ${per[i]!.length}`).join(", ")}`}
        className="block h-auto w-full"
      >
        <PitchLines />
        {per.map((list, i) =>
          on[i] ? (
            <g key={i} data-points={types[i]} data-count={list.length}>
              {list.map((q, j) => (
                <Marker key={j} kind={i} x={q[0] * PX} y={q[1] * PY} color={POINT_COLOR[i]!} />
              ))}
            </g>
          ) : null,
        )}
      </svg>
      <figcaption className="mt-2 text-[11.5px] text-ink-3">{t("def_map_note")}</figcaption>
    </figure>
  );
}

export function PassingExtras({ p }: { p: PlayerRow }) {
  const { t, lang } = useT();
  const x = p.profile?.passing;
  if (!x) return null;
  const items: [Key, number, number | null | undefined][] = [
    ["pass_prog", x.progressive, x.p90?.progressive],
    ["pass_f3", x.into_final_third, x.p90?.into_final_third],
    ["pass_box", x.into_box, x.p90?.into_box],
  ];
  return (
    <dl className="grid grid-cols-3 gap-2" data-viz="passing-extras">
      {items.map(([k, v, r]) => (
        <Stat
          key={k}
          label={t(k)}
          value={num(v, lang)}
          sub={r != null ? `${num(r, lang)} ${t("def_p90").toLowerCase()}` : undefined}
        />
      ))}
    </dl>
  );
}

const SHOT_STYLE: Record<ShotFacedRow[4], { fill: string; stroke: string; key: Key }> = {
  goal: { fill: "var(--block)", stroke: "var(--block)", key: "res_goal" },
  saved: { fill: "var(--accent)", stroke: "var(--accent)", key: "res_saved" },
  blocked: { fill: "none", stroke: "var(--ink-2)", key: "res_blocked" },
  off_target: { fill: "none", stroke: "var(--ink-3)", key: "res_off_target" },
};
const RESULTS = ["goal", "saved", "blocked", "off_target"] as const;

/** Shots faced per result (pure, unit-tested against the keeper profile). */
export const shotsByResult = (rows: readonly ShotFacedRow[]) =>
  Object.fromEntries(RESULTS.map((r) => [r, rows.filter((s) => s[4] === r).length])) as Record<ShotFacedRow[4], number>;

export function ShotsFacedMap({ p, lists }: { p: PlayerRow; lists: TeamLists }) {
  const { t } = useT();
  const rows = shotsFacedRows(lists, p.id);
  const by = shotsByResult(rows);
  // the keeper's own half only: the shots all sit near the goal on the left
  return (
    <figure className="m-0" data-viz="shots-faced" data-player={p.id}>
      <svg
        viewBox="-2 -2 58 72"
        role="img"
        aria-label={`${p.name}: ${t("gk_map")} ${rows.length}, ${RESULTS.map((r) => `${t(SHOT_STYLE[r].key)} ${by[r]}`).join(", ")}`}
        className="mx-auto block h-auto w-full max-w-[420px]"
      >
        <clipPath id={`half-${p.id}`}>
          <rect x="-2" y="-2" width="56.5" height="72" />
        </clipPath>
        <g clipPath={`url(#half-${p.id})`}>
          <PitchLines thirds={false} />
        </g>
        {RESULTS.slice()
          .reverse()
          .map((r) => (
            <g key={r} data-result={r} data-count={by[r]}>
              {rows
                .filter((s) => s[4] === r)
                .map((s) => (
                  <circle
                    key={s[0]}
                    cx={s[2] * PX}
                    cy={s[3] * PY}
                    r={0.8 + Math.sqrt(s[5]) * 2.2}
                    fill={SHOT_STYLE[r].fill}
                    fillOpacity={r === "goal" || r === "saved" ? 0.85 : undefined}
                    stroke={SHOT_STYLE[r].stroke}
                    strokeWidth={0.35}
                  />
                ))}
            </g>
          ))}
      </svg>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2" data-legend>
        {RESULTS.map((r) => (
          <li key={r} className="inline-flex items-center gap-1.5">
            <svg viewBox="-2 -2 4 4" className="h-3 w-3" aria-hidden="true">
              <circle r="1.5" fill={SHOT_STYLE[r].fill} stroke={SHOT_STYLE[r].stroke} strokeWidth="0.5" />
            </svg>
            {t(SHOT_STYLE[r].key)}
          </li>
        ))}
      </ul>
      <figcaption className="mt-1 text-[11.5px] text-ink-3">{t("gk_map_note")}</figcaption>
    </figure>
  );
}

export function KeeperFigures({ p }: { p: PlayerRow }) {
  const { t, lang } = useT();
  const k = p.profile?.keeper;
  if (!k) return null;
  return (
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-viz="keeper-figures">
      <Stat label={t("gk_saves")} value={num(k.saves, lang)} />
      <Stat
        label={t("gk_map")}
        value={num(k.shots_faced, lang)}
        sub={`${t("gk_on_target")} ${num(k.on_target, lang)}`}
      />
      <Stat label={t("gk_save_pct")} value={pct(k.save_pct, lang)} />
      <Stat label={t("gk_clean")} value={num(k.clean_sheets, lang)} />
      <Stat label={t("gk_conceded")} value={num(k.conceded, lang)} />
      <Stat label={t("gk_xg_faced")} value={num(k.xg_faced, lang)} />
      <Stat label={t("gk_diff")} value={`${k.conceded_minus_xg > 0 ? "+" : ""}${num(k.conceded_minus_xg, lang)}`} />
    </dl>
  );
}

export function KeeperDistribution({ p, meta }: { p: PlayerRow; meta: ProfilesMeta }) {
  const { t, lang } = useT();
  const k = p.profile?.keeper;
  if (!k) return null;
  return (
    <>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-viz="keeper-distribution">
        <Stat label={t("gk_passes")} value={num(k.passes, lang)} />
        <Stat label={t("gk_completion")} value={pct(k.pass_completion, lang)} />
        <Stat label={t("gk_long")} value={pct(k.long_share, lang)} />
        <Stat label={t("gk_goal_kicks")} value={num(k.goal_kicks, lang)} />
      </dl>
      <p className="mt-2 text-[11.5px] text-ink-3">{fill(t("gk_long_def"), { m: num(meta.long_pass_m, lang) })}</p>
    </>
  );
}

/** Loads the team lists once for the panels that draw from them. */
export function WithLists({ code, children }: { code: string; children: (l: TeamLists) => React.ReactNode }) {
  const lists = useTeamLists(code);
  if (lists.error) return <p className="text-[13px] text-ink-3">{String(lists.error.message)}</p>;
  if (!lists.data) return <div className="aspect-[105/68] w-full animate-pulse rounded-xl bg-surface-2" />;
  return <>{children(lists.data)}</>;
}
