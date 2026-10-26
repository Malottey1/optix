// Home's "For you" row, shown only while this browser follows something (state/favourites.ts): the
// fixtures of followed clubs (and starred fixtures), then the followed players with their season
// goals and assists (forwards, midfielders) or minutes and pass completion (defenders, keepers),
// each with its star. Numbers are read from the fixture index and ui.json; no accounts anywhere.
import { Link } from "react-router";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { FavStar } from "../../components/ui/fav";
import { useData } from "../../data/context";
import { useFixtures } from "../../data/matchContext";
import { num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import { favCount, useFavourites } from "../../state/favourites";
import type { Lang, PlayerRow } from "../../types/ui";
import { FixtureRow, followedFixture } from "../fixtures/FixturesPage";
import { fill } from "../hub/parts";

const MAX_FIXTURES = 4;

function playerLine(p: PlayerRow, t: (k: Key) => string, lang: Lang) {
  if (p.position === "FW" || p.position === "MF")
    return fill(t("fy_ga"), { g: num(p.goals, lang), a: num(p.assists, lang) });
  return fill(t("fy_apps"), { m: num(p.profile?.minutes_whole ?? 0, lang), p: `${num(p.pass_completion, lang)}%` });
}

export function ForYou() {
  const m = useData();
  const { t, lang } = useT();
  const favs = useFavourites();
  const index = useFixtures();
  if (favCount(favs) === 0) return null;
  const names = index.data?.teams ?? {};
  const fixtures = (index.data?.fixtures ?? [])
    .filter((f) => followedFixture(f, favs.fixtures, favs.teams))
    .slice(0, MAX_FIXTURES);
  const players = favs.players.map((id) => m.ui.players.find((p) => p.id === id)).filter((p): p is PlayerRow => !!p);
  return (
    <section
      aria-labelledby="for-you-h"
      data-for-you
      className="rounded-2xl border border-accent-line bg-surface-1 pad elev-1"
    >
      <h2 id="for-you-h" className="mb-3 text-[16px] font-semibold text-ink">
        {t("for_you")}
      </h2>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {fixtures.length > 0 && (
          <div className="min-w-0">
            <h3 className="eyebrow mb-2">{t("for_you_fixtures")}</h3>
            <ul className="flex flex-col gap-2" data-for-you-fixtures>
              {fixtures.map((f) => (
                <FixtureRow key={f.id} f={f} names={names} />
              ))}
            </ul>
          </div>
        )}
        {players.length > 0 && (
          <div className="min-w-0">
            <h3 className="eyebrow mb-2">{t("for_you_players")}</h3>
            <ul className="flex flex-col gap-2" data-for-you-players>
              {players.map((p) => (
                <li key={p.id} className="relative">
                  <FavStar kind="players" id={p.id} name={p.name} className="absolute right-2 top-2 z-10 h-9 w-9" />
                  <Link
                    to={`/players/${p.id}`}
                    data-for-you-player={p.id}
                    className="flex min-h-[56px] items-center gap-3 rounded-xl border border-line bg-surface-2 py-2 pl-3 pr-12 hover:border-line-strong"
                  >
                    <TeamBadge code={p.team} size={28} named />
                    <span className="min-w-0">
                      <span className="block truncate text-[14px] font-semibold text-ink">{p.name}</span>
                      <span className="block truncate text-[12px] text-ink-3">
                        {t(`pos_${p.position}` as Key)} · {playerLine(p, t, lang)}
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
