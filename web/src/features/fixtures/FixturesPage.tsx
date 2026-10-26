// #/fixtures: every match that exists in the data (matches/index.json), the showcase replay pinned
// first, then the season grouped by matchweek. Each row links to its Match Hub. Filters: team and
// status. There are no future fixtures: the data has none.
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { FavStar, FollowingChip } from "../../components/ui/fav";
import { Segmented } from "../../components/ui/segmented";
import { useFavourites } from "../../state/favourites";
import { useFixtures } from "../../data/matchContext";
import type { Fixture } from "../../data/matches";
import { Icon } from "../../icons";
import { cx } from "../../lib/cx";
import { num } from "../../lib/format";
import { useT } from "../../lib/i18n";

type StatusFilter = "all" | "live" | "final";

export function filterFixtures(rows: readonly Fixture[], team: string, status: StatusFilter): Fixture[] {
  return rows.filter(
    (f) => (team === "all" || f.home === team || f.away === team) && (status === "all" || f.status === status),
  );
}

/** A fixture shows under "Following" when it is starred or a followed team plays in it (pure). */
export const followedFixture = (f: Fixture, fixtures: readonly string[], teams: readonly string[]) =>
  fixtures.includes(f.id) || teams.includes(f.home) || teams.includes(f.away);

/** Rows grouped by matchweek in index order; the live replay is its own group, first. */
export function groupFixtures(rows: readonly Fixture[]): { key: string; week: number | null; rows: Fixture[] }[] {
  const out: { key: string; week: number | null; rows: Fixture[] }[] = [];
  for (const f of rows) {
    const key = f.status === "live" ? "live" : `mw${f.matchweek}`;
    let g = out.find((x) => x.key === key);
    if (!g) out.push((g = { key, week: f.status === "live" ? null : f.matchweek, rows: [] }));
    g.rows.push(f);
  }
  return out;
}

export function FixtureRow({ f, names }: { f: Fixture; names: Record<string, string | undefined> }) {
  const { t, lang } = useT();
  const live = f.status === "live";
  return (
    <li className="relative">
      <FavStar
        kind="fixtures"
        id={f.id}
        name={`${names[f.home] ?? f.home} – ${names[f.away] ?? f.away}`}
        className="absolute right-2 top-2 z-10 h-9 w-9"
      />
      <Link
        to={`/match/${f.id}`}
        data-fixture={f.id}
        data-status={f.status}
        className={cx(
          "grid min-h-[56px] grid-cols-[1fr_auto_1fr] items-center gap-x-3 gap-y-1 rounded-xl border py-2 pl-3 pr-12 transition-colors sm:grid-cols-[1fr_auto_1fr_auto]",
          live ? "border-accent-line bg-accent-soft" : "border-line bg-surface-2 hover:border-line-strong",
        )}
      >
        <span className="flex min-w-0 items-center justify-end gap-2 text-right">
          <span className="truncate text-[14px] font-semibold text-ink">
            <span className="sm:hidden">{f.home}</span>
            <span className="hidden sm:inline">{names[f.home] ?? f.home}</span>
          </span>
          <TeamBadge code={f.home} size={28} named />
        </span>
        <span className="display num min-w-[64px] text-center text-[20px] font-semibold leading-none text-ink">
          {num(f.score[0], lang)}–{num(f.score[1], lang)}
        </span>
        <span className="flex min-w-0 items-center gap-2">
          <TeamBadge code={f.away} size={28} named />
          <span className="truncate text-[14px] font-semibold text-ink">
            <span className="sm:hidden">{f.away}</span>
            <span className="hidden sm:inline">{names[f.away] ?? f.away}</span>
          </span>
        </span>
        <span className="col-span-3 flex items-center justify-center gap-2 text-[12px] text-ink-3 sm:col-span-1 sm:justify-end">
          <span
            className={cx(
              "inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold",
              live ? "bg-accent text-accent-ink" : "border border-line text-ink-2",
            )}
          >
            {live && <Icon name="live" size={14} />}
            {live ? t("status_live") : t("status_final")}
          </span>
          <span>
            <span className="num font-semibold text-ink-2">{num(f.insights, lang)}</span> {t("n_insights")} ·{" "}
            <span className="num font-semibold text-ink-2">{num(f.patterns, lang)}</span> {t("n_patterns")}
          </span>
        </span>
      </Link>
    </li>
  );
}

export default function FixturesPage() {
  const { t } = useT();
  const { data, error } = useFixtures();
  const [team, setTeam] = useState("all");
  const [status, setStatus] = useState<StatusFilter>("all");
  const favs = useFavourites();
  const [following, setFollowing] = useState(false);
  const groups = useMemo(
    () =>
      data
        ? groupFixtures(
            filterFixtures(data.fixtures, team, status).filter(
              (f) => !following || followedFixture(f, favs.fixtures, favs.teams),
            ),
          )
        : [],
    [data, team, status, following, favs],
  );
  if (error) throw error;
  return (
    <div className="mx-auto flex w-full max-w-[960px] flex-col gap-4" data-page="fixtures">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="display text-[28px] font-semibold leading-none text-ink">{t("fixtures_title")}</h1>
        {data && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-[12px] font-semibold text-ink-3">
              {t("filter_team")}
              <select
                id="fixtures-team"
                value={team}
                onChange={(e) => setTeam(e.target.value)}
                className="h-9 rounded-full border border-line bg-surface-2 px-3 text-[13px] text-ink"
              >
                <option value="all">{t("all_teams")}</option>
                {Object.entries(data.teams).map(([code, name]) => (
                  <option key={code} value={code}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <FollowingChip on={following} count={favs.fixtures.length + favs.teams.length} onChange={setFollowing} />
            <Segmented
              label={t("filter_status")}
              name="fixtures-status"
              size="md"
              value={status}
              onChange={setStatus}
              options={[
                { value: "all", label: t("all") },
                { value: "live", label: t("status_live") },
                { value: "final", label: t("status_final") },
              ]}
            />
          </div>
        )}
      </header>
      {!data && <div className="h-[420px] animate-pulse rounded-2xl bg-surface-2" aria-busy="true" />}
      {data && !groups.length && <p className="text-[14px] text-ink-3">{t("no_fixtures")}</p>}
      {groups.map((g) => (
        <section
          key={g.key}
          aria-labelledby={`fx-${g.key}`}
          data-group={g.key}
          className="rounded-2xl border border-line bg-surface-1 p-3 sm:p-4"
        >
          <h2 id={`fx-${g.key}`} className="eyebrow mb-2">
            {g.week === null ? t("status_live") : `${t("matchweek")} ${g.week} · ${g.rows[0]!.date}`}
          </h2>
          <ul className="flex flex-col gap-2">
            {g.rows.map((f) => (
              <FixtureRow key={f.id} f={f} names={data!.teams} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
