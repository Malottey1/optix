// #/match/:id: the Match Hub. Live replay (the showcase): the existing live console inside the hub
// frame. Final (a played season match): the Post-Match Recap, in order: scoreline header, turning
// points, heat maps, pattern and insight cards (capped per family), the matchup only when the
// Verifier passed a lane claim for this fixture, the event log and a link to the claim ledger.
// #/match/:id/ledger lists every verification attempt in the file.
import { lazy, Suspense, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { HeatPitch } from "../../charts/HeatPitch";
import { MismatchCrosshairs } from "../../components/viz/MismatchCrosshairs";
import { useData } from "../../data/context";
import { useFixtures, useMatchFile } from "../../data/matchContext";
import { eventLog, evidenceRows, expandCard, SHOWCASE_ID, type MatchFile } from "../../data/matches";
import { Icon } from "../../icons";
import { num } from "../../lib/format";
import { useT } from "../../lib/i18n";
import {
  capCards,
  ClaimTable,
  EventLog,
  fill,
  HubDrawer,
  HubHeader,
  RecapCard,
  Section,
  SectionNav,
  TurningPoints,
  type Selection,
} from "./parts";

const LivePage = lazy(() => import("../live/LivePage"));

function LiveFrame() {
  const { t } = useT();
  return (
    // at the 1600 px+ demo layout the frame row sits in the page's top padding, so every live
    // visual stays on the first screen at 1600x900 (tools/check_web.check_first_screen)
    <div className="relative flex flex-col gap-2 wide:gap-0" data-hub="live">
      <div className="flex items-center gap-2 text-[12px] font-semibold text-ink-3 wide:absolute wide:-top-[22px] wide:left-0 wide:h-5">
        <Link
          to="/fixtures"
          className="inline-flex min-h-[32px] items-center rounded-full px-2 hover:text-ink wide:min-h-0"
        >
          ← {t("back_fixtures")}
        </Link>
        <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2 py-0.5 text-accent-ink">
          <Icon name="live" size={14} />
          {t("status_live")}
        </span>
      </div>
      <Suspense fallback={<div className="h-[600px] animate-pulse rounded-2xl bg-surface-2" />}>
        <LivePage />
      </Suspense>
    </div>
  );
}

function Matchup({ file }: { file: MatchFile }) {
  const m = useData();
  const { t } = useT();
  const blocks = (file.matchups ?? []).flatMap((mu) => {
    const h = m.ui.teams.head_to_head.find((x) => x.attacker === mu.attacker && x.defender === mu.defender);
    const d = m.ui.teams.teams.find((x) => x.code === mu.defender);
    return h && d ? [{ mu, h, d }] : [];
  });
  if (!blocks.length) return null;
  return (
    <Section id="matchup" title={t("hub_matchup")}>
      <div data-lane-ok="matchup">
        <p className="mb-2 text-[12px] text-ink-3">
          {t("matchup_note")} {t("mx_legend")}
        </p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {blocks.map(({ mu, h, d }) => (
            <div key={mu.claim_id} data-matchup={`${mu.attacker}-${mu.defender}`}>
              <MismatchCrosshairs
                h={h}
                defender={d}
                lanes={m.ui.teams.lanes}
                compact
                claimLane={String((mu.metrics as Record<string, unknown>).lane ?? "")}
                claimId={mu.claim_id}
                legend={false}
              />
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}

function FinalRecap({ file }: { file: MatchFile }) {
  const { t, lang } = useT();
  const [sel, setSel] = useState<Selection>(null);
  const cards = useMemo(() => file.insights.map((c) => expandCard(file, c)), [file]);
  const shown = useMemo(() => capCards(cards), [cards]);
  const rows = useMemo(() => evidenceRows(file), [file]);
  const events = useMemo(() => eventLog(file), [file]);
  const codes = [file.header.home.code, file.header.away.code];
  const nav: [string, string][] = [
    ["turning", t("hub_turning")],
    ["heat", t("hub_heat")],
    ["cards", t("hub_cards")],
    ...(file.matchups ? ([["matchup", t("hub_matchup")]] as [string, string][]) : []),
    ["log", t("hub_log")],
  ];
  return (
    <div className="flex flex-col gap-flow" data-page="hub" data-hub="final" data-match={file.match_id}>
      <h1 className="sr-only">
        {file.header.home.name} – {file.header.away.name}
      </h1>
      <div className="flex items-center text-[12px] font-semibold text-ink-3">
        <Link to="/fixtures" className="inline-flex min-h-[32px] items-center rounded-full px-2 hover:text-ink">
          ← {t("back_fixtures")}
        </Link>
      </div>
      <HubHeader file={file} nav={<SectionNav items={nav} />} />
      <Section id="turning" title={t("hub_turning")}>
        <TurningPoints file={file} onSelect={setSel} />
      </Section>
      <div className="grid grid-cols-1 items-start gap-flow lg:grid-cols-12">
        <div className="min-w-0 lg:col-span-6">
          <Section id="heat" title={t("hub_heat")}>
            <div className="mx-auto w-full max-w-[600px]">
              <HeatPitch
                grid={file.heat}
                teams={file.heat.teams as Record<string, number[][]>}
                codes={codes}
                initialTeam={codes[0]}
              />
            </div>
          </Section>
        </div>
        <div className="min-w-0 lg:col-span-6">
          <Section id="cards" title={t("hub_cards")}>
            <p className="mb-2 text-[12px] text-ink-3">
              {fill(t("recap_shown"), { k: num(shown.length, lang), n: num(file.stream_counts.insights, lang) })}
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              {shown.map((ins) => (
                <RecapCard key={ins.insight_id} file={file} ins={ins} onSelect={setSel} />
              ))}
            </div>
          </Section>
        </div>
      </div>
      <Matchup file={file} />
      <Section id="log" title={t("hub_log")} budget="log">
        <EventLog file={file} events={events} onSelect={setSel} />
      </Section>
      <Link
        to={`/match/${file.match_id}/ledger`}
        data-ledger-link
        className="self-start rounded-full border border-line px-4 py-2 text-[13px] font-semibold text-ink-2 hover:border-accent-line hover:text-ink"
      >
        {t("hub_ledger")}: {t("hub_ledger_link")} →
      </Link>
      <HubDrawer file={file} cards={cards} rows={rows} selection={sel} onClose={() => setSel(null)} />
    </div>
  );
}

function Missing() {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-3" data-page="hub" data-hub="missing">
      <p className="text-[14px] text-ink-2">{t("match_missing")}</p>
      <Link to="/fixtures" className="text-[13px] font-semibold text-accent">
        ← {t("back_fixtures")}
      </Link>
    </div>
  );
}

function Pending() {
  return <div className="h-[640px] animate-pulse rounded-2xl bg-surface-2" aria-busy="true" />;
}

export default function MatchHub() {
  const { id = "" } = useParams();
  // the showcase replay needs nothing beyond the bundle the app already loaded
  return id === SHOWCASE_ID ? <LiveFrame /> : <FinalHub id={id} />;
}

function FinalHub({ id }: { id: string }) {
  const index = useFixtures();
  const row = index.data?.fixtures.find((f) => f.id === id);
  const file = useMatchFile(row && row.status === "final" ? id : null);
  if (index.error) throw index.error;
  if (file.error) throw file.error;
  if (!index.data) return <Pending />;
  if (!row) return <Missing />;
  if (row.status === "live") return <LiveFrame />;
  return file.data ? <FinalRecap file={file.data} /> : <Pending />;
}

export function MatchLedger() {
  const { id = "" } = useParams();
  const { t } = useT();
  const index = useFixtures();
  const row = index.data?.fixtures.find((f) => f.id === id);
  const file = useMatchFile(row && row.status === "final" ? id : null);
  if (index.data && (!row || row.status === "live"))
    return row ? (
      <div data-page="ledger" className="text-[14px] text-ink-2">
        <Link to="/tech" className="font-semibold text-accent">
          {t("hub_ledger")} →
        </Link>
      </div>
    ) : (
      <Missing />
    );
  if (!file.data) return <Pending />;
  return (
    <div className="flex flex-col gap-flow" data-page="ledger" data-match={id}>
      <Link to={`/match/${id}`} className="self-start text-[12px] font-semibold text-ink-3 hover:text-ink">
        ← {file.data.header.home.code}–{file.data.header.away.code}
      </Link>
      <h1 className="display text-[26px] font-semibold text-ink">{t("hub_ledger")}</h1>
      <ClaimTable file={file.data} />
    </div>
  );
}
