// The Match Hub's "Insights and patterns" panel. Two tabs (Insights: every recap card that is not a
// pattern finding; Patterns: the pattern findings, with one filter chip per family present), pages
// of PER_PAGE cards with Previous / Next and "Page k of n". From 1100 px the hub shows it as a sticky
// side panel of viewport height whose card list scrolls inside (a focusable, named region); below
// that it is a section under the scoreline. The tab, family and page size are remembered for the
// session in memory only (no storage). A page change returns the list to its top.
import { useEffect, useRef, useState } from "react";
import { cx } from "../../lib/cx";
import { patternIcon, Icon } from "../../icons";
import { num } from "../../lib/format";
import { patternLabel, useT } from "../../lib/i18n";
import type { Insight } from "../../types/ui";
import type { MatchFile } from "../../data/matches";
import { fill, RecapCard, type Selection } from "./parts";

export const PAGE_SIZES = [5, 10] as const;
type Tab = "insights" | "patterns";

/** Session memory (module scope, never persisted). */
export const panelMemory: { tab: Tab; family: string; perPage: number } = {
  tab: "insights",
  family: "all",
  perPage: 5,
};

/** Updates the session memory (outside React state: it only seeds the next mount). */
export function remember(v: Partial<typeof panelMemory>) {
  Object.assign(panelMemory, v);
}

export const isPattern = (c: Insight) => c.insight_type === "tactical_pattern";
const familyOf = (c: Insight) => String(c.payload.family ?? "");

/** The cards of one tab and family filter, and the page count (pure, unit-tested). */
export function panelPage(cards: readonly Insight[], tab: Tab, family: string, perPage: number, page: number) {
  const list = cards.filter((c) =>
    tab === "patterns" ? isPattern(c) && (family === "all" || familyOf(c) === family) : !isPattern(c),
  );
  const pages = Math.max(1, Math.ceil(list.length / perPage));
  const p = Math.min(Math.max(0, page), pages - 1);
  return { list, pages, page: p, shown: list.slice(p * perPage, (p + 1) * perPage) };
}

export function InsightsPanel({
  file,
  cards,
  onSelect,
  side,
}: {
  file: MatchFile;
  cards: Insight[];
  onSelect: (s: Selection) => void;
  /** true: the sticky, viewport-high side panel (1100 px and wider) */
  side: boolean;
}) {
  const { t, lang } = useT();
  const nPat = cards.filter(isPattern).length;
  const [tab, setTabState] = useState<Tab>(nPat ? panelMemory.tab : "insights");
  const [family, setFamilyState] = useState(panelMemory.family);
  const [perPage, setPerPageState] = useState(panelMemory.perPage);
  const [page, setPage] = useState(0);
  const scroller = useRef<HTMLDivElement>(null);
  const families = [...new Set(cards.filter(isPattern).map(familyOf))].sort();
  const fam = families.includes(family) ? family : "all";
  const v = panelPage(cards, tab, fam, perPage, page);
  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = 0;
  }, [v.page, tab, fam, perPage]);
  const setTab = (x: Tab) => {
    remember({ tab: x });
    setTabState(x);
    setPage(0);
  };
  const setFamily = (x: string) => {
    remember({ family: x });
    setFamilyState(x);
    setPage(0);
  };
  const setPerPage = (x: number) => {
    remember({ perPage: x });
    setPerPageState(x);
    setPage(0);
  };
  const tabs: [Tab, string, number][] = [
    ["insights", t("panel_insights"), cards.length - nPat],
    ["patterns", t("panel_patterns"), nPat],
  ];
  const chip = (active: boolean) =>
    cx(
      "inline-flex min-h-[32px] items-center gap-1.5 rounded-full border px-3 text-[12px] font-semibold",
      active ? "border-accent-line bg-accent/10 text-ink" : "border-line text-ink-3 hover:text-ink",
    );
  return (
    <section
      id="insights"
      aria-labelledby="insights-h"
      data-panel={side ? "side" : "section"}
      data-budget="cards"
      className={cx(
        "flex min-w-0 flex-col rounded-2xl border border-line bg-surface-1",
        side ? "sticky top-[80px] h-[calc(100vh-96px)]" : "scroll-mt-20",
      )}
    >
      <div className="flex flex-col gap-2.5 border-b border-line px-4 pb-3 pt-4">
        <div className="flex items-baseline justify-between gap-2">
          <h2 id="insights-h" className="text-[15px] font-semibold text-ink">
            {t("panel_title")}
          </h2>
          <p className="text-[12px] text-ink-3">
            {fill(t("recap_shown"), { k: num(cards.length, lang), n: num(file.stream_counts.insights, lang) })}
          </p>
        </div>
        <div role="tablist" aria-label={t("panel_title")} className="flex gap-1.5">
          {tabs.map(([k, label, n]) => (
            <button
              key={k}
              type="button"
              role="tab"
              id={`tab-${k}`}
              aria-selected={tab === k}
              aria-controls="insights-list"
              disabled={n === 0}
              data-tab={k}
              onClick={() => setTab(k)}
              className={cx(chip(tab === k), "disabled:opacity-40")}
            >
              {label} <span className="num text-ink-3">{num(n, lang)}</span>
            </button>
          ))}
        </div>
        {tab === "patterns" && families.length > 1 && (
          <div role="group" aria-label={t("panel_family")} className="flex flex-wrap gap-1.5" data-family-chips>
            <button
              type="button"
              aria-pressed={fam === "all"}
              onClick={() => setFamily("all")}
              className={chip(fam === "all")}
            >
              {t("panel_all")}
            </button>
            {families.map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={fam === f}
                data-family-chip={f}
                onClick={() => setFamily(f)}
                className={chip(fam === f)}
              >
                <Icon name={patternIcon(f)} size={16} />
                {patternLabel(f, lang)}
              </button>
            ))}
          </div>
        )}
      </div>
      <div
        ref={scroller}
        id="insights-list"
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
        tabIndex={0}
        data-scroll-region
        className={cx(
          "flex flex-col gap-3 p-4 outline-none focus-visible:ring-2 focus-visible:ring-accent-line",
          side && "min-h-0 flex-1 overflow-y-auto",
        )}
      >
        {v.shown.map((ins) => (
          <RecapCard key={ins.insight_id} file={file} ins={ins} onSelect={onSelect} />
        ))}
      </div>
      <nav
        aria-label={t("panel_pages")}
        className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5 text-[12.5px]"
        data-pager
      >
        <button
          type="button"
          onClick={() => setPage(v.page - 1)}
          disabled={v.page === 0}
          className="min-h-[36px] rounded-full border border-line px-3 font-semibold text-ink-2 hover:text-ink disabled:opacity-40"
        >
          ← {t("panel_prev")}
        </button>
        <span className="text-ink-3" aria-live="polite" data-page-label>
          {fill(t("panel_page"), { k: num(v.page + 1, lang), n: num(v.pages, lang) })}
        </span>
        <span className="flex items-center gap-1" role="group" aria-label={t("panel_per_page")}>
          {PAGE_SIZES.map((n) => (
            <button
              key={n}
              type="button"
              aria-pressed={perPage === n}
              onClick={() => setPerPage(n)}
              className={cx(
                "num min-h-[32px] min-w-[32px] rounded-full border text-[12px] font-semibold",
                perPage === n ? "border-accent-line text-ink" : "border-line text-ink-3",
              )}
            >
              {n}
            </button>
          ))}
        </span>
        <button
          type="button"
          onClick={() => setPage(v.page + 1)}
          disabled={v.page >= v.pages - 1}
          className="min-h-[36px] rounded-full border border-line px-3 font-semibold text-ink-2 hover:text-ink disabled:opacity-40"
        >
          {t("panel_next")} →
        </button>
      </nav>
    </section>
  );
}
