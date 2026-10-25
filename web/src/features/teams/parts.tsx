// Team Grid and Team Board pieces. Every number comes from ui.json (engine/profiles.py,
// engine/style_labels.py, agents/dashboard_data.py lineups and patterns); lanes are named from the
// attacker's point of view. Text-light: tables live in closed "View data" sections.
import { Link } from "react-router";
import { Jersey } from "../../charts/LineupPitch";
import { PitchLines, PY } from "../../components/pitch/Pitch";
import { Sheet } from "../../components/ui/sheet";
import { Icon, patternIcon, styleLabelIcon } from "../../icons";
import { cx } from "../../lib/cx";
import { num, pct, signed } from "../../lib/format";
import { patternLabel, useT, type Key } from "../../lib/i18n";
import { sliceArc } from "../../lib/viz";
import type { LineupNode, PlayerRow, SignatureRow, StyleLabel, TeamProfile } from "../../types/ui";

export const FINGERPRINT = ["tempo", "press", "directness", "territory", "counter"] as const;
const LANE_KEYS: Key[] = ["lane_lf", "lane_lhs", "lane_c", "lane_rhs", "lane_rf"];
export const laneKey = (lanes: readonly string[], lane: string): Key => LANE_KEYS[lanes.indexOf(lane)] ?? "lane_c";

export const fill = (s: string, vars: Record<string, string>) =>
  s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

/** The label's word in the current language: typical, or the direction against the league. */
export function labelWord(l: StyleLabel, t: (k: Key) => string): string {
  return l.direction === "typical" ? t("sl_typical") : t(`sl_${l.id}_${l.direction}` as Key);
}

export function FingerprintChips({ team, size = "sm" }: { team: TeamProfile; size?: "sm" | "md" }) {
  const { t } = useT();
  const labels = FINGERPRINT.map((id) => team.labels.find((l) => l.id === id)).filter(Boolean) as StyleLabel[];
  return (
    <ul className="flex flex-wrap gap-1.5" data-fingerprint={team.code}>
      {labels.map((l) => {
        const typical = l.direction === "typical";
        return (
          <li
            key={l.id}
            data-chip={l.id}
            data-label={l.id}
            data-direction={l.direction}
            className={cx(
              "inline-flex items-center gap-1.5 rounded-full border font-semibold",
              size === "sm" ? "px-2 py-0.5 text-[11.5px]" : "px-2.5 py-1 text-[12.5px]",
              typical ? "border-line text-ink-3" : "border-muted/40 bg-muted-soft text-ink",
            )}
          >
            <Icon name={styleLabelIcon(l.id, l.direction)} size={14} />
            <span className="font-medium text-ink-3">{t(`fp_${l.id}` as Key)}</span>
            {labelWord(l, t)}
          </li>
        );
      })}
    </ul>
  );
}

/** Style pizza: one slice per fingerprint metric, radius = the team's value over the league's,
 * the ring = the league (ratio 1). Values and league figures are in View data. */
export function StylePizza({ team }: { team: TeamProfile }) {
  const { t, lang } = useT();
  const labels = FINGERPRINT.map((id) => team.labels.find((l) => l.id === id)).filter(Boolean) as StyleLabel[];
  const R0 = 14;
  const RING = 58;
  const ratio = (l: StyleLabel) => (l.value != null && l.league ? Math.min(1.6, l.value / l.league) : 0);
  return (
    <figure className="m-0" data-viz="team-pizza" data-team={team.code}>
      <div className="grid grid-cols-1 items-center gap-3 sm:grid-cols-[minmax(0,240px)_1fr]">
        <svg
          viewBox="0 0 200 200"
          className="mx-auto block w-full max-w-[240px]"
          role="img"
          aria-label={t("board_style")}
        >
          <circle
            cx="100"
            cy="100"
            r={R0 + RING}
            fill="none"
            stroke="var(--ink-3)"
            strokeDasharray="3 3"
            strokeWidth="1"
          />
          {labels.map((l, i) => {
            const r1 = R0 + ratio(l) * RING;
            return (
              <path
                key={l.id}
                data-slice={l.id}
                d={sliceArc(100, 100, R0, r1, i, labels.length)}
                fill={l.direction === "typical" ? "var(--ink-3)" : "var(--muted-accent)"}
                fillOpacity={l.direction === "typical" ? 0.45 : 0.85}
              />
            );
          })}
        </svg>
        <ol className="flex flex-col gap-1 text-[12.5px]">
          {labels.map((l) => (
            <li key={l.id} className="flex items-center gap-2">
              <Icon name={styleLabelIcon(l.id, l.direction)} size={16} className="text-ink-3" />
              <span className="text-ink-2">{t(`fp_${l.id}` as Key)}</span>
            </li>
          ))}
        </ol>
      </div>
      <figcaption className="mt-2 text-[12px] text-ink-3">{t("board_style_note")}</figcaption>
      <ViewData>
        <table className="w-full border-collapse text-left text-[12px]">
          <thead className="text-ink-3">
            <tr>
              <th scope="col" className="py-1 pr-2">
                {t("tbl_measure")}
              </th>
              <th scope="col" className="py-1 pr-2 text-right">
                {t("tbl_value")}
              </th>
              <th scope="col" className="py-1 text-right">
                {t("tbl_league")}
              </th>
            </tr>
          </thead>
          <tbody>
            {labels.map((l) => (
              <tr key={l.id} className="border-t border-line">
                <th scope="row" className="py-1 pr-2 font-normal">
                  {t(`fp_${l.id}` as Key)}
                </th>
                <td className="num py-1 pr-2 text-right">
                  {num(l.value, lang)}
                  {l.unit}
                </td>
                <td className="num py-1 text-right">
                  {num(l.league, lang)}
                  {l.unit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ViewData>
    </figure>
  );
}

export function ViewData({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  return (
    <details className="mt-2 text-[12px] text-ink-3" data-view-data>
      <summary className="cursor-pointer select-none py-1 font-semibold text-ink-2">{t("view_data")}</summary>
      <div className="overflow-x-auto pt-1">{children}</div>
    </details>
  );
}

/** "Where they attack": the pitch with five lane bands shaded by the lift of the team's share of
 * final-third entries over the league (diverging: orange above, blue below), the lift printed. */
export function LaneLiftStrip({ team, lanes }: { team: TeamProfile; lanes: readonly string[] }) {
  const { t, lang } = useT();
  const max = Math.max(1, ...lanes.map((l) => Math.abs(team.entry_lanes[l]?.effect ?? 0)));
  const soft = team.soft_lane;
  return (
    <figure className="m-0" data-viz="lane-lift" data-team={team.code}>
      <svg viewBox="-1 -1 107 70" className="block h-auto w-full" role="img" aria-label={t("lane_lift_label")}>
        <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
        {lanes.map((l, i) => {
          const e = team.entry_lanes[l]?.effect ?? 0;
          return (
            <g key={l} data-lane={l} data-value={e}>
              <rect
                x="0"
                y={i * 20 * PY}
                width="105"
                height={20 * PY}
                fill={e >= 0 ? "var(--heat-rise)" : "var(--heat-fall)"}
                fillOpacity={(Math.abs(e) / max) * 0.75}
              />
              <text x="3" y={i * 20 * PY + 8.4} fontSize="4" fill="var(--ink)" fontWeight="600">
                {t(LANE_KEYS[i]!)}
              </text>
              <text x="102" y={i * 20 * PY + 8.4} fontSize="4.4" fill="var(--ink)" fontWeight="700" textAnchor="end">
                {signed(e, lang)}
              </text>
            </g>
          );
        })}
        <PitchLines ground={false} />
      </svg>
      <figcaption className="mt-1.5 text-[12px] text-ink-3" data-lane-ok="lane-lift">
        {t("lane_lift_label")} · {t("heat_attacking")} →
      </figcaption>
      {soft ? (
        <p className="mt-1.5 text-[13px] text-ink-2" data-soft-lane={soft.lane}>
          {fill(t("soft_lane_note"), {
            lane: t(laneKey(lanes, soft.lane)),
            rate: pct(soft.rate, lang),
            league: pct(soft.league, lang),
          })}
        </p>
      ) : (
        <p className="mt-1.5 text-[12px] text-ink-3" data-soft-lane="none">
          {t("no_soft_lane")}
        </p>
      )}
      <ViewData>
        <table className="w-full min-w-[420px] border-collapse text-left text-[12px]" data-table="lanes">
          <thead className="text-ink-3">
            <tr>
              <th scope="col" className="py-1 pr-2">
                {t("tbl_lane")}
              </th>
              <th scope="col" className="py-1 pr-2 text-right">
                {t("tbl_share")}
              </th>
              <th scope="col" className="py-1 pr-2 text-right">
                {t("tbl_league")}
              </th>
              <th scope="col" className="py-1 pr-2 text-right">
                {t("tbl_lift")}
              </th>
              <th scope="col" className="py-1 text-right">
                {t("tbl_completion")}
              </th>
            </tr>
          </thead>
          <tbody>
            {lanes.map((l) => {
              const a = team.entry_lanes[l]!;
              const c = team.completion_conceded[l]!;
              return (
                <tr key={l} className="border-t border-line">
                  <th scope="row" className="py-1 pr-2 font-normal">
                    {t(laneKey(lanes, l))}
                  </th>
                  <td className="num py-1 pr-2 text-right">{num(a.share, lang)}</td>
                  <td className="num py-1 pr-2 text-right">{num(a.league, lang)}</td>
                  <td className="num py-1 pr-2 text-right">{signed(a.effect, lang)}</td>
                  <td className="num py-1 text-right">
                    {num(c.rate, lang)} <span className="text-ink-3">({num(c.league, lang)})</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </ViewData>
    </figure>
  );
}

export function SignatureList({
  code,
  rows,
  all,
  open,
  setOpen,
}: {
  code: string;
  rows: SignatureRow[];
  all: (SignatureRow & { signature: boolean })[];
  open: boolean;
  setOpen: (o: boolean) => void;
}) {
  const { t, lang } = useT();
  const line = (r: SignatureRow) => (
    <>
      <Icon name={patternIcon(r.family)} size={18} className="shrink-0 text-ink-2" />
      <b className="min-w-0 flex-1 truncate font-semibold text-ink">{patternLabel(r.family, lang)}</b>
      <span className="num text-ink-2">{pct(r.share, lang)}</span>
      {r.interval && r.interval[0] != null && (
        <span className="num text-[11.5px] text-ink-3">
          {num(r.interval[0], lang)}–{num(r.interval[1], lang)}
        </span>
      )}
    </>
  );
  return (
    <div data-signature-patterns={code}>
      {rows.length ? (
        <ul className="flex flex-col gap-1.5 text-[13px]">
          {rows.slice(0, 3).map((r) => (
            <li key={r.family} data-family={r.family} className="flex items-center gap-2">
              {line(r)}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[12.5px] text-ink-3">{t("signature_none")}</p>
      )}
      {all.length > 0 && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-2 rounded-full border border-line px-3 py-1.5 text-[12px] font-semibold text-ink-2 hover:border-line-strong hover:text-ink"
        >
          {t("show_all")} ({num(all.length, lang)})
        </button>
      )}
      <Sheet
        open={open}
        onOpenChange={setOpen}
        id="team-patterns"
        title={fill(t("all_patterns"), { team: code })}
        closeLabel={t("close")}
        bottomOnPhone
      >
        <ul className="flex flex-col gap-2 text-[13px]" data-all-patterns={code}>
          {all.map((r) => (
            <li
              key={r.family}
              data-family={r.family}
              className="flex flex-wrap items-center gap-2 border-b border-line pb-2"
            >
              {line(r)}
              <span className="w-full text-[12px] text-ink-3">
                <span className="num">{num(r.matches, lang)}</span>/<span className="num">{num(r.played, lang)}</span>{" "}
                {t("signature_share")} · {t("others")} <span className="num">{pct(r.others_share, lang)}</span>
                {r.signature ? ` · ${t("signature_tag")}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </Sheet>
    </div>
  );
}

export const initials = (name: string) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0]!.toUpperCase())
    .slice(0, 2)
    .join("");

export function Avatar({ name, code, size = 56 }: { name: string; code: string; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="inline-grid shrink-0 place-items-center rounded-full font-display font-bold text-[#05080f]"
      style={{ width: size, height: size, fontSize: size * 0.38, background: `var(--team-${code.toLowerCase()})` }}
    >
      {initials(name)}
    </span>
  );
}

/** The lineup node's mini-profile: bottom sheet on a phone, side sheet above. */
export function PlayerSheet({
  code,
  node,
  player,
  name,
  onClose,
}: {
  code: string;
  node: LineupNode | null;
  player: PlayerRow | undefined;
  name: string;
  onClose: () => void;
}) {
  const { t, lang } = useT();
  return (
    <Sheet
      open={node !== null}
      onOpenChange={(o) => !o && onClose()}
      id="player-sheet"
      title={name}
      eyebrow={code}
      closeLabel={t("close")}
      width="sm:max-w-[420px]"
      bottomOnPhone
    >
      {node && (
        <div className="flex flex-col gap-4" data-player-sheet={node.id}>
          <div className="flex items-center gap-4">
            <Avatar name={name} code={code} />
            <div>
              <div className="text-[13px] text-ink-2">{t(`pos_${node.position}` as Key)}</div>
              <div className="mt-1 flex items-center gap-2 text-[13px] text-ink-3">
                <Jersey code={code} shirt={node.shirt} size={28} />
                {t("number_short")} <span className="num font-semibold text-ink">{node.shirt}</span>
              </div>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-2">
            {(
              [
                ["season_goals", player?.goals ?? 0],
                ["season_assists", player?.assists ?? 0],
              ] as const
            ).map(([k, v]) => (
              <div key={k} className="rounded-xl border border-line bg-surface-2 px-3 py-2">
                <dt className="text-[12px] text-ink-3">{t(k)}</dt>
                <dd className="display num text-[26px] font-semibold leading-none text-ink">{num(v, lang)}</dd>
              </div>
            ))}
          </dl>
          <Link
            to={`/players/${node.id}`}
            data-ledger-link={node.id}
            className="rounded-xl bg-accent px-4 py-3 text-center text-[13px] font-bold tracking-wide text-accent-ink hover:brightness-110"
          >
            {t("view_ledger")}
          </Link>
        </div>
      )}
    </Sheet>
  );
}
