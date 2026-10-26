// #/match/:id: the Match Hub. Live replay (the showcase): the existing live console inside the hub
// frame. Final (a played season match): the Post-Match Recap, in order: scoreline header, turning
// points, heat maps, pattern and insight cards (capped per family), the matchup only when the
// Verifier passed a lane claim for this fixture, the event log and a link to the claim ledger.
// #/match/:id/ledger lists every verification attempt in the file.
// Fan view (state/view.ts, the default): story first, i.e. scoreline, turning points, lineups, one heat
// map and at most five cards picked by lib/personalize.ts; the matchup, event log and ledger link
// are Analyst view. Following a player or choosing a focus metric filters the cards in both views.
import { lazy, Suspense, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { HeatPitch } from "../../charts/HeatPitch";
import { useData } from "../../data/context";
import { useFixtures, useMatchFile } from "../../data/matchContext";
import { eventLog, evidenceRows, expandCard, SHOWCASE_ID, xiRows, type MatchFile } from "../../data/matches";
import { Icon } from "../../icons";
import { useT } from "../../lib/i18n";
import { useMedia } from "../../lib/useMedia";
import { MatchLineups } from "../../charts/MatchLineups";
import { PlayerSheet } from "../teams/parts";
import type { LineupNode } from "../../types/ui";
import { InsightsPanel } from "./InsightsPanel";
import { FocusButton, FollowChip, MetricPicker, ModeToggle } from "../../components/personal/controls";
import { FinalMetricReadout, FinalPlayerSoFar } from "../../components/personal/panels";
import { involvedFromLog } from "../../data/events";
import { cx } from "../../lib/cx";
import { personalize } from "../../lib/personalize";
import { useFavourites } from "../../state/favourites";
import { useView } from "../../state/view";
import { Matchup, shownMatchups } from "./MatchupStrips";
import {
  capCards,
  ClaimTable,
  EventLog,
  HubDrawer,
  HubHeader,
  Section,
  SectionNav,
  TurningPoints,
  type Selection,
} from "./parts";

const LivePage = lazy(() => import("../live/LivePage"));

/** The hub's personalization row: view switch, the followed player's chip, the focus metric. */
function HubControls({ final, name, className }: { final: boolean; name: string | null; className?: string }) {
  return (
    <div className={cx("flex flex-wrap items-center gap-2", className)} data-hub-controls>
      <ModeToggle />
      {name && <FollowChip name={name} />}
      <MetricPicker final={final} />
    </div>
  );
}

function LiveFrame() {
  const { t } = useT();
  const m = useData();
  const focus = useView((s) => (s.focus && m.timeline.players[s.focus] ? s.focus : null));
  return (
    // at the 1600 px+ demo layout the frame row sits in the page's top padding, so every live
    // visual stays on the first screen at 1600x900 (tools/check_web.check_first_screen)
    <div className="relative flex flex-col gap-2 wide:gap-0" data-hub="live">
      <div className="flex flex-wrap items-center gap-2 text-[12px] font-semibold text-ink-3 wide:absolute wide:-top-[22px] wide:left-0 wide:right-0 wide:h-5 wide:flex-nowrap">
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
        <HubControls
          final={false}
          name={focus ? m.timeline.players[focus]!.name : null}
          className="ml-auto wide:[&_[data-following]]:min-h-0 wide:[&_button]:min-h-0 wide:[&_button]:py-0 wide:[&_button]:h-5"
        />
      </div>
      <Suspense fallback={<div className="h-[600px] animate-pulse rounded-2xl bg-surface-2" />}>
        <LivePage />
      </Suspense>
    </div>
  );
}

/** The hub's two-column breakpoint: from here the insights panel is a sticky side panel. */
export const HUB_WIDE = "(min-width: 1100px)";

function FinalRecap({ file }: { file: MatchFile }) {
  const m = useData();
  const { t } = useT();
  const wide = useMedia(HUB_WIDE);
  const [params] = useSearchParams();
  const atClock = params.get("t") != null && /^\d+$/.test(params.get("t")!) ? Number(params.get("t")) : undefined;
  const [sel, setSel] = useState<Selection>(null);
  const [open, setOpen] = useState<{ id: string; code: string } | null>(null);
  const cards = useMemo(() => file.insights.map((c) => expandCard(file, c)), [file]);
  const shown = useMemo(() => capCards(cards), [cards]);
  const { mode, metric: rawMetric } = useView();
  const fan = mode === "fan";
  const metric = rawMetric === "momentum" ? rawMetric : null;
  const focus = useView((s) => (s.focus && file.players[s.focus] ? s.focus : null));
  const clubs = useFavourites((s) => s.teams);
  const involved = useMemo(() => (focus ? involvedFromLog(file) : {}), [file, focus]);
  const picked = useMemo(
    () => personalize(shown, { mode, clubs, players: focus ? [focus] : [], metric }, involved),
    [shown, mode, clubs, focus, metric, involved],
  );
  const at = atClock ?? file.duration_sec;
  const rows = useMemo(() => evidenceRows(file), [file]);
  const events = useMemo(() => eventLog(file), [file]);
  const codes = [file.header.home.code, file.header.away.code];
  const nav: [string, string][] = [
    ...(wide ? [] : ([["insights", t("panel_title")]] as [string, string][])),
    ["turning", t("hub_turning")],
    ["lineups", t("hub_lineups")],
    ["heat", t("hub_heat")],
    ...(!fan && shownMatchups(file, m.ui.teams).length ? ([["matchup", t("hub_matchup")]] as [string, string][]) : []),
    ...(fan ? [] : ([["log", t("hub_log")]] as [string, string][])),
  ];
  const panel = (
    <InsightsPanel
      file={file}
      cards={picked}
      onSelect={setSel}
      side={wide}
      fan={fan}
      empty={focus ? t("focus_none") : metric ? t("metric_feed_none") : undefined}
    />
  );
  const sheetRow = open
    ? xiRows(file, file.lineups.home.code === open.code ? "home" : "away").find((r) => r[0] === open.id)
    : undefined;
  const node: LineupNode | null = sheetRow
    ? {
        id: sheetRow[0],
        shirt: sheetRow[1],
        position: sheetRow[2],
        role: null,
        starts: 0,
        line: sheetRow[3],
        slot: sheetRow[4],
        of: sheetRow[5],
      }
    : null;
  return (
    <div
      className="flex flex-col gap-flow"
      data-page="hub"
      data-hub="final"
      data-view={mode}
      data-match={file.match_id}
    >
      <h1 className="sr-only">
        {file.header.home.name} – {file.header.away.name}
      </h1>
      <div className="flex items-center text-[12px] font-semibold text-ink-3">
        <Link to="/fixtures" className="inline-flex min-h-[32px] items-center rounded-full px-2 hover:text-ink">
          ← {t("back_fixtures")}
        </Link>
      </div>
      <div className="grid grid-cols-1 items-start gap-flow min-[1100px]:grid-cols-[minmax(0,62fr)_minmax(0,38fr)]">
        <div className="flex min-w-0 flex-col gap-flow" data-hub-column="main">
          <HubHeader
            file={file}
            fan={fan}
            nav={
              <>
                <HubControls
                  final
                  name={focus ? String(file.players[focus]![0]) : null}
                  className="mt-3 border-t border-line pt-2.5"
                />
                <SectionNav items={nav} />
              </>
            }
          />
          {(metric || focus) && (
            <div className="flex min-w-0 flex-col gap-flow" data-focus-panels>
              {metric && <FinalMetricReadout file={file} metric={metric} at={at} />}
              {focus && <FinalPlayerSoFar file={file} pid={focus} at={at} />}
            </div>
          )}
          {!wide && panel}
          <Section id="turning" title={t("hub_turning")}>
            <TurningPoints file={file} onSelect={setSel} />
          </Section>
          <Section id="lineups" title={t("hub_lineups")} budget="lineups">
            <MatchLineups file={file} onOpen={(id, code) => setOpen({ id, code })} />
          </Section>
          <Section id="heat" title={t("hub_heat")}>
            <div className="mx-auto w-full max-w-[640px]">
              <HeatPitch
                grid={file.heat}
                teams={file.heat.teams as Record<string, number[][]>}
                codes={codes}
                initialTeam={codes[0]}
              />
            </div>
          </Section>
          {!fan && (
            <>
              <Matchup file={file} />
              <Section id="log" title={t("hub_log")} budget="log">
                <EventLog file={file} events={events} onSelect={setSel} atClock={atClock} />
              </Section>
              <Link
                to={`/match/${file.match_id}/ledger`}
                data-ledger-link
                className="self-start rounded-full border border-line px-4 py-2 text-[13px] font-semibold text-ink-2 hover:border-accent-line hover:text-ink"
              >
                {t("hub_ledger")}: {t("hub_ledger_link")} →
              </Link>
            </>
          )}
        </div>
        {wide && (
          <div className="min-w-0 self-stretch" data-hub-column="side">
            {panel}
          </div>
        )}
      </div>
      <HubDrawer file={file} cards={cards} rows={rows} selection={sel} onClose={() => setSel(null)} />
      <PlayerSheet
        code={open?.code ?? ""}
        node={node}
        player={m.ui.players.find((p) => p.id === open?.id)}
        name={open ? String(file.players[open.id]?.[0] ?? open.id) : ""}
        onClose={() => setOpen(null)}
        actions={open ? <FocusButton id={open.id} /> : null}
      />
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
