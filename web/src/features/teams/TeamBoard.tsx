// #/teams/:code: the Team Board, visual first. In order: identity header (badge, kit, the five
// fingerprint chips), the lineup pitch (most-used XI, by listed position) with a mini-profile per
// player, the style pizza against the league, where they attack (lane lift strip), the game-state
// slider (V3) and up to three signature patterns, with the rest in a drawer. Tables sit in closed
// "View data" sections.
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { Jersey, LineupPitch } from "../../charts/LineupPitch";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { StateSwaps } from "../../components/viz/StateSwaps";
import { useData } from "../../data/context";
import { useT } from "../../lib/i18n";
import { FingerprintChips, LaneLiftStrip, PlayerSheet, SignatureList } from "./parts";
import { StyleRows } from "./StyleRows";

function Block({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-h`} className="min-w-0 rounded-2xl border border-line bg-surface-1 pad">
      <h2 id={`${id}-h`} className="mb-3 text-[15px] font-semibold text-ink">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function TeamBoard() {
  const { code = "" } = useParams();
  const m = useData();
  const { t } = useT();
  const team = m.ui.teams.teams.find((x) => x.code === code.toUpperCase());
  const lineup = team ? m.ui.lineups[team.code] : undefined;
  const [open, setOpen] = useState<string | null>(null);
  const [allOpen, setAllOpen] = useState(false);
  const names = useMemo(() => Object.fromEntries(m.ui.players.map((p) => [p.id, p.name])), [m]);
  const timelineNames = m.timeline.players;
  if (!team || !lineup)
    return (
      <div data-page="team-board" className="flex flex-col gap-2">
        <p className="text-[14px] text-ink-2">{t("team_missing")}</p>
        <Link to="/teams" className="text-[13px] font-semibold text-accent">
          ← {t("back_teams")}
        </Link>
      </div>
    );
  const nameOf = (id: string) => names[id] ?? timelineNames[id]?.name ?? id;
  const allNames = Object.fromEntries(lineup.xi.map((n) => [n.id, nameOf(n.id)]));
  const node = lineup.xi.find((n) => n.id === open) ?? null;
  const fams = m.ui.patterns?.team_families?.[team.code] ?? [];
  return (
    <div className="flex flex-col gap-flow" data-page="team-board" data-team={team.code} data-budget="team-board">
      <Link to="/teams" className="self-start text-[12px] font-semibold text-ink-3 hover:text-ink">
        ← {t("back_teams")}
      </Link>
      <header className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-surface-1 pad">
        <TeamBadge code={team.code} size={72} />
        <div className="min-w-0 flex-1">
          <h1 className="display text-[30px] font-semibold leading-none text-ink">{team.name}</h1>
          <div className="mt-2">
            <FingerprintChips team={team} size="md" />
          </div>
        </div>
        <span className="hidden sm:block">
          <Jersey code={team.code} shirt={10} size={56} />
        </span>
      </header>
      <div className="grid grid-cols-1 items-start gap-flow xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-7">
          <Block id="lineup" title={`${t("board_lineup")} · ${lineup.label} ${t("by_listed_positions")}`}>
            <LineupPitch code={team.code} xi={lineup.xi} names={allNames} onOpen={setOpen} />
            <p className="mt-2 text-[12px] text-ink-3">{t("board_lineup_note")}</p>
          </Block>
        </div>
        <div className="flex min-w-0 flex-col gap-flow xl:col-span-5">
          <Block id="style" title={t("board_style")}>
            <StyleRows team={team} teams={m.ui.teams.teams} toleranceRel={m.ui.teams.style_rule.tolerance_rel} />
          </Block>
        </div>
      </div>
      <div className="grid grid-cols-1 items-start gap-flow lg:grid-cols-3">
        <Block id="attack" title={t("board_attack")}>
          <LaneLiftStrip team={team} lanes={m.ui.teams.lanes} />
        </Block>
        <Block id="states" title={t("board_states")}>
          <StateSwaps visuals={m.ui.visuals} codes={[team.code]} initial={team.code} compact />
        </Block>
        <Block id="signature" title={t("board_signature")}>
          <SignatureList
            code={team.code}
            rows={m.ui.patterns?.signature[team.code] ?? []}
            all={fams}
            open={allOpen}
            setOpen={setAllOpen}
          />
        </Block>
      </div>
      <PlayerSheet
        code={team.code}
        node={node}
        player={m.ui.players.find((p) => p.id === open)}
        name={open ? nameOf(open) : ""}
        onClose={() => setOpen(null)}
      />
    </div>
  );
}
