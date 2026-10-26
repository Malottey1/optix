// Home below the hero (a lazy chunk; the showcase match file loads only here). Every number is read
// from the data: the showcase strip from matches/m_showcase.json (header score, turning points), the
// key insights from the showcase stream (the Verifier's final attempt), the xG race from
// ui.visuals.shots, momentum from the timeline, the heat thumbnail from the match file's heat bins,
// the spotlight from ui.players, patterns from the catalogue, the trust line from the ledger.
// Choices are deterministic (homePicks): nothing is ranked by hand.
import { Link } from "react-router";
import { PitchLines } from "../../components/pitch/Pitch";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { StatusChip } from "../../components/ui/badge";
import { Glyph } from "../../components/icons";
import { heatValues } from "../../charts/HeatPitch";
import { useData } from "../../data/context";
import { useMatchFile } from "../../data/matchContext";
import { SHOWCASE_ID, type MatchFile } from "../../data/matches";
import type { MatchModel } from "../../data/model";
import { Icon, patternIcon, type IconName } from "../../icons";
import { cx } from "../../lib/cx";
import { clock, num, words } from "../../lib/format";
import { patternLabel, useT, type Key } from "../../lib/i18n";
import type { Insight, Period, PlayerRow } from "../../types/ui";
import { cardChip, PCT_METRICS, statusOf, textOf } from "../live/shared";
import { STATUS_KEY } from "../live/Feed";
import { fill } from "../hub/parts";
import { Avatar } from "../teams/parts";
import { ForYou } from "./ForYou";

/** Club order of the hero artwork, left to right. */
const ORDER = ["AUR", "NTG", "CAL", "VES", "HAR"];
/** Key-insight sentences longer than this are skipped, so a card stays within its word budget. */
export const MAX_SENTENCE_WORDS = 18;
/** Stream types that are running counters, not findings (never picked as key insights). */
const COUNTERS = new Set(["recap_line", "milestone", "threat_pass", "rhythm_wave"]);

const nWords = (s: string) => s.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;

/** The deterministic Home choices (pure, unit-tested):
 * insights: the first revised finding, then the first two passed findings of other types, in stream
 * order, each with a sentence of at most MAX_SENTENCE_WORDS words;
 * spotlight: the showcase goal scorer with the most season goals (ties: player id);
 * patterns: the first two validated catalogue families seen in the showcase stream (catalogue order),
 * topped up from the catalogue. */
export function homePicks(m: MatchModel) {
  const candidates = m.insights.filter(
    (i) => !COUNTERS.has(i.insight_type) && nWords(textOf(i.text.rendered, "en", "casual")) <= MAX_SENTENCE_WORDS,
  );
  const revised = candidates.find((i) => statusOf(m, i) === "revised");
  const picked: Insight[] = revised ? [revised] : [];
  for (const i of candidates) {
    if (picked.length >= 3) break;
    if (statusOf(m, i) === "revised" || picked.some((p) => p.insight_type === i.insight_type)) continue;
    picked.push(i);
  }
  const scorers = new Set(m.timeline.goals.map((g) => g.player_id));
  const spotlight =
    m.ui.players.filter((p) => scorers.has(p.id)).sort((a, b) => b.goals - a.goals || a.id.localeCompare(b.id))[0] ??
    null;
  const cat = (m.ui.patterns?.catalogue ?? []).filter((c) => c.status === "validated").map((c) => c.family);
  const seen = new Set(m.insights.map((i) => String(i.payload.family ?? "")));
  const patterns = [...cat.filter((f) => seen.has(f)), ...cat.filter((f) => !seen.has(f))].slice(0, 2);
  return { insights: picked.sort((a, b) => a.clock.start_sec - b.clock.start_sec), spotlight, patterns };
}

const card = "rounded-2xl border border-line bg-surface-1 pad elev-1";
const more = "inline-flex items-center gap-1 text-[13px] font-semibold text-accent hover:underline";

function SectionHead({ id, title, link }: { id: string; title: string; link?: { to: string; label: string } }) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
      <h2 id={id} className="text-[16px] font-semibold text-ink">
        {title}
      </h2>
      {link && (
        <Link to={link.to} className={more}>
          {link.label}
          <Glyph name="arrow" className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

const TP_ICON: Record<string, (tp: MatchFile["turning_points"][number]) => IconName> = {
  goal: () => "goal",
  card: (tp) => (tp.card === "red" || tp.card === "second_yellow" ? "red-card" : "yellow-card"),
  sub: () => "substitution",
};

function ShowcaseStrip({ file }: { file: MatchFile }) {
  const { t, lang } = useT();
  const h = file.header;
  const periods = file.periods as Period[];
  const marks = file.turning_points.filter((tp) => tp.kind in TP_ICON);
  const live = file.status !== "final";
  return (
    <section aria-labelledby="home-showcase" className={card} data-home="showcase" data-budget="card">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <h2 id="home-showcase" className="eyebrow w-full sm:w-auto">
          {t("ho_showcase")}
        </h2>
        <div className="flex items-center gap-3" data-score>
          <TeamBadge code={h.home.code} size={36} named />
          <span className="text-[15px] font-semibold text-ink">{h.home.code}</span>
          <span className="display num text-[28px] font-bold leading-none text-ink">
            {num(h.home.goals, lang)}–{num(h.away.goals, lang)}
          </span>
          <span className="text-[15px] font-semibold text-ink">{h.away.code}</span>
          <TeamBadge code={h.away.code} size={36} named />
        </div>
        <span
          className={cx(
            "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[12px] font-semibold",
            live ? "bg-accent text-accent-ink" : "border border-line text-ink-2",
          )}
        >
          {live && <Icon name="live" size={14} />}
          {t(live ? "ho_live_chip" : "ho_final_chip")}
        </span>
        <Link to={`/match/${SHOWCASE_ID}`} className={cx(more, "sm:ml-auto")}>
          {t("ho_explore")}
          <Glyph name="arrow" className="h-4 w-4" />
        </Link>
      </div>
      <div className="relative mt-4 h-9" role="list" aria-label={t("ho_timeline")} data-timeline>
        <span className="absolute inset-x-0 top-1/2 h-px bg-line-strong" aria-hidden="true" />
        {marks.map((tp) => (
          <span
            key={tp.event_id}
            role="listitem"
            data-mark={tp.kind}
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
            style={{ left: `${(tp.clock_sec / file.duration_sec) * 100}%` }}
          >
            <span className="sr-only">
              {words(tp.kind)} {tp.team} {clock(tp.clock_sec, periods)}
            </span>
            <Icon
              name={TP_ICON[tp.kind]!(tp)}
              size={18}
              className={cx("rounded-full bg-surface-1", tp.team === h.home.code ? "text-home" : "text-away")}
            />
          </span>
        ))}
      </div>
    </section>
  );
}

function metricOf(m: MatchModel, ins: Insight, lang: Parameters<typeof num>[1]) {
  const c = m.chain(ins.claim_id).at(-1)?.claim;
  if (!c || c.value?.amount == null) return null;
  const pctUnit = c.value.unit === "percent" || PCT_METRICS.has(c.metric);
  return { label: words(c.metric), value: `${num(c.value.amount, lang)}${pctUnit ? "%" : ""}` };
}

function KeyInsights({ picks }: { picks: Insight[] }) {
  const m = useData();
  const { t, lang } = useT();
  return (
    <section aria-labelledby="home-insights" data-home="insights">
      <SectionHead
        id="home-insights"
        title={t("ho_insights")}
        link={{ to: `/match/${SHOWCASE_ID}`, label: t("ho_view_all") }}
      />
      <ul className="grid grid-cols-1 gap-flow md:grid-cols-3">
        {picks.map((ins) => {
          const status = statusOf(m, ins);
          const chip = cardChip(m, ins, lang);
          const metric = metricOf(m, ins, lang);
          return (
            <li key={ins.insight_id} className={cx(card, "flex flex-col gap-2.5")} data-budget="card">
              <article data-insight-id={ins.insight_id} data-status={status} className="flex h-full flex-col gap-2.5">
                <div className="flex flex-wrap items-center gap-2 text-[12px]">
                  <StatusChip status={status} label={t(STATUS_KEY[status])} />
                  <span className="inline-flex items-center gap-1.5 font-semibold text-ink-2">
                    <Icon name={chip.icon} size={16} />
                    {chip.label}
                  </span>
                  <time className="num ml-auto font-semibold text-ink-3">
                    {clock(ins.clock.start_sec, m.timeline.periods)}
                  </time>
                </div>
                <p className="text-[14.5px] font-semibold leading-snug text-ink" lang={lang}>
                  {textOf(ins.text.rendered, lang, "casual")}
                </p>
                <div className="mt-auto flex items-end justify-between gap-2">
                  {metric && (
                    <p className="flex flex-col">
                      <span className="display num text-[22px] font-bold leading-none text-ink">{metric.value}</span>
                      <span className="mt-1 text-[11.5px] text-ink-3">{metric.label}</span>
                    </p>
                  )}
                  <Link
                    to={`/match/${SHOWCASE_ID}?t=${ins.clock.start_sec + ins.clock.duration_sec}`}
                    data-home-evidence={ins.insight_id}
                    className="ml-auto inline-flex min-h-[36px] items-center gap-1 rounded-full border border-line px-3 text-[12px] font-semibold text-ink-2 hover:border-accent-line hover:text-ink"
                  >
                    {t("ho_evidence")}
                    <Glyph name="arrow" className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function XgRace() {
  const m = useData();
  const tl = m.timeline;
  const shots = m.ui.visuals.shots;
  const W = 200;
  const H = 80;
  const total = (code: string) => shots.filter((s) => s[2] === code).reduce((a, s) => a + s[6], 0);
  const top = Math.max(total(tl.home.code), total(tl.away.code), 0.1);
  const path = (code: string) => {
    let acc = 0;
    let d = `M0,${H}`;
    for (const s of shots.filter((x) => x[2] === code)) {
      const x = (s[1] / tl.duration_sec) * W;
      d += ` L${x.toFixed(1)},${(H - (acc / top) * (H - 6)).toFixed(1)}`;
      acc += s[6];
      d += ` L${x.toFixed(1)},${(H - (acc / top) * (H - 6)).toFixed(1)}`;
    }
    return `${d} L${W},${(H - (acc / top) * (H - 6)).toFixed(1)}`;
  };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" aria-hidden="true" data-xg-race>
      <line x1="0" x2={W} y1={H} y2={H} stroke="var(--line-strong)" />
      {[tl.home.code, tl.away.code].map((c, i) => (
        <path
          key={c}
          d={path(c)}
          data-team={c}
          data-total={Math.round(total(c) * 100) / 100}
          fill="none"
          stroke={i ? "var(--away)" : "var(--home)"}
          strokeWidth="2"
        />
      ))}
    </svg>
  );
}

function MomentumSpark() {
  const m = useData();
  const pts = m.timeline.momentum;
  const W = 200;
  const H = 80;
  const top = Math.max(1, ...pts.map((p) => Math.abs(p[1])));
  const x = (c: number) => (c / m.timeline.duration_sec) * W;
  const y = (v: number) => H / 2 - (v / top) * (H / 2 - 3);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="block h-auto w-full"
      aria-hidden="true"
      data-momentum-spark
      data-points={pts.length}
    >
      <defs>
        <clipPath id="mo-up">
          <rect x="0" y="0" width={W} height={H / 2} />
        </clipPath>
        <clipPath id="mo-down">
          <rect x="0" y={H / 2} width={W} height={H / 2} />
        </clipPath>
      </defs>
      <line x1="0" x2={W} y1={H / 2} y2={H / 2} stroke="var(--line-strong)" />
      <path d={`${d} L${W},${H / 2} L0,${H / 2} z`} fill="var(--home)" opacity="0.5" clipPath="url(#mo-up)" />
      <path d={`${d} L${W},${H / 2} L0,${H / 2} z`} fill="var(--away)" opacity="0.5" clipPath="url(#mo-down)" />
    </svg>
  );
}

function HeatThumb({ file }: { file: MatchFile }) {
  const code = file.header.home.code;
  const halves = (file.heat.teams as Record<string, number[][]>)[code] ?? [];
  const grid = file.heat;
  const { counts, values, scale } = heatValues(grid, halves, "volume", "both");
  return (
    <svg
      viewBox="-1 -1 107 70"
      className="block h-auto w-full"
      aria-hidden="true"
      data-heat-thumb
      data-total={counts.reduce((a, b) => a + b, 0)}
    >
      <defs>
        <clipPath id="home-heat-clip">
          <rect x="0" y="0" width="105" height="68" />
        </clipPath>
        <filter id="home-heat-soft" x="-5%" y="-5%" width="110%" height="110%">
          <feGaussianBlur stdDeviation="2.4" />
        </filter>
      </defs>
      <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
      <g clipPath="url(#home-heat-clip)" filter="url(#home-heat-soft)">
        {values.map((v, b) => {
          const row = Math.floor(b / grid.cols);
          const col = b % grid.cols;
          const x0 = grid.x_edges[col]! * 1.05;
          const y0 = grid.y_edges[row]! * 0.68;
          return (
            <rect
              key={b}
              x={x0}
              y={y0}
              width={grid.x_edges[col + 1]! * 1.05 - x0 + 0.05}
              height={grid.y_edges[row + 1]! * 0.68 - y0 + 0.05}
              fill="var(--heat-seq)"
              fillOpacity={scale > 0 ? Math.min(1, v / scale) * 0.92 : 0}
            />
          );
        })}
      </g>
      <PitchLines ground={false} />
    </svg>
  );
}

function Tiles({ file }: { file: MatchFile }) {
  const m = useData();
  const { t, lang } = useT();
  const h = file.header;
  const tiles: { id: string; title: Key; icon: IconName; body: React.ReactNode; note: string }[] = [
    {
      id: "xg",
      title: "ho_xg",
      icon: "metric-xg",
      body: (
        <>
          <XgRace />
          <p className="mt-2 flex gap-4 text-[12.5px] font-semibold">
            <span className="text-home">
              {h.home.code} <span className="num">{num(h.home.xg, lang)}</span>
            </span>
            <span className="text-away">
              {h.away.code} <span className="num">{num(h.away.xg, lang)}</span>
            </span>
          </p>
        </>
      ),
      note: t("ho_xg_note"),
    },
    {
      id: "momentum",
      title: "ho_momentum",
      icon: "metric-momentum",
      body: <MomentumSpark />,
      note: fill(t("ho_momentum_note"), { home: m.timeline.home.code, away: m.timeline.away.code }),
    },
    {
      id: "heat",
      title: "ho_heat",
      icon: "metric-territorial-stress",
      body: <HeatThumb file={file} />,
      note: fill(t("ho_heat_note"), { team: h.home.code }),
    },
  ];
  return (
    <ul className="grid grid-cols-1 gap-flow md:grid-cols-3" data-home="tiles">
      {tiles.map((x) => (
        <li key={x.id} data-tile={x.id} data-budget="card">
          <Link
            to={`/match/${SHOWCASE_ID}`}
            className={cx(card, "flex h-full flex-col gap-2 hover:border-line-strong")}
          >
            <span className="flex items-center gap-2 text-[14px] font-semibold text-ink">
              <Icon name={x.icon} size={18} className="text-accent" />
              {t(x.title)}
            </span>
            {x.body}
            <span className="mt-auto text-[11.5px] text-ink-3">{x.note}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Spotlight({ p }: { p: PlayerRow }) {
  const { t, lang } = useT();
  const stats: [Key, number][] = [
    ["season_goals", p.goals],
    ["season_assists", p.assists],
    ["con_chances", p.chances],
  ];
  return (
    <section aria-labelledby="home-spot" className={card} data-home="spotlight" data-budget="card">
      <SectionHead id="home-spot" title={t("ho_spotlight")} />
      <Link
        to={`/players/${p.id}`}
        className="flex items-center gap-3 rounded-xl hover:bg-surface-2"
        data-player={p.id}
      >
        <Avatar name={p.name} code={p.team} size={52} />
        <span className="min-w-0">
          <span className="flex items-center gap-2">
            <TeamBadge code={p.team} size={22} named />
            <span className="truncate text-[15px] font-semibold text-ink">{p.name}</span>
          </span>
          <span className="block text-[12.5px] text-ink-3">{t(`pos_${p.position}` as Key)}</span>
        </span>
      </Link>
      <dl className="mt-3 grid grid-cols-3 gap-2">
        {stats.map(([k, v]) => (
          <div key={k} className="flex flex-col-reverse rounded-xl bg-surface-2 px-3 py-2">
            <dt className="mt-1 text-[11px] text-ink-3">{t(k)}</dt>
            <dd className="display num m-0 text-[20px] font-bold leading-none text-ink">{num(v, lang)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-[13px] text-ink-2">{fill(t("ho_spot_sentence"), { g: num(p.goals, lang) })}</p>
    </section>
  );
}

function Patterns({ families }: { families: string[] }) {
  const { t, lang } = useT();
  return (
    <section aria-labelledby="home-patterns" className={card} data-home="patterns" data-budget="card">
      <SectionHead id="home-patterns" title={t("ho_patterns")} />
      <ul className="flex flex-col gap-3">
        {families.map((f) => (
          <li key={f} className="flex gap-3" data-family={f}>
            <Icon name={patternIcon(f)} size={22} className="mt-0.5 shrink-0 text-accent" />
            <span className="min-w-0">
              <span className="flex flex-wrap items-center gap-2">
                <b className="text-[14px] text-ink">{patternLabel(f, lang)}</b>
                <StatusChip status="published" label={t("ho_validated")} />
              </span>
              <span className="mt-0.5 block text-[12.5px] leading-snug text-ink-2">{t(`hp_${f}` as Key)}</span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Teams() {
  const m = useData();
  const { t } = useT();
  const teams = [...m.ui.teams.teams].sort((a, b) => ORDER.indexOf(a.code) - ORDER.indexOf(b.code));
  return (
    <section aria-labelledby="home-teams" className={card} data-home="teams" data-budget="card">
      <SectionHead id="home-teams" title={t("ho_teams")} link={{ to: "/teams", label: t("home_clubs_link") }} />
      <ul className="grid grid-cols-5 gap-2">
        {teams.map((tm) => (
          <li key={tm.code}>
            <Link
              to={`/teams/${tm.code}`}
              data-team={tm.code}
              aria-label={`${tm.code}, ${tm.name}`}
              className="flex flex-col items-center gap-1 rounded-xl py-2 hover:bg-surface-2"
            >
              <TeamBadge code={tm.code} size={44} named />
              <span className="text-[11.5px] font-semibold tracking-[0.06em] text-ink-3">{tm.code}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Trust() {
  const m = useData();
  const { t, lang } = useT();
  const items: { key: string; icon: IconName; text: React.ReactNode }[] = [
    { key: "engine", icon: "trace-to-data", text: t("ho_trust_1") },
    {
      key: "revised",
      icon: "verdict-revised",
      text: fill(t("ho_trust_2"), { n: num(m.ui.ledger.counts.revised, lang) }),
    },
    { key: "evidence", icon: "evidence-drawer", text: t("ho_trust_3") },
  ];
  return (
    <section aria-labelledby="home-trust" className={card} data-home="trust">
      <SectionHead id="home-trust" title={t("ho_trust")} link={{ to: "/tech", label: t("ho_how") }} />
      <ul className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {items.map((x) => (
          <li key={x.key} data-proof={x.key} className="flex gap-3 rounded-xl bg-surface-2 px-4 py-3">
            <Icon name={x.icon} size={20} className="mt-0.5 shrink-0 text-accent" />
            <span className="text-[13px] leading-snug text-ink-2">{x.text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function HomeSections() {
  const m = useData();
  const file = useMatchFile(SHOWCASE_ID);
  const picks = homePicks(m);
  return (
    <div className="flex flex-col gap-flow" data-page-budget="home-page">
      <ForYou />
      {file.data ? (
        <ShowcaseStrip file={file.data} />
      ) : (
        <div className="h-[120px] animate-pulse rounded-2xl bg-surface-2" />
      )}
      <KeyInsights picks={picks.insights} />
      {file.data ? <Tiles file={file.data} /> : <div className="h-[220px] animate-pulse rounded-2xl bg-surface-2" />}
      <div className="grid grid-cols-1 gap-flow lg:grid-cols-3">
        {picks.spotlight && <Spotlight p={picks.spotlight} />}
        <Patterns families={picks.patterns} />
        <Teams />
      </div>
      <Trust />
    </div>
  );
}
