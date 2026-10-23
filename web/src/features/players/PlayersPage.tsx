// #/players: involvement, pass quality and chances created per player, season totals from event
// data only (ui.json, engine/metrics.py, engine/threat.py). No fatigue, GPS, speed or fitness
// figure exists in the data or on this page. The Verifier's player rules add the context that
// stops a volume passer or a set-piece taker from being misread.
import { TeamBadge } from "../../components/brand/TeamBadge";
import { scaleLinear } from "d3-scale";
import { useMemo, useState } from "react";
import { Chip, StatusChip } from "../../components/ui/badge";
import { Panel } from "../../components/ui/card";
import { ScrollRegion } from "../../components/ui/scroll-region";
import { Segmented } from "../../components/ui/segmented";
import { Tip } from "../../components/ui/tooltip";
import { useData } from "../../data/context";
import { cx } from "../../lib/cx";
import { num, pct, words } from "../../lib/format";
import { Icon, patternIcon } from "../../icons";
import { patternLabel, useT } from "../../lib/i18n";
import { PassRoutes, leagueXaPerChance, type RouteMode } from "../../components/viz/PassRoutes";
import { PercentilePizza } from "../../components/viz/PercentilePizza";
import type { PlayerCheck, PlayerRow } from "../../types/ui";
import { reasonFor, textOf } from "../live/shared";

const RULE_TITLE: Record<string, string> = {
  wide_forward_passes: "Volume, not value",
  set_piece_inflation: "Chances from dead balls",
};

function ContextCard({ p, c, featured }: { p: PlayerRow; c: PlayerCheck; featured: boolean }) {
  const m = useData();
  const { lang } = useT();
  const [view, setView] = useState<"before" | "after">("after");
  const reason = reasonFor(m, [c.rule], lang);
  const src = view === "before" && c.original ? c.original : c.text;
  const rows = m.evidenceOf(c.evidence_event_ids).slice(0, 6);
  const wide = c.rule === "wide_forward_passes";
  return (
    <article
      data-player={p.id}
      data-rule={c.rule}
      data-team={p.team}
      className={cx(
        "flex min-w-0 flex-col rounded-2xl border bg-surface-1 pad elev-1",
        featured ? "border-revise/40" : "border-line",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusChip status="revised" label={RULE_TITLE[c.rule] ?? words(c.rule)} />
        <span className="ml-auto inline-flex items-center gap-1.5 text-[12px] font-semibold text-ink-3">
          <TeamBadge code={p.team} size={24} named />
          {p.team} · {p.position}
        </span>
      </div>
      <h3 className="mt-2 text-[19px] font-bold tracking-tight text-ink">{p.name}</h3>
      <p
        className={cx(
          "mt-2 min-h-[3.6em] text-[14.5px] font-semibold leading-snug",
          view === "before" ? "text-ink-2 line-through decoration-block/70 decoration-2" : "text-ink",
        )}
        data-role="player-sentence"
        lang={lang}
      >
        {textOf(src, lang, "casual")}
      </p>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12px] font-semibold text-revise">
          {view === "before" ? "The plain stat (held back)" : "What the Verifier lets out"}
        </span>
        <Segmented
          label={`${p.name}: before or after verification`}
          name={`pv-${p.id}-${c.rule}`}
          value={view}
          onChange={setView}
          options={[
            { value: "before", label: "Before" },
            { value: "after", label: "After" },
          ]}
        />
      </div>
      {reason && (
        <p className="mt-2 text-[12.5px] leading-snug text-ink-2">
          <b className="text-ink">Why:</b> {reason}
        </p>
      )}
      <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
        {(wide
          ? [
              ["Forward passes", num(p.forward_passes, lang)],
              ["Ending wide", pct(p.wide_share, lang)],
              ["Pass quality", `${num(p.pass_quality_ratio, lang)}×`],
            ]
          : [
              ["Chances", num(p.chances, lang)],
              ["Set pieces", num(p.chances_set_piece, lang)],
              ["Open play", num(p.chances_open_play, lang)],
            ]
        ).map(([k, v]) => (
          <div key={k} className="rounded-xl bg-surface-2 px-2 py-2">
            <dd className="display m-0 text-[24px] font-bold leading-none text-ink">{v}</dd>
            <dt className="mt-1 text-[11px] leading-tight text-ink-3">{k}</dt>
          </div>
        ))}
      </dl>
      <div className="mt-3" data-card-visual="pass-routes">
        <PassRoutes
          rows={m.ui.visuals.routes[p.id] ?? []}
          mode={wide ? "fwd" : "chances"}
          leagueHotShare={m.ui.visuals.league_hot_share}
          leagueXa={leagueXaPerChance(m.ui.visuals.routes)}
          thirdX={m.ui.visuals.zones.third_x}
          player={p.id}
          compact
        />
      </div>
      <details className="mt-3 text-[12.5px]">
        <summary className="cursor-pointer font-semibold text-ink-2 hover:text-ink">
          Evidence (<span className="num">{num(c.evidence_event_ids.length, lang)}</span> events)
        </summary>
        <ul className="mt-2 space-y-1 text-ink-2">
          {rows.map((e) => (
            <li key={e.event_id} data-event-id={e.event_id} className="flex min-w-0 gap-2">
              <code className="shrink-0 text-[11px] text-ink-3">{e.event_id}</code>
              <span className="truncate">
                {words(e.event_type)} · {words(e.outcome)}
              </span>
            </li>
          ))}
        </ul>
      </details>
    </article>
  );
}

/** Forward-pass volume against pass quality. Axis ends are the data's own extremes. */
function VolumeQuality({ players, flagged }: { players: PlayerRow[]; flagged: Set<string> }) {
  const { lang } = useT();
  const pts = players.filter((p) => p.pass_quality_ratio != null && p.forward_passes > 0);
  const W = 640;
  const H = 300;
  const pad = { l: 40, r: 16, t: 14, b: 30 };
  const xMax = Math.max(...pts.map((p) => p.forward_passes));
  const yMax = Math.max(...pts.map((p) => p.pass_quality_ratio!));
  const x = scaleLinear()
    .domain([0, xMax])
    .range([pad.l, W - pad.r]);
  const y = scaleLinear()
    .domain([0, yMax])
    .range([H - pad.b, pad.t]);
  const [hover, setHover] = useState<PlayerRow | null>(null);
  const shown =
    hover ??
    pts.find((p) => flagged.has(p.id) && p.checks.some((c) => c.fired && c.rule === "wide_forward_passes")) ??
    null;
  return (
    <Panel
      id="volume-quality"
      title="Volume against quality"
      subtitle="Every player's forward passes (season total) against pass quality. Far right and low is the volume passer the Verifier holds back; small samples on the left are noisy."
    >
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_15rem]">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="block h-auto w-full"
          role="img"
          aria-label="Scatter: forward passes against pass quality, one dot per player"
          data-chart="volume-quality"
        >
          <rect
            x={pad.l}
            y={pad.t}
            width={W - pad.l - pad.r}
            height={H - pad.t - pad.b}
            fill="var(--surface-2)"
            rx="6"
          />
          <line
            x1={pad.l}
            x2={W - pad.r}
            y1={y(1)}
            y2={y(1)}
            stroke="var(--ink-3)"
            strokeDasharray="4 4"
            strokeWidth="1"
          />
          {pts.map((p) => {
            const f = flagged.has(p.id);
            return (
              <circle
                key={p.id}
                data-player={p.id}
                data-team={p.team}
                cx={x(p.forward_passes)}
                cy={y(p.pass_quality_ratio!)}
                r={f ? 6 : 3.5}
                fill={f ? "var(--revise)" : "var(--muted-accent)"}
                opacity={f ? 1 : 0.55}
                stroke={hover?.id === p.id ? "var(--ink)" : "none"}
                strokeWidth="2"
                onMouseEnter={() => setHover(p)}
                onMouseLeave={() => setHover(null)}
              />
            );
          })}
        </svg>
        <div className="flex flex-col gap-3 text-[12.5px] text-ink-2">
          <div className="rounded-xl border border-line bg-surface-2 px-3.5 py-3" aria-live="polite">
            {shown ? (
              <>
                <p className="font-semibold text-ink">{shown.name}</p>
                <p className="inline-flex items-center gap-1.5 text-ink-3">
                  <TeamBadge code={shown.team} size={24} named />
                  {shown.team} · {shown.position}
                </p>
                <p className="mt-2">
                  <span className="num font-semibold text-ink">{num(shown.forward_passes, lang)}</span> forward passes ·{" "}
                  <span className="num font-semibold text-ink">{num(shown.pass_quality_ratio, lang)}×</span> quality ·{" "}
                  <span className="num font-semibold text-ink">{pct(shown.wide_share, lang)}</span> ending wide
                </p>
              </>
            ) : (
              <p className="text-ink-3">Hover a dot to read the player.</p>
            )}
          </div>
          <ul className="space-y-1.5 text-ink-3">
            <li>
              <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-revise" />
              Context added by the Verifier
            </li>
            <li>
              <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-muted" />
              Other players
            </li>
            <li>Dashed line: league rate (1×)</li>
            <li>
              Axes run from zero to the highest value in the data: <span className="num">{num(xMax, lang)}</span>{" "}
              forward passes, <span className="num">{num(yMax, lang)}×</span> quality.
            </li>
          </ul>
        </div>
      </div>
    </Panel>
  );
}

/** The most prolific chance creators, split into set-piece and open-play chances. */
function ChanceSources({ players, flagged }: { players: PlayerRow[]; flagged: Set<string> }) {
  const { lang } = useT();
  const top = [...players].sort((a, b) => b.chances - a.chances || a.name.localeCompare(b.name)).slice(0, 10);
  const max = Math.max(...top.map((p) => p.chances), 1);
  return (
    <Panel
      id="chance-sources"
      title="Where the chances come from"
      subtitle="The leading chance creators, split by source. A total built on corners and free kicks says less about open-play creativity."
    >
      <ul className="space-y-2">
        {top.map((p) => (
          <li
            key={p.id}
            data-player={p.id}
            data-team={p.team}
            className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_2.5rem] items-center gap-3 text-[12.5px]"
          >
            <span className={cx("truncate", flagged.has(p.id) ? "font-semibold text-ink" : "text-ink-2")}>
              {p.name} <span className="text-ink-3">{p.team}</span>
            </span>
            <svg viewBox="0 0 100 10" preserveAspectRatio="none" className="block h-3 w-full" aria-hidden="true">
              <rect
                x="0"
                y="0"
                width={(100 * p.chances_open_play) / max}
                height="10"
                rx="1.5"
                fill="var(--accent)"
                opacity="0.85"
              />
              <rect
                x={(100 * p.chances_open_play) / max}
                y="0"
                width={(100 * p.chances_set_piece) / max}
                height="10"
                rx="1.5"
                fill="var(--revise)"
              />
            </svg>
            <span className="num text-right font-semibold text-ink">{num(p.chances, lang)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-3">
        <span>
          <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-accent" />
          Open play
        </span>
        <span>
          <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-revise" />
          Set piece
        </span>
      </p>
    </Panel>
  );
}

const SORTS = {
  involvement: { label: "Involvement", key: "involvement" },
  forward: { label: "Forward passes", key: "forward_passes" },
  chances: { label: "Chances", key: "chances" },
} as const;
type SortKey = keyof typeof SORTS;

function PlayerTable({ players, flagged }: { players: PlayerRow[]; flagged: Set<string> }) {
  const { lang } = useT();
  const teams = [...new Set(players.map((p) => p.team))].sort();
  const [team, setTeam] = useState("all");
  const [sort, setSort] = useState<SortKey>("involvement");
  const [query, setQuery] = useState("");
  const [all, setAll] = useState(false);
  const key = SORTS[sort].key;
  const rows = useMemo(
    () =>
      players
        .filter((p) => (team === "all" || p.team === team) && p.name.toLowerCase().includes(query.trim().toLowerCase()))
        .sort((a, b) => b[key] - a[key] || a.name.localeCompare(b.name)),
    [players, team, query, key],
  );
  const shown = all ? rows : rows.slice(0, 15);
  const th = "px-3 py-2 text-left font-semibold whitespace-nowrap";
  const td = "num px-3 py-1.5 whitespace-nowrap";
  return (
    <Panel
      id="deck"
      title="All players"
      actions={
        <span className="shrink-0 whitespace-nowrap text-[12px] text-ink-3">
          <span className="num">{num(rows.length, lang)}</span> players
        </span>
      }
    >
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-[12.5px] font-semibold text-ink-3">
          Team
          <select
            id="player-team"
            value={team}
            onChange={(e) => setTeam(e.target.value)}
            className="h-9 rounded-xl border border-line bg-surface-2 px-3 text-[13.5px] font-semibold text-ink"
          >
            <option value="all">All</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-[12.5px] font-semibold text-ink-3">
          Find
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Player name"
            className="h-9 w-40 rounded-xl border border-line bg-surface-2 px-3 text-[13.5px] text-ink placeholder:text-ink-3"
          />
        </label>
        <Segmented<SortKey>
          label="Sort by"
          name="sort"
          value={sort}
          onChange={setSort}
          options={(Object.keys(SORTS) as SortKey[]).map((value) => ({ value, label: SORTS[value].label }))}
        />
      </div>
      <ScrollRegion label="Player table, scrolls" className="mt-4">
        <table className="w-full min-w-[900px] border-collapse text-[13px]" data-table="players">
          <thead className="bg-surface-2 text-ink-3">
            <tr>
              <th scope="col" className={th}>
                Player
              </th>
              <th scope="col" className={th}>
                Team
              </th>
              <th scope="col" className={th}>
                Pos
              </th>
              <th scope="col" className={th}>
                <Tip content="Actions credited to the player: on-ball actions, duels, pressures, fouls and saves (season total).">
                  <button type="button" className="underline decoration-dotted underline-offset-4">
                    Involvement
                  </button>
                </Tip>
              </th>
              <th scope="col" className={th}>
                Team share
              </th>
              <th scope="col" className={th}>
                Passes
              </th>
              <th scope="col" className={th}>
                Completed
              </th>
              <th scope="col" className={th}>
                Forward
              </th>
              <th scope="col" className={th}>
                Wide
              </th>
              <th scope="col" className={th}>
                <Tip content="Share of forward passes into high-threat central cells, against the league rate (1× = league).">
                  <button type="button" className="underline decoration-dotted underline-offset-4">
                    Pass quality
                  </button>
                </Tip>
              </th>
              <th scope="col" className={th}>
                Chances
              </th>
              <th scope="col" className={th}>
                Open play
              </th>
              <th scope="col" className={th}>
                Set piece
              </th>
              <th scope="col" className={th}>
                Verifier
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((p) => (
              <tr key={p.id} data-player={p.id} data-team={p.team} className="border-t border-line">
                <th scope="row" className="whitespace-nowrap px-3 py-1.5 text-left font-semibold text-ink">
                  {p.name}
                </th>
                <td className="px-3 py-1.5">
                  <span className="inline-flex items-center gap-1.5">
                    <TeamBadge code={p.team} size={24} named />
                    {p.team}
                  </span>
                </td>
                <td className="px-3 py-1.5 text-ink-3">{p.position}</td>
                <td className={cx(td, "font-semibold")}>{num(p.involvement, lang)}</td>
                <td className={td}>{pct(p.team_share, lang)}</td>
                <td className={td}>{num(p.passes, lang)}</td>
                <td className={td}>{pct(p.pass_completion, lang)}</td>
                <td className={td}>{num(p.forward_passes, lang)}</td>
                <td className={td}>{pct(p.wide_share, lang)}</td>
                <td className={td}>{p.pass_quality_ratio == null ? "–" : `${num(p.pass_quality_ratio, lang)}×`}</td>
                <td className={td}>{num(p.chances, lang)}</td>
                <td className={td}>{num(p.chances_open_play, lang)}</td>
                <td className={td}>{num(p.chances_set_piece, lang)}</td>
                <td className="px-3 py-1.5">
                  {flagged.has(p.id) ? (
                    <Chip className="border-revise/40 text-revise">context added</Chip>
                  ) : (
                    <span className="text-ink-3">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
      {rows.length > shown.length || all ? (
        <button
          type="button"
          onClick={() => setAll(!all)}
          id="players-more"
          className="mt-3 rounded-full border border-line px-3.5 py-1.5 text-[13px] font-semibold text-ink-2 hover:text-ink"
        >
          {all ? "Show fewer" : "Show all players"}
        </button>
      ) : null}
    </Panel>
  );
}

/** One player: pass routes (V4) and percentiles (V8), with a picker. */
/** Player-level tactical patterns found for this player this season (ui.json patterns.players). */
function PlayerPatterns({ id }: { id: string }) {
  const m = useData();
  const { lang } = useT();
  const rows = m.ui.patterns?.players[id];
  if (!rows?.length) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-2" data-player-patterns={id}>
      {rows.map((r) => (
        <li
          key={r.family}
          data-family={r.family}
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-2 px-3 py-1 text-[12.5px] text-ink-2"
        >
          <Icon name={patternIcon(r.family)} size={14} />
          <b className="text-ink">{patternLabel(r.family, lang)}</b>
          <span>
            in <span className="num">{num(r.matches, lang)}</span> of the team's{" "}
            <span className="num">{num(r.team_played, lang)}</span> matches
          </span>
        </li>
      ))}
    </ul>
  );
}

function Profile({ players, initial }: { players: PlayerRow[]; initial: string }) {
  const m = useData();
  const [id, setId] = useState(initial);
  const [mode, setMode] = useState<RouteMode>("fwd");
  const p = players.find((x) => x.id === id) ?? players[0]!;
  const rows = m.ui.visuals.routes[p.id];
  const sorted = useMemo(
    () => [...players].sort((a, b) => a.team.localeCompare(b.team) || a.name.localeCompare(b.name)),
    [players],
  );
  return (
    <Panel
      id="profile"
      title="Player profile"
      subtitle="Where a player's passes go and what they are worth, and how the player ranks among outfield regulars."
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12px] font-semibold text-ink-3">
          Player
          <select
            id="profile-player"
            className="h-10 max-w-full rounded-xl border border-line bg-surface-2 px-3 text-[14px] font-semibold text-ink"
            value={p.id}
            onChange={(e) => setId(e.target.value)}
          >
            {sorted.map((x) => (
              <option key={x.id} value={x.id}>
                {x.team} · {x.name} ({x.position})
              </option>
            ))}
          </select>
        </label>
        <Segmented<RouteMode>
          label="Passes to draw"
          name="route-mode"
          value={mode}
          onChange={setMode}
          options={[
            { value: "fwd", label: "Forward passes" },
            { value: "chances", label: "Chances created" },
          ]}
        />
      </div>
      <PlayerPatterns id={p.id} />
      <div className="mt-4 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        {rows ? (
          <PassRoutes
            rows={rows}
            mode={mode}
            leagueHotShare={m.ui.visuals.league_hot_share}
            leagueXa={leagueXaPerChance(m.ui.visuals.routes)}
            thirdX={m.ui.visuals.zones.third_x}
            player={p.id}
          />
        ) : (
          <p className="rounded-xl border border-dashed border-line-strong px-4 py-6 text-center text-[13px] text-ink-3">
            Pass routes are not available in this dataset for this player.
          </p>
        )}
        <PercentilePizza p={p} players={players} />
      </div>
    </Panel>
  );
}

export default function PlayersPage() {
  const m = useData();
  const players = m.ui.players;
  const cards = players.flatMap((p) => p.checks.filter((c) => c.fired).map((c) => ({ p, c })));
  cards.sort(
    (a, b) =>
      Number(b.c.rule === "wide_forward_passes") - Number(a.c.rule === "wide_forward_passes") ||
      b.p.chances - a.p.chances,
  );
  const flagged = new Set(cards.map((x) => x.p.id));
  return (
    <div className="flex flex-col gap-flow" data-page="players">
      <header className="max-w-3xl">
        <p className="eyebrow">Season totals · event data only</p>
        <h1 className="mt-1 text-[28px] font-bold tracking-tight text-ink sm:text-[34px]">Player Deck</h1>
        <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">
          Involvement, pass quality and chances created. The data has no minutes played, so these are season totals, not
          rates per ninety, and no tracking, so there are no distance, speed or fitness figures.
        </p>
      </header>
      <Panel
        id="context"
        title="Context the Verifier adds"
        subtitle="Player claims that are true but would mislead on their own. The Verifier holds the plain stat back until the sentence carries the context; toggle Before and After to compare."
      >
        <div className="grid grid-cols-1 gap-flow md:grid-cols-2 xl:grid-cols-4">
          {cards.map(({ p, c }, i) => (
            <ContextCard key={`${p.id}-${c.rule}`} p={p} c={c} featured={i < 2} />
          ))}
        </div>
      </Panel>
      <Profile players={players} initial={cards[0]?.p.id ?? players[0]!.id} />
      <div className="grid grid-cols-1 gap-flow xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <VolumeQuality players={players} flagged={flagged} />
        <ChanceSources players={players} flagged={flagged} />
      </div>
      <PlayerTable players={players} flagged={flagged} />
    </div>
  );
}
