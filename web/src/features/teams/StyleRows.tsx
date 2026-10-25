// "Style against the league" (Team Board): one row per fingerprint measure (Tempo, Press, Passing,
// Territory, Counters): the team's value against the league average, a bold bar in the club accent
// over a thin neutral league bar, both on ONE scale per measure running from the lowest to the
// highest team in the league, and a plain-words chip computed from the numbers only (rule below,
// tolerance from ui teams.style_rule). Never verdict or heat colours. Definitions in a tooltip and in
// "View data".
import { num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import type { StyleLabel, TeamProfile } from "../../types/ui";
import { FINGERPRINT, ViewData } from "./parts";

export type StyleChip = "highest" | "lowest" | "above" | "below" | "average";

/** The rows of one team (pure, unit-tested; tools/check_web.py recomputes the same in Python).
 * chip: highest / lowest only for a unique extreme among the league's teams; otherwise about
 * average when |value - league| <= tolerance_rel x league, else above / below. Bar positions are
 * fractions of the measure's [lowest team, highest team] range. */
export function styleRows(teams: readonly TeamProfile[], team: TeamProfile, toleranceRel: number) {
  return FINGERPRINT.flatMap((id) => {
    const l = team.labels.find((x) => x.id === id);
    if (!l || l.value == null || l.league == null) return [];
    const all = teams.map((x) => x.labels.find((y) => y.id === id)?.value).filter((v): v is number => v != null);
    const lo = Math.min(...all);
    const hi = Math.max(...all);
    const pos = (v: number) => (hi > lo ? (v - lo) / (hi - lo) : 0.5);
    const top = all.filter((v) => v === hi).length === 1 && l.value === hi;
    const bottom = all.filter((v) => v === lo).length === 1 && l.value === lo;
    const chip: StyleChip = top
      ? "highest"
      : bottom
        ? "lowest"
        : Math.abs(l.value - l.league) <= toleranceRel * Math.abs(l.league)
          ? "average"
          : l.value > l.league
            ? "above"
            : "below";
    return [
      {
        id,
        label: l,
        value: l.value,
        league: l.league,
        lo,
        hi,
        team: pos(l.value),
        base: pos(l.league),
        chip,
        n: all.length,
      },
    ];
  });
}

const NAME: Record<string, Key> = {
  tempo: "st_tempo",
  press: "st_press",
  directness: "st_passing",
  territory: "st_territory",
  counter: "st_counters",
};

const fmt = (l: StyleLabel, v: number, lang: Parameters<typeof num>[1]) =>
  l.unit === "%" ? `${num(v, lang)}%` : num(v, lang);

export function StyleRows({
  team,
  teams,
  toleranceRel,
}: {
  team: TeamProfile;
  teams: readonly TeamProfile[];
  toleranceRel: number;
}) {
  const { t, lang } = useT();
  const rows = styleRows(teams, team, toleranceRel);
  const accent = `var(--team-${team.code.toLowerCase()})`;
  const chipText = (c: StyleChip, n: number) => t(`st_chip_${c}` as Key).replace("{n}", num(n, lang));
  return (
    <figure className="m-0" data-viz="style-rows" data-team={team.code}>
      <div className="mb-2 flex items-center gap-4 text-[12px] text-ink-3" aria-hidden="true">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: accent }} />
          {team.code}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-ink-3" />
          {t("st_league")}
        </span>
      </div>
      <ul className="flex flex-col gap-3">
        {rows.map((r) => (
          <li
            key={r.id}
            data-style-row={r.id}
            data-value={r.value}
            data-chip={r.chip}
            title={r.id === "tempo" ? `${t("st_tempo_unit")}. ${r.label.rule}` : r.label.rule}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <span className="text-[13.5px] font-semibold text-ink">
                {t(NAME[r.id] ?? "st_tempo")}
                {r.id === "tempo" && <span className="sr-only">, {t("st_tempo_unit")}</span>}
              </span>
              <span className="flex items-baseline gap-2">
                <span
                  className="rounded-full border border-line px-2 py-0.5 text-[11.5px] font-semibold text-ink-2"
                  data-chip-text
                >
                  {chipText(r.chip, r.n)}
                </span>
                <span className="num text-[15px] font-bold" style={{ color: accent }}>
                  {fmt(r.label, r.value, lang)}
                </span>
                <span className="sr-only">{t("st_vs")}</span>
                <span aria-hidden="true" className="h-3 w-px self-center bg-line-strong" />
                <span className="num text-[13px] text-ink-2">{fmt(r.label, r.league, lang)}</span>
              </span>
            </div>
            <div className="mt-1.5 flex flex-col gap-1" aria-hidden="true">
              <span className="relative block h-2.5 rounded-full bg-surface-3">
                <span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${Math.max(2, r.team * 100)}%`, background: accent }}
                />
              </span>
              <span className="relative block h-1 rounded-full bg-surface-3">
                <span
                  className="absolute inset-y-0 left-0 rounded-full bg-ink-3"
                  style={{ width: `${Math.max(2, r.base * 100)}%` }}
                />
              </span>
            </div>
          </li>
        ))}
      </ul>
      <figcaption className="mt-2 text-[12px] text-ink-3">{t("st_caption")}</figcaption>
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
              <th scope="col" className="py-1 pr-2 text-right">
                {t("tbl_league")}
              </th>
              <th scope="col" className="py-1 pr-2 text-right">
                {t("st_lowest")}
              </th>
              <th scope="col" className="py-1 text-right">
                {t("st_highest")}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-line">
                <th scope="row" className="py-1 pr-2 font-normal">
                  {t(NAME[r.id] ?? "st_tempo")}
                </th>
                <td className="num py-1 pr-2 text-right">{fmt(r.label, r.value, lang)}</td>
                <td className="num py-1 pr-2 text-right">{fmt(r.label, r.league, lang)}</td>
                <td className="num py-1 pr-2 text-right">{fmt(r.label, r.lo, lang)}</td>
                <td className="num py-1 text-right">{fmt(r.label, r.hi, lang)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="mt-2 flex flex-col gap-1">
          {rows.map((r) => (
            <li key={r.id}>{r.label.rule}</li>
          ))}
        </ul>
      </ViewData>
    </figure>
  );
}
