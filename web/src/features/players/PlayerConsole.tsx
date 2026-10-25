// #/players/:id: the Player Console. Header (initials avatar, name, number, position, team badge,
// whole minutes and two position stats), the pass map (one thin line per completed pass, the most
// progressive ones, coloured forward / progressive / key pass) with a chances tab drawn like the
// chance drawer, then the position panels (PositionPanels.tsx, ChanceDrawer.tsx): chances and the chance
// evidence drawer for forwards and midfielders, defensive actions, their map and progressive passing
// for defenders, shots faced, shot stopping and distribution for goalkeepers. The percentile pizza and
// the same percentiles as diverging bars around the median, the season touch map (HeatPitch on the
// team's players-heat file), the player's validated patterns with their evidence, and a
// "Raw / With context" toggle built only from the Verifier's existing player checks (ui.players[].
// checks: the held-back sentence, the published one and the recomputed figures). With no context
// claim the toggle is disabled and says so; nothing is invented. A player with no pattern gets a
// one-line note, and the position panels move up into the right column instead of an empty card.
import { useState } from "react";
import { Link, useParams } from "react-router";
import { Jersey } from "../../charts/LineupPitch";
import { HeatPitch } from "../../charts/HeatPitch";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { Sheet } from "../../components/ui/sheet";
import { Segmented } from "../../components/ui/segmented";
import { ChanceMap, PassMap } from "../../components/viz/PassMap";
import { PercentilePizza, comparisonGroup, pizzaValues } from "../../components/viz/PercentilePizza";
import { useData } from "../../data/context";
import { usePlayersHeat } from "../../data/matchContext";
import { chanceRows, passRows } from "../../data/matches";
import { eventIcon, Icon, patternIcon } from "../../icons";
import { clock, num, pct, words } from "../../lib/format";
import { patternLabel, useT, type Key } from "../../lib/i18n";
import type { PlayerCheck, PlayerRow, ProfilesMeta } from "../../types/ui";
import { reasonFor, textOf } from "../live/shared";
import { Avatar } from "../teams/parts";
import { ChancesPanel } from "./ChanceDrawer";
import { deckStats } from "./PlayerDeck";
import {
  DefenceMap,
  DefensiveActions,
  KeeperDistribution,
  KeeperFigures,
  NotInData,
  PassingExtras,
  ShotsFacedMap,
  WithLists,
} from "./PositionPanels";

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

/** Percentile minus 50 per pizza slice (same group, same rounding as the pizza). */
export function divergingValues(p: PlayerRow, players: readonly PlayerRow[]) {
  return pizzaValues(p, comparisonGroup(players, p.position)).map((v) => ({
    ...v,
    delta: v.pctl == null ? null : v.pctl - 50,
  }));
}

function DivergingBars({ p, players }: { p: PlayerRow; players: readonly PlayerRow[] }) {
  const { t, lang } = useT();
  const rows = divergingValues(p, players);
  return (
    <figure className="m-0" data-viz="diverging-bars">
      <ul className="flex flex-col gap-1.5">
        {rows.map((r) => (
          <li
            key={r.key}
            data-slice={r.key}
            className="grid grid-cols-[minmax(0,9.5rem)_1fr_2.5rem] items-center gap-2"
          >
            <span className="truncate text-[12px] text-ink-2">{r.label}</span>
            <span className="relative h-3 rounded-full bg-surface-2">
              <span className="absolute inset-y-0 left-1/2 w-px bg-ink-3" />
              {r.delta != null && (
                <span
                  className="absolute inset-y-0 rounded-full"
                  style={{
                    left: r.delta >= 0 ? "50%" : `${50 + r.delta}%`,
                    width: `${Math.abs(r.delta)}%`,
                    background: r.delta >= 0 ? "var(--heat-rise)" : "var(--heat-fall)",
                  }}
                />
              )}
            </span>
            <span className="num text-right text-[12px] font-semibold text-ink">
              {r.delta == null ? "–" : `${r.delta > 0 ? "+" : ""}${num(r.delta, lang)}`}
            </span>
          </li>
        ))}
      </ul>
      <figcaption className="mt-2 text-[12px] text-ink-3">{t("bars_note")}</figcaption>
    </figure>
  );
}

function EvidenceSheet({
  ids,
  title,
  open,
  onClose,
}: {
  ids: readonly string[];
  title: string;
  open: boolean;
  onClose: () => void;
}) {
  const m = useData();
  const { t, lang } = useT();
  const rows = m.evidenceOf(ids);
  return (
    <Sheet
      open={open}
      onOpenChange={(o) => !o && onClose()}
      id="player-evidence"
      title={title}
      eyebrow={t("evidence")}
      closeLabel={t("close")}
      width="sm:max-w-[480px]"
      bottomOnPhone
    >
      <ul className="flex flex-col gap-1.5 text-[13px]">
        {rows.map((e) => (
          <li
            key={e.event_id}
            data-event-id={e.event_id}
            className="flex min-w-0 items-center gap-2 border-b border-line pb-1.5"
          >
            <Icon name={eventIcon(e.event_type, e.outcome) ?? "pass"} size={16} className="shrink-0 text-ink-3" />
            <span className="num w-12 shrink-0 text-ink-3">{clock(e.clock_sec)}</span>
            <span className="truncate text-ink">{words(e.event_type)}</span>
            <span className="truncate text-ink-3">{words(e.outcome)}</span>
            <code className="ml-auto shrink-0 text-[11px] text-ink-3">{e.event_id}</code>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[12px] text-ink-3">
        <span className="num">{num(rows.length, lang)}</span> · {t("evidence_events")}
      </p>
    </Sheet>
  );
}

function Patterns({ id }: { id: string }) {
  const m = useData();
  const { t, lang } = useT();
  const [open, setOpen] = useState<string | null>(null);
  const rows = m.ui.patterns?.players[id] ?? [];
  const row = rows.find((r) => r.family === open);
  if (!rows.length) return <p className="text-[13px] text-ink-3">{t("patterns_none")}</p>;
  return (
    <>
      <ul className="flex flex-wrap gap-2" data-player-patterns={id}>
        {rows.map((r) => (
          <li key={r.family} data-family={r.family}>
            <button
              type="button"
              onClick={() => setOpen(r.family)}
              className="inline-flex min-h-[44px] flex-wrap items-center gap-x-2 gap-y-0.5 rounded-2xl border border-line bg-surface-2 px-3.5 py-1.5 text-left text-[13px] text-ink-2 hover:border-line-strong"
            >
              <Icon name={patternIcon(r.family)} size={16} />
              <b className="text-ink">{patternLabel(r.family, lang)}</b>
              <span className="num">
                {num(r.matches, lang)} {t("of_word")} {num(r.team_played, lang)} {t("matches_played")}
              </span>
              <Icon name="evidence-drawer" size={14} className="text-ink-3" />
            </button>
          </li>
        ))}
      </ul>
      <EvidenceSheet
        ids={row?.evidence ?? []}
        title={row ? patternLabel(row.family, lang) : ""}
        open={row != null}
        onClose={() => setOpen(null)}
      />
    </>
  );
}

function ContextToggle({ p }: { p: PlayerRow }) {
  const m = useData();
  const { t, lang } = useT();
  const c: PlayerCheck | undefined = p.checks.find((x) => x.fired && x.original);
  const [view, setView] = useState<"raw" | "context">("context");
  if (!c)
    return (
      <div data-context="none">
        <Segmented
          label={t("console_context")}
          name="player-context"
          value="raw"
          onChange={() => {}}
          options={[
            { value: "raw", label: t("con_raw") },
            { value: "context", label: t("con_context") },
          ]}
          disabled
        />
        <p className="mt-2 text-[13px] text-ink-3">{t("con_none")}</p>
      </div>
    );
  const wide = c.rule === "wide_forward_passes";
  const reason = reasonFor(m, c.rule_ids.length ? c.rule_ids : [c.rule], lang);
  const src = view === "raw" ? c.original! : c.text;
  const figures: [Key, string][] = wide
    ? [
        ["con_forward", num(p.forward_passes, lang)],
        ["con_wide", pct(p.wide_share, lang)],
        ["con_quality", `${num(p.pass_quality_ratio, lang)}×`],
      ]
    : [
        ["con_chances", num(p.chances, lang)],
        ["con_set", num(p.chances_set_piece, lang)],
        ["con_open", num(p.chances_open_play, lang)],
      ];
  return (
    <div data-context={c.rule} data-view={view}>
      <Segmented
        label={t("console_context")}
        name="player-context"
        value={view}
        onChange={setView}
        options={[
          { value: "raw", label: t("con_raw") },
          { value: "context", label: t("con_context") },
        ]}
      />
      <p className="mt-3 text-[15px] font-semibold leading-snug text-ink" lang={lang} data-role="player-sentence">
        {textOf(src, lang, "casual")}
      </p>
      <p className="mt-1 text-[12px] text-ink-3">{t(view === "raw" ? "con_raw_note" : "con_context_note")}</p>
      {view === "context" && (
        <>
          {reason && (
            <p className="mt-2 text-[12.5px] leading-snug text-ink-2">
              <b className="text-ink">{t("con_why")}:</b> {reason}
            </p>
          )}
          <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
            {figures.map(([k, v]) => (
              <div key={k} className="flex flex-col-reverse rounded-xl bg-surface-2 px-2 py-2">
                <dt className="mt-1 text-[11px] leading-tight text-ink-3">{t(k)}</dt>
                <dd className="display num m-0 text-[22px] font-bold leading-none text-ink">{v}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
    </div>
  );
}

function TouchMap({ p }: { p: PlayerRow }) {
  const { t } = useT();
  const heat = usePlayersHeat(p.team);
  if (heat.error) return <p className="text-[13px] text-ink-3">{t("touch_none")}</p>;
  if (!heat.data) return <div className="aspect-[105/68] w-full animate-pulse rounded-xl bg-surface-2" />;
  const bins = heat.data.players[p.id];
  if (!bins) return <p className="text-[13px] text-ink-3">{t("touch_none")}</p>;
  return (
    <>
      <HeatPitch grid={heat.data} teams={{ [p.id]: bins }} codes={[p.id]} label={p.name} compact />
      <p className="mt-2 text-[12px] text-ink-3">{t("touch_note")}</p>
    </>
  );
}

/** The position panels: chances (FW, MF), defending (DF), shot stopping (GK), as [lead, ...rest]; the
 * lead is a short panel so it fits beside the pass map. A player with no pattern gets the lead panel in the console's right column and the rest below. */
function positionPanels(p: PlayerRow, meta: ProfilesMeta, t: (k: Key) => string): React.ReactNode[] {
  const prof = p.profile;
  const pos = p.position;
  if (prof && (pos === "FW" || pos === "MF"))
    return [
      <Block key="chances" id="chances" title={t("ch_title")}>
        <ChancesPanel p={p} meta={meta} />
        <div className="mt-3">
          <NotInData topic="pp_na_lines" />
        </div>
      </Block>,
    ];
  if (prof?.defence && pos === "DF")
    return [
      <Block key="defence" id="defence" title={t("def_title")}>
        <DefensiveActions p={p} meta={meta} />
        <div className="mt-3 flex flex-col gap-1">
          <NotInData topic="pp_na_ground" />
          <NotInData topic="pp_na_regain" />
        </div>
      </Block>,
      <Block key="defence-map" id="defence-map" title={t("def_map")}>
        <WithLists code={p.team}>{(l) => <DefenceMap p={p} lists={l} />}</WithLists>
      </Block>,
      <Block key="passing" id="passing" title={t("pass_title")}>
        <PassingExtras p={p} />
      </Block>,
    ];
  if (prof?.keeper && pos === "GK")
    return [
      <Block key="keeper" id="keeper" title={t("gk_figures")}>
        <KeeperFigures p={p} />
        <div className="mt-3">
          <NotInData topic="pp_na_save" />
        </div>
      </Block>,
      <Block key="shots-faced" id="shots-faced" title={t("gk_map")}>
        <WithLists code={p.team}>{(l) => <ShotsFacedMap p={p} lists={l} />}</WithLists>
      </Block>,
      <Block key="distribution" id="distribution" title={t("gk_dist")}>
        <KeeperDistribution p={p} meta={meta} />
      </Block>,
    ];
  return [];
}

/** The panels below the top row: with a pattern, all of them (lead panel on the left, the others
 * stacked on the right); without one, those after the lead panel, side by side. */
function PanelsBelow({ panels, pos, all }: { panels: React.ReactNode[]; pos: string; all: boolean }) {
  if (!panels.length || (!all && panels.length < 2)) return null;
  if (all && panels.length === 1) return panels[0];
  const [lead, ...rest] = panels;
  return (
    <div className="grid grid-cols-1 items-start gap-flow xl:grid-cols-2" data-position-panels={pos}>
      {all ? (
        <>
          {lead}
          <div className="flex min-w-0 flex-col gap-flow">{rest}</div>
        </>
      ) : (
        rest
      )}
    </div>
  );
}

export default function PlayerConsole() {
  const { id = "" } = useParams();
  const m = useData();
  const { t, lang } = useT();
  const [mode, setMode] = useState<"fwd" | "chances">("fwd");
  const players = m.ui.players;
  const p = players.find((x) => x.id === id);
  if (!p)
    return (
      <div data-page="player" className="flex flex-col gap-2">
        <p className="text-[14px] text-ink-2">{t("player_missing")}</p>
        <Link to="/players" className="text-[13px] font-semibold text-accent">
          ← {t("back_players")}
        </Link>
      </div>
    );
  const prof = p.profile;
  const meta = m.ui.profiles;
  const hasPatterns = (m.ui.patterns?.players[p.id] ?? []).length > 0;
  const panels = positionPanels(p, meta, t);
  return (
    <div className="flex flex-col gap-flow" data-page="player" data-player={p.id}>
      <Link to="/players" className="self-start text-[12px] font-semibold text-ink-3 hover:text-ink">
        ← {t("back_players")}
      </Link>
      <header className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-surface-1 pad">
        <Avatar name={p.name} code={p.team} size={72} />
        <div className="min-w-0 flex-1">
          <h1 className="display text-[28px] font-semibold leading-none text-ink sm:text-[32px]">{p.name}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ink-2">
            <span className="inline-flex items-center gap-1.5">
              <Jersey code={p.team} shirt={p.shirt} size={28} />
              {t("number_short")} <span className="num font-semibold text-ink">{p.shirt}</span>
            </span>
            <span>{t(`pos_${p.position}` as Key)}</span>
            <Link
              to={`/teams/${p.team}`}
              className="inline-flex items-center gap-1.5 font-semibold text-ink hover:text-accent"
            >
              <TeamBadge code={p.team} size={24} named />
              {p.team}
            </Link>
          </p>
        </div>
        <dl className="flex w-full flex-wrap gap-x-5 gap-y-2 text-[12px] text-ink-3 sm:w-auto" data-console-stats>
          {prof && (
            <div className="flex flex-col-reverse">
              <dt className="mt-1">{t("pp_minutes")}</dt>
              <dd className="display num m-0 text-[24px] font-semibold leading-none text-ink sm:text-[30px]">
                {num(prof.minutes_whole, lang)}
              </dd>
            </div>
          )}
          {deckStats(p).map(([k, v]) => (
            <div key={k} className="flex flex-col-reverse">
              <dt className="mt-1">{t(k)}</dt>
              <dd className="display num m-0 text-[24px] font-semibold leading-none text-ink sm:text-[30px]">
                {v(lang)}
              </dd>
            </div>
          ))}
        </dl>
      </header>
      <div className="grid grid-cols-1 items-start gap-flow xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-7">
          <Block id="routes" title={t("console_routes")}>
            <Segmented<"fwd" | "chances">
              label={t("routes_label")}
              name="route-mode"
              value={mode}
              onChange={setMode}
              options={[
                { value: "fwd", label: t("route_fwd") },
                { value: "chances", label: t("route_chances") },
              ]}
              className="mb-3"
            />
            <WithLists code={p.team}>
              {(l) => {
                const passes = passRows(l, p.id);
                const chances = chanceRows(l, p.id);
                if (mode === "fwd")
                  return passes.length ? (
                    <PassMap rows={passes} player={p.id} name={p.name} />
                  ) : (
                    <p className="text-[13px] text-ink-3">{t("routes_none")}</p>
                  );
                return chances.length ? (
                  <ChanceMap rows={chances} player={p.id} name={p.name} />
                ) : (
                  <p className="text-[13px] text-ink-3">{t("ch_none")}</p>
                );
              }}
            </WithLists>
          </Block>
        </div>
        <div className="flex min-w-0 flex-col gap-flow xl:col-span-5" data-right-column>
          <Block id="context" title={t("console_context")}>
            <ContextToggle p={p} />
          </Block>
          {hasPatterns ? (
            <Block id="patterns" title={t("console_patterns")}>
              <Patterns id={p.id} />
            </Block>
          ) : (
            <>
              <p
                id="patterns"
                data-patterns="none"
                className="flex items-center gap-2 rounded-xl border border-line px-3.5 py-2.5 text-[13px] text-ink-3"
              >
                <Icon name="verdict-context" size={16} className="shrink-0" />
                {t("patterns_none_line")}
              </p>
              {panels[0] && (
                <div className="flex min-w-0 flex-col gap-flow" data-position-panels={p.position}>
                  {panels[0]}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <PanelsBelow panels={panels} pos={p.position} all={hasPatterns} />
      <div className="grid grid-cols-1 items-start gap-flow lg:grid-cols-2 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <Block id="pizza" title={t("console_pizza")}>
          <PercentilePizza p={p} players={players} />
        </Block>
        <Block id="bars" title={t("console_bars")}>
          <DivergingBars p={p} players={players} />
        </Block>
        <Block id="touch" title={t("console_touch")}>
          <TouchMap p={p} />
        </Block>
      </div>
    </div>
  );
}
