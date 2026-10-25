// #/players: the Player Deck. One card per player (initials avatar, badge, name, position, season
// two stats by position, deckStats), each a link to the Player Console. Filters by team and position, search by
// name. Four columns at 1440, three at 1024, two at phone width.
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { FavStar, FollowingChip } from "../../components/ui/fav";
import { useFavourites } from "../../state/favourites";
import { useData } from "../../data/context";
import { num, pct } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import type { Lang, PlayerRow } from "../../types/ui";
import { Avatar } from "../teams/parts";

const POSITIONS = ["GK", "DF", "MF", "FW"] as const;

/** Pure filter (unit-tested): team code or "", position or "", case- and accent-blind name search. */
export function filterPlayers(rows: readonly PlayerRow[], team: string, position: string, q: string): PlayerRow[] {
  const fold = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const needle = fold(q.trim());
  return rows.filter(
    (p) =>
      (!team || p.team === team) &&
      (!position || p.position === position) &&
      (!needle || fold(p.name).includes(needle)),
  );
}

/** The two card stats of a position (FW/MF goals and assists, DF tackles and interceptions, GK
 * saves and save rate), each with its label key and display; the next available stat stands in when
 * a profile part is missing (goals and assists exist for everyone). Pure, unit-tested. */
export function deckStats(p: PlayerRow): [Key, (lang: Lang) => string][] {
  const d = p.profile?.defence;
  const k = p.profile?.keeper;
  const ga: [Key, (lang: Lang) => string][] = [
    ["season_goals", (l) => num(p.goals, l)],
    ["season_assists", (l) => num(p.assists, l)],
  ];
  if (p.position === "DF" && d)
    return [
      ["def_tackles", (l) => num(d.tackles, l)],
      ["def_interceptions", (l) => num(d.interceptions, l)],
    ];
  if (p.position === "GK" && k)
    return [
      ["gk_saves", (l) => num(k.saves, l)],
      ["gk_save_pct", (l) => pct(k.save_pct, l)],
    ];
  return ga;
}

const ORDER = { GK: 0, DF: 1, MF: 2, FW: 3 } as Record<string, number>;

function Select({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: [string, string][];
}) {
  return (
    <label htmlFor={id} className="flex flex-col gap-1 text-[12px] font-semibold text-ink-3">
      {label}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-xl border border-line bg-surface-2 px-3 text-[14px] font-semibold text-ink"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function PlayerDeck() {
  const m = useData();
  const { t, lang } = useT();
  const [team, setTeam] = useState("");
  const [position, setPosition] = useState("");
  const [q, setQ] = useState("");
  const followed = useFavourites((f) => f.players);
  const [following, setFollowing] = useState(false);
  const sorted = useMemo(
    () =>
      [...m.ui.players].sort(
        (a, b) =>
          a.team.localeCompare(b.team) || (ORDER[a.position] ?? 9) - (ORDER[b.position] ?? 9) || a.shirt - b.shirt,
      ),
    [m],
  );
  const rows = filterPlayers(sorted, team, position, q).filter((p) => !following || followed.includes(p.id));
  return (
    <div className="flex flex-col gap-flow" data-page="players">
      <h1 className="display text-[28px] font-semibold leading-none text-ink">{t("deck_title")}</h1>
      <div className="flex flex-wrap items-end gap-3" role="search">
        <Select
          id="deck-team"
          label={t("filter_team")}
          value={team}
          onChange={setTeam}
          options={[["", t("all_teams")], ...m.ui.teams.teams.map((x) => [x.code, x.name] as [string, string])]}
        />
        <Select
          id="deck-position"
          label={t("filter_position")}
          value={position}
          onChange={setPosition}
          options={[["", t("all_positions")], ...POSITIONS.map((p) => [p, t(`pos_${p}` as Key)] as [string, string])]}
        />
        <label
          htmlFor="deck-search"
          className="flex min-w-[200px] flex-1 flex-col gap-1 text-[12px] font-semibold text-ink-3"
        >
          {t("deck_search")}
          <input
            id="deck-search"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            autoComplete="off"
            className="h-11 rounded-xl border border-line bg-surface-2 px-3 text-[14px] text-ink placeholder:text-ink-3"
          />
        </label>
        <span className="pb-1">
          <FollowingChip on={following} count={followed.length} onChange={setFollowing} />
        </span>
        <p className="pb-3 text-[12.5px] text-ink-3" aria-live="polite">
          <span className="num font-semibold text-ink-2">{num(rows.length, lang)}</span> {t("deck_count")}
        </p>
      </div>
      {rows.length ? (
        <ul className="grid grid-cols-2 gap-3 sm:gap-flow lg:grid-cols-3 xl:grid-cols-4" data-deck>
          {rows.map((p) => (
            <li key={p.id} className="relative">
              <FavStar kind="players" id={p.id} name={p.name} className="absolute right-2.5 top-2.5 z-10" />
              <Link
                to={`/players/${p.id}`}
                data-player={p.id}
                data-budget="card"
                className="flex h-full min-h-[44px] flex-col gap-3 rounded-2xl border border-line bg-surface-1 p-3 transition-colors hover:border-line-strong sm:p-4"
              >
                <div className="flex items-center gap-3">
                  <Avatar name={p.name} code={p.team} size={44} />
                  <TeamBadge code={p.team} size={28} named />
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-[15px] font-semibold text-ink">{p.name}</h2>
                  <p className="text-[12.5px] text-ink-3">{t(`pos_${p.position}` as Key)}</p>
                </div>
                <dl className="mt-auto flex gap-4 text-[12px] text-ink-3" data-deck-stats={p.position}>
                  {deckStats(p).map(([k, v]) => (
                    <div key={k} className="flex flex-col-reverse">
                      <dt className="mt-1">{t(k)}</dt>
                      <dd className="display num m-0 text-[22px] font-semibold leading-none text-ink">{v(lang)}</dd>
                    </div>
                  ))}
                </dl>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-xl border border-dashed border-line-strong px-4 py-6 text-center text-[13px] text-ink-3">
          {t("deck_empty")}
        </p>
      )}
    </div>
  );
}
