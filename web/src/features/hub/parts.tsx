// Match Hub building blocks for a played (Final) match, from its recap file (data/matches.ts):
// compact header, turning-points timeline, recap cards, event log, the evidence drawer and the
// claim ledger table. Every number shown is in the file; nothing is computed beyond counting rows.
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { Sheet } from "../../components/ui/sheet";
import { Arrowheads, InsightLayer, PitchLines } from "../../components/pitch/Pitch";
import type { LogEvent, MatchFile, TurningPoint } from "../../data/matches";
import { eventIcon, Icon, insightIcon, patternIcon, type IconName } from "../../icons";
import { cx } from "../../lib/cx";
import { clock, num, words } from "../../lib/format";
import { patternLabel, typeLabel, useT, type Key } from "../../lib/i18n";
import type { EvidenceRow, Insight, Period } from "../../types/ui";
import { textOf } from "../live/shared";

export const fill = (s: string, vars: Record<string, string>) =>
  s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

export type Selection =
  { kind: "tp"; tp: TurningPoint } | { kind: "card"; id: string } | { kind: "event"; id: string } | null;

/** Per-family caps for the recap cards: at most `cap` pattern cards per family and per other type,
 * in stream order (the export already caps non-pattern types at two). */
export function capCards(cards: readonly Insight[], cap = 2): Insight[] {
  const seen = new Map<string, number>();
  return cards.filter((c) => {
    const k = c.insight_type === "tactical_pattern" ? `p:${String(c.payload.family)}` : c.insight_type;
    const n = (seen.get(k) ?? 0) + 1;
    seen.set(k, n);
    return n <= cap;
  });
}

export function tpIcon(tp: TurningPoint): IconName {
  if (tp.kind === "goal") return "goal";
  if (tp.kind === "card") return tp.card === "red" || tp.card === "second_yellow" ? "red-card" : "yellow-card";
  if (tp.kind === "sub") return "substitution";
  if (tp.kind === "momentum") return "metric-momentum";
  return patternIcon(tp.family);
}

export function tpLabel(tp: TurningPoint, t: (k: Key) => string, lang: string): string {
  if (tp.kind === "goal") return t("tp_goal");
  if (tp.kind === "card") return tp.card === "red" || tp.card === "second_yellow" ? t("tp_red") : t("tp_yellow");
  if (tp.kind === "sub") return t("tp_sub");
  if (tp.kind === "momentum") return t("tp_momentum");
  return patternLabel(tp.family ?? null, lang as "en");
}

export function playerName(file: MatchFile, id: string | null | undefined): string {
  return id && file.players[id] ? String(file.players[id]![0]) : "";
}

export function HubHeader({ file, nav }: { file: MatchFile; nav?: ReactNode }) {
  const { t, lang } = useT();
  const h = file.header;
  const side = (s: typeof h.home, align: "left" | "right") => (
    <div className={cx("flex min-w-0 items-center gap-3", align === "right" && "flex-row-reverse text-right")}>
      <TeamBadge code={s.code} size={44} className="hidden sm:inline-grid" />
      <div className="min-w-0">
        <div className="truncate text-[16px] font-semibold text-ink sm:text-[18px]">
          <span className="sm:hidden">{s.code}</span>
          <span className="hidden sm:inline">{s.name}</span>
        </div>
        <div className="text-[11.5px] text-ink-3 sm:text-[12px]">
          <span className="num">{num(s.xg, lang)}</span> xG · <span className="num">{num(s.shots, lang)}</span>{" "}
          {t("shots")}
        </div>
      </div>
    </div>
  );
  return (
    <header className="rounded-2xl border border-line bg-surface-1 px-4 py-3" data-budget="hub-header">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        {side(h.home, "left")}
        <div className="text-center">
          <div className="display num text-[34px] font-semibold leading-none text-ink" data-score>
            {num(h.home.goals, lang)}–{num(h.away.goals, lang)}
          </div>
          <div className="mt-1 text-[11.5px] font-semibold text-ink-3">
            {file.status === "live" ? t("status_live") : t("status_final")} · {t("matchweek")} {h.matchweek}
          </div>
        </div>
        {side(h.away, "right")}
      </div>
      {nav}
    </header>
  );
}

/** Buttons that scroll to a section (hash links would change the route). */
export function SectionNav({ items }: { items: [string, string][] }) {
  const { t } = useT();
  return (
    <nav aria-label={t("hub_sections")} className="mt-3 flex flex-wrap gap-1.5 border-t border-line pt-2.5">
      {items.map(([id, label]) => (
        <button
          key={id}
          type="button"
          data-section-link={id}
          onClick={() => document.getElementById(id)?.scrollIntoView({ block: "start" })}
          className="min-h-[32px] rounded-full border border-line px-3 text-[12px] font-semibold text-ink-2 hover:border-line-strong hover:text-ink"
        >
          {label}
        </button>
      ))}
    </nav>
  );
}

export function Section({
  id,
  title,
  children,
  budget,
}: {
  id: string;
  title: string;
  children: ReactNode;
  budget?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-h`}
      className="scroll-mt-20 rounded-2xl border border-line bg-surface-1 pad"
      data-budget={budget ?? id}
    >
      <h2 id={`${id}-h`} className="mb-3 text-[15px] font-semibold text-ink">
        {title}
      </h2>
      {children}
    </section>
  );
}

/** Rows of the timeline so that icons never collide: greedy, nearest free row, per side. */
export function layoutMarks(xs: readonly number[], minGap: number, maxRows = 3): number[] {
  const last: number[] = [];
  return xs.map((x) => {
    let r = last.findIndex((l) => x - l >= minGap);
    if (r < 0) r = last.length < maxRows ? last.length : last.indexOf(Math.min(...last));
    last[r] = x;
    return r;
  });
}

export function TurningPoints({ file, onSelect }: { file: MatchFile; onSelect: (s: Selection) => void }) {
  const { t, lang } = useT();
  const dur = Math.max(1, file.duration_sec);
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(200, e!.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  // icons are 32 px wide: keep at least 34 px between two icons in one row
  const gap = (34 / width) * 100;
  const sides = [file.header.home.code, file.header.away.code];
  const rows = useMemo(() => {
    return sides.map((code) => {
      const tps = file.turning_points.filter((tp) => tp.team === code);
      const pos = layoutMarks(
        tps.map((tp) => (tp.clock_sec / dur) * 100),
        gap,
        8,
      );
      return tps.map((tp, i) => ({ tp, row: pos[i]! }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, gap]);
  const ht = file.periods[1] ? (file.periods[1].start_sec / dur) * 100 : null;
  const ROW = 28;
  const height = (side: number) => Math.max(1, ...rows[side]!.map((r) => r.row + 1)) * ROW;
  return (
    <div ref={box} className="relative" data-turning-points={file.match_id}>
      {[0, 1].map((side) => (
        <div key={side} className="relative" style={{ height: height(side) }} aria-label={sides[side]} role="group">
          {rows[side]!.map(({ tp, row }) => {
            const label = `${tpLabel(tp, t, lang)} · ${clock(tp.clock_sec, file.periods as Period[])} · ${tp.team}${
              tp.player_id ? ` · ${playerName(file, tp.player_id)}` : ""
            }`;
            return (
              <button
                key={`${tp.kind}-${tp.event_id ?? tp.insight_id}`}
                type="button"
                title={label}
                aria-label={label}
                data-tp={tp.kind}
                data-event-id={tp.event_id}
                data-insight-id={tp.insight_id}
                onClick={() => onSelect({ kind: "tp", tp })}
                className={cx(
                  "absolute flex -translate-x-1/2 items-center justify-center rounded-full border hover:border-accent-line",
                  tp.kind === "goal"
                    ? "h-8 w-8 border-ink-2 bg-surface-4 text-ink"
                    : tp.kind === "sub"
                      ? "h-7 w-7 border-line bg-surface-2 text-ink-3"
                      : "h-7 w-7 border-line bg-surface-2 text-ink-2",
                )}
                style={{
                  left: `${(tp.clock_sec / dur) * 100}%`,
                  [side === 0 ? "bottom" : "top"]: row * ROW + 1,
                }}
              >
                <Icon name={tpIcon(tp)} size={18} />
              </button>
            );
          })}
        </div>
      ))}
      <div className="pointer-events-none absolute inset-x-0" style={{ top: height(0) }} aria-hidden="true">
        <div className="relative h-px bg-line-strong">
          {ht !== null && <span className="absolute -top-1.5 h-3 w-px bg-ink-3" style={{ left: `${ht}%` }} />}
        </div>
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-ink-3" aria-hidden="true">
        <span className="inline-flex items-center gap-1">
          <TeamBadge code={sides[0]!} size={16} named /> {sides[0]} ↑ · {sides[1]} ↓
        </span>
        <span>{clock(dur, file.periods as Period[])}</span>
      </div>
    </div>
  );
}

const amountOf = (file: MatchFile, ins: Insight) => file.claims.filter((c) => c.claim_id === ins.claim_id).at(-1);

/** Longest sentence a recap card shows; a longer one stays in the evidence drawer. */
export const CARD_SENTENCE_WORDS = 22;

/** The card's one short sentence: the tone that is shorter in English, shown only when it has at
 * most CARD_SENTENCE_WORDS words in every language, so switching language never hides or shows a
 * sentence (or its numbers). */
export function cardSentence(ins: Insight, lang: string): string | null {
  const n = (s: string) => s.split(/\s+/).filter(Boolean).length;
  const tones = (["casual", "analyst"] as const).filter((tone) => textOf(ins.text.rendered, "en", tone));
  const tone = tones.sort((a, b) => n(textOf(ins.text.rendered, "en", a)) - n(textOf(ins.text.rendered, "en", b)))[0];
  if (!tone) return null;
  const langs = Object.keys(ins.text.rendered) as "en"[];
  if (langs.some((l) => n(textOf(ins.text.rendered, l, tone)) > CARD_SENTENCE_WORDS)) return null;
  return textOf(ins.text.rendered, lang as "en", tone) || null;
}

export function RecapCard({
  file,
  ins,
  onSelect,
}: {
  file: MatchFile;
  ins: Insight;
  onSelect: (s: Selection) => void;
}) {
  const { t, lang } = useT();
  const family = ins.insight_type === "tactical_pattern" ? (ins.payload.family ?? null) : null;
  const claim = amountOf(file, ins);
  const lane = typeof ins.payload.metrics?.lane === "string" ? ins.payload.metrics.lane : null;
  const label = family ? patternLabel(family, lang) : typeLabel(ins.insight_type, lang);
  const points = ins.payload.points ?? [];
  const side = ins.teams.primary === file.header.home.code ? "home" : "away";
  const sentence = cardSentence(ins, lang);
  return (
    <article
      data-insight-id={ins.insight_id}
      data-claim-id={ins.claim_id}
      data-type={ins.insight_type}
      data-family={family ?? undefined}
      data-budget="card"
      className="flex min-w-0 flex-col gap-2 rounded-2xl border border-line bg-surface-2 p-3"
    >
      <div className="flex items-center gap-2 text-[12px] font-semibold text-ink-2">
        <Icon name={insightIcon(ins.insight_type, claim?.metric, lane, family)} size={18} />
        <h3 className="min-w-0 flex-1 truncate text-[13.5px] text-ink">{label}</h3>
        <TeamBadge code={ins.teams.primary} size={20} />
        <time className="num text-ink-3">{clock(ins.clock.start_sec, file.periods as Period[])}</time>
      </div>
      {points.length > 0 ? (
        <svg
          viewBox="-1 -1 107 70"
          className="block h-auto w-full"
          role="img"
          aria-label={`${label}: ${t("evidence_title")}`}
          data-card-pitch
        >
          <Arrowheads id={`rc-${ins.insight_id}`} />
          <PitchLines />
          <InsightLayer insight={ins} side={side} markerId={`rc-${ins.insight_id}`} />
        </svg>
      ) : (
        claim?.amount !== undefined && (
          <div className="display num text-[30px] font-semibold leading-none text-ink" data-amount>
            {num(claim.amount, lang)}
          </div>
        )
      )}
      {sentence && (
        <p className="text-[13.5px] leading-snug text-ink-2" lang={lang}>
          {sentence}
        </p>
      )}
      <button
        type="button"
        data-evidence={ins.insight_id}
        aria-label={`${t("open_evidence")}: ${label}`}
        title={t("open_evidence")}
        onClick={() => onSelect({ kind: "card", id: ins.insight_id })}
        className="mt-auto inline-flex h-9 w-9 items-center justify-center self-end rounded-full border border-line text-ink-2 hover:border-accent-line hover:text-ink"
      >
        <Icon name="evidence-drawer" size={18} />
      </button>
    </article>
  );
}

const ROW_H = 40;
const VIEW_H = 440;

/** Virtualised, keyboard-navigable event log (ArrowUp/Down, PageUp/Down, Home/End, Enter). */
export function EventLog({
  file,
  events,
  onSelect,
  atClock,
}: {
  file: MatchFile;
  events: LogEvent[];
  onSelect: (s: Selection) => void;
  /** open at the first logged event at or after this clock (a replay link, ?t=) */
  atClock?: number;
}) {
  const { t, lang } = useT();
  const [type, setType] = useState<string>("all");
  // a replay link (?t=) opens at the first logged event at or after its clock
  const [start] = useState(() =>
    atClock == null
      ? 0
      : Math.max(
          0,
          events.findIndex((e) => e.clock_sec >= atClock),
        ),
  );
  const [active, setActive] = useState(start);
  const [top, setTop] = useState(start * ROW_H);
  const box = useRef<HTMLDivElement>(null);
  const types = useMemo(() => [...new Set(events.map((e) => e.event_type))].sort(), [events]);
  const shown = useMemo(() => (type === "all" ? events : events.filter((e) => e.event_type === type)), [events, type]);
  const pick = (ty: string) => {
    setType(ty);
    setActive(0);
    setTop(0);
    if (box.current) box.current.scrollTop = 0;
  };
  const first = Math.max(0, Math.floor(top / ROW_H) - 4);
  const last = Math.min(shown.length, Math.ceil((top + VIEW_H) / ROW_H) + 4);
  const move = (i: number) => {
    const n = Math.max(0, Math.min(shown.length - 1, i));
    setActive(n);
    const el = box.current;
    if (!el) return;
    if (n * ROW_H < el.scrollTop) el.scrollTop = n * ROW_H;
    else if ((n + 1) * ROW_H > el.scrollTop + VIEW_H) el.scrollTop = (n + 1) * ROW_H - VIEW_H;
  };
  const key = (e: React.KeyboardEvent) => {
    const page = Math.floor(VIEW_H / ROW_H);
    const map: Record<string, number> = { ArrowDown: 1, ArrowUp: -1, PageDown: page, PageUp: -page };
    if (e.key in map) move(active + map[e.key]!);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(shown.length - 1);
    else if (e.key === "Enter" && shown[active]) onSelect({ kind: "event", id: shown[active]!.event_id });
    else return;
    e.preventDefault();
  };
  useEffect(() => {
    if (atClock == null) return;
    if (box.current) box.current.scrollTop = start * ROW_H;
    document.getElementById("log")?.scrollIntoView({ block: "start" });
  }, [atClock, start]);
  const omitted = file.events.omitted_types;
  return (
    <div data-event-log={file.match_id} data-at-clock={atClock ?? undefined}>
      <div role="toolbar" aria-label={t("log_filter")} className="mb-2 flex flex-wrap gap-1.5">
        {["all", ...types].map((ty) => {
          const icon = ty === "all" ? null : eventIcon(ty);
          return (
            <button
              key={ty}
              type="button"
              aria-pressed={type === ty}
              data-log-type={ty}
              title={ty === "all" ? t("log_all") : words(ty)}
              onClick={() => pick(ty)}
              className={cx(
                "inline-flex min-h-[36px] min-w-[36px] items-center justify-center gap-1 rounded-full border px-2.5 text-[12px] font-semibold",
                type === ty ? "border-accent-line bg-accent-soft text-ink" : "border-line text-ink-2 hover:text-ink",
              )}
            >
              {icon ? <Icon name={icon} size={16} /> : null}
              <span className={icon ? "sr-only" : undefined}>{ty === "all" ? t("log_all") : words(ty)}</span>
            </button>
          );
        })}
      </div>
      <p className="mb-1 text-[12px] text-ink-3">
        {fill(t("log_shown"), { n: num(shown.length, lang), total: num(file.events.total, lang) })}
      </p>
      <div
        ref={box}
        role="listbox"
        tabIndex={0}
        aria-label={t("hub_log")}
        aria-activedescendant={shown[active] ? `ev-${shown[active]!.event_id}` : undefined}
        onKeyDown={key}
        onScroll={(e) => setTop((e.target as HTMLDivElement).scrollTop)}
        className="relative overflow-y-auto rounded-xl border border-line bg-surface-2"
        style={{ height: Math.min(VIEW_H, Math.max(ROW_H, shown.length * ROW_H)) }}
      >
        <div style={{ height: shown.length * ROW_H }} className="relative">
          {shown.slice(first, last).map((e, k) => {
            const i = first + k;
            const icon = eventIcon(e.event_type, e.outcome);
            return (
              <div
                key={e.event_id}
                id={`ev-${e.event_id}`}
                role="option"
                aria-selected={i === active}
                data-log-row={e.event_id}
                onClick={() => {
                  setActive(i);
                  onSelect({ kind: "event", id: e.event_id });
                }}
                className={cx(
                  "absolute inset-x-0 flex cursor-pointer items-center gap-2 border-b border-line px-3 text-[12.5px]",
                  i === active ? "bg-surface-3 text-ink" : "text-ink-2",
                )}
                style={{ top: i * ROW_H, height: ROW_H }}
              >
                <span className="num w-[52px] shrink-0 text-ink-3">{clock(e.clock_sec, file.periods as Period[])}</span>
                {e.team && <TeamBadge code={e.team} size={18} named />}
                <span className="inline-flex w-5 justify-center text-ink-3">
                  {icon && <Icon name={icon} size={16} />}
                </span>
                <span className="w-[92px] shrink-0 truncate">{words(e.event_type)}</span>
                <span className="min-w-0 flex-1 truncate">{playerName(file, e.player_id)}</span>
                <span className="hidden shrink-0 text-ink-3 sm:inline">{words(e.outcome)}</span>
              </div>
            );
          })}
        </div>
      </div>
      {omitted.length > 0 && (
        <p className="mt-2 text-[12px] text-ink-3">
          {fill(t("log_omitted"), { types: omitted.map(words).join(", ") })}
        </p>
      )}
    </div>
  );
}

function EvidenceList({
  file,
  ids,
  rows,
}: {
  file: MatchFile;
  ids: readonly string[];
  rows: Record<string, EvidenceRow>;
}) {
  const { t } = useT();
  return (
    <ol className="flex flex-col gap-1 text-[12.5px]" data-evidence-list>
      {ids.map((id) => {
        const r = rows[id];
        return (
          <li key={id} data-event-id={id} className="flex flex-wrap items-baseline gap-x-2 border-b border-line py-1">
            <span className="num w-[52px] text-ink-3">
              {r && r.match_id === file.match_id ? clock(r.clock_sec, file.periods as Period[]) : ""}
            </span>
            <span className="text-ink">{r ? words(r.event_type) : ""}</span>
            <span className="text-ink-2">{r?.player ?? ""}</span>
            {r && r.match_id !== file.match_id && <span className="text-ink-3">({t("evidence_other_match")})</span>}
            <span className="ml-auto font-mono text-[11px] text-ink-3">{id}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function ClaimTable({ file, ids }: { file: MatchFile; ids?: Set<string> }) {
  const { t, lang } = useT();
  const rows = ids ? file.claims.filter((c) => ids.has(c.claim_id)) : file.claims;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-left text-[12.5px]" data-table="match-claims">
        <thead className="text-ink-3">
          <tr>
            <th scope="col" className="py-1.5 pr-2">
              {t("tbl_claim")}
            </th>
            <th scope="col" className="py-1.5 pr-2">
              {t("tbl_metric")}
            </th>
            <th scope="col" className="py-1.5 pr-2 text-right">
              {t("tbl_attempt")}
            </th>
            <th scope="col" className="py-1.5 pr-2">
              {t("tbl_verdict")}
            </th>
            <th scope="col" className="py-1.5">
              {t("tbl_rules")}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.claim_id} data-claim-id={c.claim_id} className="border-t border-line align-top">
              <td className="max-w-[260px] break-all py-1.5 pr-2 font-mono text-[11px] text-ink-2">{c.claim_id}</td>
              <td className="py-1.5 pr-2">{words(c.metric)}</td>
              <td className="num py-1.5 pr-2 text-right">{num(c.attempt, lang)}</td>
              <td className="py-1.5 pr-2">{words(c.status)}</td>
              <td className="py-1.5 text-ink-3">{c.rule_ids.map(words).join(", ") || "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Evidence drawer for a turning point, a card or a log row. */
export function HubDrawer({
  file,
  cards,
  rows,
  selection,
  onClose,
}: {
  file: MatchFile;
  cards: Insight[];
  rows: Record<string, EvidenceRow>;
  selection: Selection;
  onClose: () => void;
}) {
  const { t, lang } = useT();
  let title = "";
  let body: ReactNode = null;
  const cardBody = (ins: Insight) => {
    const chain = new Set<string>();
    let c = file.claims.find((x) => x.claim_id === ins.claim_id);
    while (c) {
      chain.add(c.claim_id);
      c = c.revision_of ? file.claims.find((x) => x.claim_id === c!.revision_of) : undefined;
    }
    return (
      <div className="flex flex-col gap-4">
        <p className="text-[14px] leading-snug text-ink" lang={lang}>
          {textOf(ins.text.rendered, lang, "analyst")}
        </p>
        <ClaimTable file={file} ids={chain} />
        <EvidenceList file={file} ids={ins.evidence_event_ids} rows={rows} />
      </div>
    );
  };
  if (selection?.kind === "card" || (selection?.kind === "tp" && selection.tp.insight_id)) {
    const id = selection.kind === "card" ? selection.id : selection.tp.insight_id!;
    const ins = cards.find((c) => c.insight_id === id);
    if (ins) {
      const family = ins.insight_type === "tactical_pattern" ? (ins.payload.family ?? null) : null;
      title = family ? patternLabel(family, lang) : typeLabel(ins.insight_type, lang);
      body = cardBody(ins);
    }
  } else if (selection?.kind === "tp" || selection?.kind === "event") {
    const id = selection.kind === "tp" ? selection.tp.event_id! : selection.id;
    const r = rows[id];
    title = selection.kind === "tp" ? tpLabel(selection.tp, t, lang) : r ? words(r.event_type) : id;
    const sub =
      selection.kind === "tp" && selection.tp.kind === "sub"
        ? fill(t("tp_on_off"), {
            off: playerName(file, selection.tp.player_id),
            on: playerName(file, selection.tp.on_player_id),
          })
        : null;
    const citing = new Set(
      file.claims
        .filter((c) =>
          c.evidence.some(
            (e) => (typeof e === "number" ? `${file.match_id}_e${String(e).padStart(5, "0")}` : e) === id,
          ),
        )
        .map((c) => c.claim_id),
    );
    body = (
      <div className="flex flex-col gap-4">
        {sub && <p className="text-[14px] text-ink">{sub}</p>}
        <EvidenceList file={file} ids={[id]} rows={rows} />
        {citing.size > 0 && <ClaimTable file={file} ids={citing} />}
      </div>
    );
  }
  return (
    <Sheet
      open={selection !== null}
      onOpenChange={(o) => !o && onClose()}
      id="hub-evidence"
      eyebrow={t("evidence_title")}
      title={title}
      closeLabel={t("close")}
    >
      {body}
    </Sheet>
  );
}
