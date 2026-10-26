// The verified stream: one card per insight, newest first. Each card has the plain-language
// headline (the stream's casual sentence in the chosen language), an evidence summary, the
// standard stat a with-context card holds back, and, for rewritten cards, Before / After with the
// rule's one-sentence reason. "Open evidence" opens the drawer with the exact events.
// Fan view (state/view.ts): the top cards by lib/personalize.ts, each with headline, visual and a
// "Verified" tick that opens the same drawer; chips, attempts and Before / After stay in Analyst view.
// A followed player or a focus metric filters the stream the same way in both views.
import { AnimatePresence, m as motion } from "motion/react";
import { memo, useMemo, useRef, useState } from "react";
import { Glyph } from "../../components/icons";
import { Icon } from "../../icons";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { Chip, StatusChip, TeamDot, type Status } from "../../components/ui/badge";
import { Panel } from "../../components/ui/card";
import { Segmented } from "../../components/ui/segmented";
import { Empty } from "../../components/ui/skeleton";
import { Tip } from "../../components/ui/tooltip";
import { useData } from "../../data/context";
import { involvedFromEvents } from "../../data/events";
import { useEventFile } from "../../data/matchContext";
import { SHOWCASE_ID } from "../../data/matches";
import { personalize } from "../../lib/personalize";
import { useFavourites } from "../../state/favourites";
import { useView } from "../../state/view";
import { cx } from "../../lib/cx";
import { clock, num, words } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import { select, useReplay } from "../../state/replay";
import { useSettings } from "../../state/settings";
import type { Insight } from "../../types/ui";
import { CardVisual } from "./CardVisual";
import { PCT_METRICS, cardChip, evidenceMix, reasonFor, statusOf, textOf } from "./shared";

export const STATUS_KEY: Record<Status, Key> = {
  published: "verified",
  published_with_context: "with_context",
  revised: "rewritten",
  blocked: "blocked",
};

function EvidenceSummary({ ins }: { ins: Insight }) {
  const m = useData();
  const { t, lang } = useT();
  const final = m.chain(ins.claim_id).at(-1)?.claim;
  const mix = evidenceMix(m, ins.evidence_event_ids);
  const n = ins.evidence_event_ids.length;
  const w = final?.window;
  return (
    <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-ink-3" data-role="evidence-summary">
      <Icon name="evidence-drawer" size={14} />
      <span>
        <b className="num font-semibold text-ink-2">{num(n, lang)}</b> {n === 1 ? t("event") : t("events")}
      </span>
      {mix.length > 0 && (
        <span className="min-w-0">
          (
          {mix.map(([type, c], i) => (
            <span key={type}>
              {i > 0 && ", "}
              {words(type)} <span className="num">{num(c, lang)}</span>
            </span>
          ))}
          )
        </span>
      )}
      {final && (
        <span className="whitespace-nowrap">
          ·{" "}
          {w && final.scope === "window" ? (
            <span className="num">
              {clock(w.from_sec, m.timeline.periods)}–{clock(w.to_sec, m.timeline.periods)}
            </span>
          ) : (
            words(final.scope)
          )}
        </span>
      )}
      {ins.payload.confidence && (
        <span className="whitespace-nowrap">
          · {t("confidence")} <b className="font-semibold text-ink-2">{ins.payload.confidence}</b>
        </span>
      )}
    </p>
  );
}

function EvidenceInline({ ins }: { ins: Insight }) {
  const m = useData();
  const rows = m.evidenceOf(ins.evidence_event_ids).slice(0, 4);
  if (!rows.length) return null;
  return (
    <ul className="mt-3 space-y-1 border-t border-line pt-3 text-[12px] text-ink-2" data-evidence-inline>
      {rows.map((e) => (
        <li key={e.event_id} data-event-id={e.event_id} className="flex min-w-0 gap-2">
          <span className="num w-[4.2rem] shrink-0 text-ink-3">
            {e.match_id === m.timeline.match_id ? clock(e.clock_sec, m.timeline.periods) : e.match_id}
          </span>
          <span className="min-w-0 truncate">
            <b className="font-semibold text-ink">{e.player ?? e.team}</b> · {words(e.event_type)} · {words(e.outcome)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function Rewritten({
  ins,
  view,
  setView,
}: {
  ins: Insight;
  view: "before" | "after";
  setView: (v: "before" | "after") => void;
}) {
  const m = useData();
  const { t, lang } = useT();
  const rw = m.ui.rewrites[ins.insight_id]!;
  const reason = reasonFor(m, rw.rule_ids, lang);
  return (
    <div className="mt-3 rounded-xl border border-revise/30 bg-revise-soft px-3 py-2.5" data-rewrite>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12px] font-semibold text-revise">
          {view === "before" ? t("original") : t("allowed")}
        </span>
        <Segmented
          label={t("rewritten")}
          name={`rw-${ins.insight_id}`}
          value={view}
          onChange={setView}
          options={[
            { value: "before", label: t("before") },
            { value: "after", label: t("after") },
          ]}
        />
      </div>
      {reason && (
        <p className="mt-2 text-[12.5px] leading-snug text-ink-2" data-role="reason">
          <b className="font-semibold text-ink">{t("why")}:</b> {reason}
        </p>
      )}
    </div>
  );
}

export const InsightCard = memo(function InsightCard({
  ins,
  selected,
  onEvidence,
  fan = false,
}: {
  ins: Insight;
  selected: boolean;
  onEvidence: (id: string) => void;
  fan?: boolean;
}) {
  const m = useData();
  const { t, lang } = useT();
  const evidenceOpen = useSettings((s) => s.evidenceOpen);
  const [view, setView] = useState<"before" | "after">("after");
  const rw = m.ui.rewrites[ins.insight_id];
  const status = statusOf(m, ins);
  const before = Boolean(rw) && view === "before";
  const headline = before ? textOf(rw!.original, lang, "casual") : textOf(ins.text.rendered, lang, "casual");
  const attempts = m.chain(ins.claim_id).length;
  const chip = ins.context_chip;
  return (
    <article
      data-insight-id={ins.insight_id}
      data-claim-id={ins.claim_id}
      data-type={ins.insight_type}
      data-status={status}
      data-team={ins.teams.primary}
      aria-current={selected ? "true" : undefined}
      className={cx(
        "relative rounded-2xl border bg-surface-2 pad transition-colors",
        selected ? "border-accent-line ring-1 ring-accent/30" : "border-line hover:border-line-strong",
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "absolute inset-y-4 left-0 w-[3px] rounded-r-full",
          m.sideOf(ins.teams.primary) === "home" ? "bg-home" : "bg-away",
        )}
      />
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 text-[12px]">
        <time className="display text-[17px] font-semibold leading-none text-ink">
          {clock(ins.clock.start_sec, m.timeline.periods)}
        </time>
        <span className="inline-flex items-center gap-1.5 font-semibold text-ink-2">
          <TeamDot side={m.sideOf(ins.teams.primary)} />
          <TeamBadge code={ins.teams.primary} size={24} named />
          {ins.teams.primary}
        </span>
        {!fan && (
          <Chip>
            <Icon name={cardChip(m, ins, lang).icon} size={14} />
            {cardChip(m, ins, lang).label}
          </Chip>
        )}
        {fan ? (
          <button
            type="button"
            data-verified-tick={ins.insight_id}
            data-evidence={ins.insight_id}
            onClick={() => onEvidence(ins.insight_id)}
            aria-label={t("v_tick_open").replace("{label}", headline)}
            className="ml-auto inline-flex min-h-[32px] items-center gap-1 rounded-full border border-accent-line bg-accent-soft px-2.5 font-semibold text-accent hover:brightness-110"
          >
            <Icon name="verdict-passed" size={14} />
            {t("v_tick")}
          </button>
        ) : (
          <StatusChip status={status} label={t(STATUS_KEY[status])} className="ml-auto" />
        )}
      </div>
      <button
        type="button"
        onClick={() => select(selected ? null : ins.insight_id)}
        aria-pressed={selected}
        aria-label={`${t("show_on_pitch")}: ${headline}`}
        className="mt-2.5 block w-full rounded-lg text-left"
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.p
            key={before ? "before" : "after"}
            data-role="headline"
            lang={lang}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className={cx(
              "text-[15.5px] font-semibold leading-snug",
              before ? "text-ink-2 line-through decoration-block/70 decoration-2" : "text-ink",
            )}
          >
            {headline}
          </motion.p>
        </AnimatePresence>
      </button>
      <CardVisual ins={ins} />
      {fan ? null : (
        <>
          {rw && <Rewritten ins={ins} view={view} setView={setView} />}
          {chip?.standard_metric != null && chip.standard_value != null && !rw && (
            <Tip content={t("standard_note")}>
              <button
                type="button"
                className="mt-2.5 inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-0.5 rounded-lg border border-dashed border-line-strong px-2.5 py-1 text-left text-[12px] text-ink-3 hover:text-ink-2"
              >
                <span className="eyebrow !text-[10.5px]">{t("standard_stat")}</span>
                <span>
                  {words(chip.standard_metric)}{" "}
                  <b className="num font-semibold">
                    {num(chip.standard_value, lang)}
                    {PCT_METRICS.has(chip.standard_metric) ? "%" : ""}
                  </b>
                </span>
              </button>
            </Tip>
          )}
          <EvidenceSummary ins={ins} />
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-[12px] text-ink-3">
            <span>
              <span className="num font-semibold text-ink-2">{num(attempts, lang)}</span>{" "}
              {attempts === 1 ? t("attempts_one") : t("attempts_many")}
            </span>
            <button
              type="button"
              data-evidence={ins.insight_id}
              onClick={() => onEvidence(ins.insight_id)}
              className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 font-semibold text-ink-2 hover:border-accent-line hover:text-ink"
            >
              {t("open_evidence")}
              <Glyph name="arrow" className="h-3.5 w-3.5" />
            </button>
          </div>
          {evidenceOpen && <EvidenceInline ins={ins} />}
        </>
      )}
    </article>
  );
});

type Filter = "all" | "checked";

export function Feed({ onEvidence }: { onEvidence: (id: string) => void }) {
  const m = useData();
  const { t, lang } = useT();
  const n = useReplay((s) => m.visibleCount(s.t));
  const selected = useReplay((s) => s.selected);
  const [filter, setFilter] = useState<Filter>("all");
  const listRef = useRef<HTMLOListElement>(null);
  const { mode, metric } = useView();
  const focus = useView((s) => (s.focus && m.timeline.players[s.focus] ? s.focus : null));
  const clubs = useFavourites((s) => s.teams);
  const fan = mode === "fan";
  // the event file is fetched only while a player is followed
  const ev = useEventFile(focus ? SHOWCASE_ID : null);
  const involved = useMemo(() => (ev.data ? involvedFromEvents(ev.data) : {}), [ev.data]);
  const visible = m.insights.slice(0, n).filter((i) => fan || filter === "all" || statusOf(m, i) !== "published");
  const picked = personalize(visible, { mode, clubs, players: focus ? [focus] : [], metric }, involved);
  // newest first in both views (personalize chose and capped; the feed keeps the clock order)
  const shown = [...picked].reverse().sort((a, b) => b.clock.start_sec - a.clock.start_sec);
  return (
    <Panel
      id="feed-panel"
      title={t("stream")}
      className="flex min-h-0 flex-col lg:max-h-[calc(100vh-116px)]"
      bodyClassName="flex min-h-0 flex-1 flex-col"
      actions={
        <span
          id="feed-count"
          className="shrink-0 whitespace-nowrap rounded-full bg-accent-soft px-2.5 py-1 text-[12px] font-bold text-accent"
        >
          <span className="num">{num(n, lang)}</span> {t("insights")}
        </span>
      }
    >
      {!fan && (
        <Segmented<Filter>
          label={t("stream")}
          name="feed-filter"
          value={filter}
          onChange={setFilter}
          className="self-start"
          options={[
            { value: "all", label: t("filter_all") },
            { value: "checked", label: t("filter_checked") },
          ]}
        />
      )}
      {shown.length ? (
        <ol
          id="feed"
          ref={listRef}
          aria-live="polite"
          aria-relevant="additions"
          className="-mx-1 mt-3 flex min-h-0 flex-1 flex-col gap-flow overflow-y-auto px-1 pb-1"
        >
          <AnimatePresence initial={false}>
            {shown.map((ins) => (
              <motion.li
                key={ins.insight_id}
                layout="position"
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.22 }}
                data-insight-id={ins.insight_id}
              >
                <InsightCard ins={ins} selected={selected === ins.insight_id} onEvidence={onEvidence} fan={fan} />
              </motion.li>
            ))}
          </AnimatePresence>
        </ol>
      ) : (
        <Empty className="mt-3">
          {focus && n > 0 ? t("focus_none") : metric && n > 0 ? t("metric_feed_none") : t("none_yet")}
        </Empty>
      )}
    </Panel>
  );
}
