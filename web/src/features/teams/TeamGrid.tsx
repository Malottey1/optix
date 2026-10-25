// #/teams: one card per club (badge, name, matches played and the five fingerprint chips), each a
// link to its Team Board. The kits note appears once, as a page footnote.
import { Link } from "react-router";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { useData } from "../../data/context";
import { num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { FingerprintChips } from "./parts";

export default function TeamGrid() {
  const m = useData();
  const { t, lang } = useT();
  return (
    <div className="flex flex-col gap-flow" data-page="teams">
      <h1 className="display text-[28px] font-semibold leading-none text-ink">{t("teams_title")}</h1>
      <ul className="grid grid-cols-1 gap-flow sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
        {m.ui.teams.teams.map((team) => (
          <li key={team.code}>
            <Link
              to={`/teams/${team.code}`}
              data-team={team.code}
              data-budget="team-card"
              className="flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface-1 pad transition-colors hover:border-line-strong"
            >
              <div className="flex items-center gap-3">
                <TeamBadge code={team.code} size={56} named />
                <div className="min-w-0">
                  <h2 className="truncate text-[17px] font-semibold text-ink">{team.name}</h2>
                  <p className="text-[12.5px] text-ink-3">
                    <span className="num font-semibold text-ink-2">{num(team.matches, lang)}</span>{" "}
                    {t("matches_played")}
                  </p>
                </div>
              </div>
              <FingerprintChips team={team} />
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-[12px] text-ink-3">{t("teams_kits_note")}</p>
    </div>
  );
}
