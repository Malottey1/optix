// The chances panel of the Player Console and its evidence drawer. Figures come from ui.json
// players[].profile.chances; the drawer's pitch, breakdown and table come from the team's lazy
// players-<code>.json (one row per key pass: where it started and ended, the kind of situation,
// the pass type, its xA and what the shot it set up became). Each table row's play button opens
// the Match Hub at that match and clock (#/match/<id>?t=<clock_sec>). Coordinates appear only
// under "View data".
import { useState } from "react";
import { Link } from "react-router";
import { PitchLines, PX, PY } from "../../components/pitch/Pitch";
import { Segmented } from "../../components/ui/segmented";
import { Sheet } from "../../components/ui/sheet";
import { chanceRows, matchOfEvent, type ChanceRow, type TeamLists } from "../../data/matches";
import { Icon } from "../../icons";
import { num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import type { ChanceKind, PlayerRow, ProfilesMeta } from "../../types/ui";
import { fill } from "../hub/parts";
import { Stat, WithLists } from "./PositionPanels";

export type ChanceTab = "all" | "set" | "open";
const KINDS: ChanceKind[] = ["corner", "free_kick", "throw_in", "set_piece", "open_play"];
const KIND_COLOR: Record<ChanceKind, string> = {
  corner: "var(--revise)",
  free_kick: "var(--away)",
  throw_in: "var(--home)",
  set_piece: "var(--muted-accent)",
  open_play: "var(--accent)",
};
const RESULT_KEY: Record<string, Key> = {
  goal: "res_goal",
  saved: "res_saved",
  blocked: "res_blocked",
  off_target: "res_off_target",
};

/** The rows of one tab (pure, unit-tested): set pieces are every kind but open play. */
export const chancesOf = (rows: readonly ChanceRow[], tab: ChanceTab) =>
  rows.filter((r) => (tab === "all" ? true : tab === "open" ? r[4] === "open_play" : r[4] !== "open_play"));

/** The Match Hub link of one chance: its match, opened at the pass's clock. */
export const playLink = (r: ChanceRow) => `/match/${matchOfEvent(r[0])}?t=${r[1]}`;

function ChancePitch({ rows, label }: { rows: readonly ChanceRow[]; label: string }) {
  return (
    <svg viewBox="-2 -2 109 72" role="img" aria-label={label} className="block h-auto w-full" data-chance-pitch>
      <PitchLines />
      {rows.map((r) => {
        const c = KIND_COLOR[r[4]];
        return (
          <g key={r[0]} data-chance={r[0]} data-kind={r[4]}>
            <line x1={r[8] * PX} y1={r[9] * PY} x2={r[10] * PX} y2={r[11] * PY} stroke={c} strokeWidth={0.55} />
            <circle cx={r[8] * PX} cy={r[9] * PY} r={0.6} fill={c} />
            <circle
              cx={r[10] * PX}
              cy={r[11] * PY}
              r={1.3}
              fill={r[7] === "goal" ? c : "var(--surface-1)"}
              stroke={c}
              strokeWidth={0.45}
            />
          </g>
        );
      })}
    </svg>
  );
}

function DrawerBody({ p, meta, lists }: { p: PlayerRow; meta: ProfilesMeta; lists: TeamLists }) {
  const { t, lang } = useT();
  const [tab, setTab] = useState<ChanceTab>("all");
  const c = p.profile!.chances;
  const all = chanceRows(lists, p.id);
  const rows = chancesOf(all, tab);
  const kinds = KINDS.filter((k) => all.some((r) => r[4] === k));
  return (
    <div className="flex flex-col gap-4" data-chance-drawer={p.id}>
      <p className="text-[14px] leading-snug text-ink-2" data-role="chance-sentence">
        {fill(t("ch_sentence"), {
          name: p.name,
          n: num(c.total, lang),
          sp: num(c.set_piece, lang),
          op: num(c.open_play, lang),
        })}
      </p>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-chance-tiles>
        <Stat label={t("ch_total")} value={num(c.total, lang)} />
        <Stat label={t("ch_sp")} value={num(c.set_piece, lang)} />
        <Stat label={t("ch_op")} value={num(c.open_play, lang)} />
        <Stat
          label={t("ch_xa_per")}
          value={num(c.xa_per, lang)}
          sub={fill(t("ch_league"), { v: num(meta.league_chances.xa_per, lang) })}
        />
      </dl>
      <div>
        <Segmented<ChanceTab>
          label={t("ch_title")}
          name="chance-tab"
          value={tab}
          onChange={setTab}
          options={[
            { value: "all", label: t("ch_all") },
            { value: "set", label: t("ch_sp") },
            { value: "open", label: t("ch_op") },
          ]}
          className="mb-2"
        />
        <ChancePitch rows={rows} label={`${p.name}: ${t("ch_title")} ${rows.length}`} />
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-2" data-legend>
          {kinds.map((k) => (
            <li key={k} className="inline-flex items-center gap-1.5">
              <span className="h-1 w-4 rounded-full" style={{ background: KIND_COLOR[k] }} aria-hidden="true" />
              {t(`ch_kind_${k}` as Key)}
            </li>
          ))}
          <li className="inline-flex items-center gap-1.5">
            <svg viewBox="-2 -2 4 4" className="h-3 w-3" aria-hidden="true">
              <circle r="1.4" fill="var(--surface-1)" stroke="var(--ink-2)" strokeWidth="0.5" />
            </svg>
            {t("ch_legend_shot")}
          </li>
        </ul>
      </div>
      <section aria-labelledby="ch-breakdown-h">
        <h3 id="ch-breakdown-h" className="mb-1.5 text-[13px] font-semibold text-ink">
          {t("ch_breakdown")}
        </h3>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-[12.5px] sm:grid-cols-3" data-chance-breakdown>
          {[
            ...KINDS.filter((k) => k !== "set_piece" || c.kinds.set_piece > 0).map(
              (k) => [`ch_kind_${k}` as Key, c.kinds[k], k] as const,
            ),
            ["ch_key", c.total, "key"] as const,
            ["ch_prog", c.progressive, "progressive"] as const,
            ["ch_fwd", c.forward, "forward"] as const,
          ].map(([k, v, id]) => (
            <div key={id} className="flex justify-between gap-2 border-b border-line py-1" data-breakdown={id}>
              <dt className="text-ink-2">{t(k)}</dt>
              <dd className="num m-0 font-semibold text-ink">{num(v, lang)}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section aria-labelledby="ch-list-h">
        <h3 id="ch-list-h" className="mb-1.5 text-[13px] font-semibold text-ink">
          {t("ch_list")}
        </h3>
        <div className="max-h-[320px] overflow-y-auto" tabIndex={0} data-scroll-region aria-labelledby="ch-list-h">
          <table className="w-full border-collapse text-[12.5px]" data-chance-table>
            <thead className="sticky top-0 bg-surface-1">
              <tr className="text-left text-[11px] text-ink-3">
                <th scope="col" className="py-1 pr-2 font-semibold">
                  {t("ch_minute")}
                </th>
                <th scope="col" className="py-1 pr-2 font-semibold">
                  {t("ch_type")}
                </th>
                <th scope="col" className="py-1 pr-2 font-semibold">
                  {t("ch_pass")}
                </th>
                <th scope="col" className="py-1 pr-2 text-right font-semibold">
                  xA
                </th>
                <th scope="col" className="py-1 pr-2 font-semibold">
                  {t("ch_result")}
                </th>
                <th scope="col" className="py-1 font-semibold">
                  <span className="sr-only">{t("ch_play")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]} className="border-t border-line" data-chance-row={r[0]}>
                  <td className="num py-1 pr-2 text-ink">{num(r[3], lang)}&#8242;</td>
                  <td className="py-1 pr-2 text-ink-2">{t(`ch_kind_${r[4]}` as Key)}</td>
                  <td className="py-1 pr-2 text-ink-2">{t(`pt_${r[5]}` as Key)}</td>
                  <td className="num py-1 pr-2 text-right text-ink">{num(r[6], lang)}</td>
                  <td className="py-1 pr-2 text-ink-2">{r[7] ? t(RESULT_KEY[r[7]] ?? "res_off_target") : "–"}</td>
                  <td className="py-1">
                    <Link
                      to={playLink(r)}
                      data-play={r[0]}
                      aria-label={fill(t("ch_play_label"), { t: `${num(r[3], lang)}′` })}
                      className="inline-grid h-8 w-8 place-items-center rounded-full border border-line text-ink-2 hover:border-accent-line hover:text-ink"
                    >
                      <Icon name="play" size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <p className="text-[12.5px] leading-snug text-ink-2" data-role="what-this-shows">
        {t("ch_what")}
      </p>
      <details className="text-[12px] text-ink-3">
        <summary className="cursor-pointer select-none py-1 font-semibold text-ink-2">{t("view_data")}</summary>
        <div className="max-h-[240px] overflow-auto" tabIndex={0} data-scroll-region aria-label={t("view_data")}>
          <table className="w-full border-collapse text-[11.5px]">
            <thead>
              <tr className="text-left">
                <th scope="col">id</th>
                <th scope="col">x0</th>
                <th scope="col">y0</th>
                <th scope="col">x1</th>
                <th scope="col">y1</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]}>
                  <td>
                    <code>{r[0]}</code>
                  </td>
                  <td className="num">{num(r[8], lang)}</td>
                  <td className="num">{num(r[9], lang)}</td>
                  <td className="num">{num(r[10], lang)}</td>
                  <td className="num">{num(r[11], lang)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

export function ChancesPanel({ p, meta }: { p: PlayerRow; meta: ProfilesMeta }) {
  const { t, lang } = useT();
  const [open, setOpen] = useState(false);
  const c = p.profile?.chances;
  if (!c || c.total === 0) return <p className="text-[13px] text-ink-3">{t("ch_none")}</p>;
  return (
    <>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-viz="chances-panel">
        <Stat label={t("ch_total")} value={num(c.total, lang)} />
        <Stat label={t("ch_sp")} value={num(c.set_piece, lang)} />
        <Stat label={t("ch_op")} value={num(c.open_play, lang)} />
        <Stat
          label={t("ch_xa_per")}
          value={num(c.xa_per, lang)}
          sub={fill(t("ch_league"), { v: num(meta.league_chances.xa_per, lang) })}
        />
      </dl>
      <button
        type="button"
        onClick={() => setOpen(true)}
        data-open-chances
        className="mt-3 inline-flex min-h-[40px] items-center gap-2 rounded-full border border-line-strong bg-surface-2 px-4 text-[13px] font-semibold text-ink hover:border-accent-line"
      >
        <Icon name="evidence-drawer" size={16} />
        {t("ch_open")}
      </button>
      <Sheet
        open={open}
        onOpenChange={setOpen}
        id="chance-evidence"
        eyebrow={
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5">
            <Icon name="pass" size={14} />
            {t("ch_title")}
          </span>
        }
        title={<span className="display text-[24px]">{p.name}</span>}
        closeLabel={t("close")}
        width="sm:max-w-[720px]"
        bottomOnPhone
      >
        {open && <WithLists code={p.team}>{(l) => <DrawerBody p={p} meta={meta} lists={l} />}</WithLists>}
      </Sheet>
    </>
  );
}
