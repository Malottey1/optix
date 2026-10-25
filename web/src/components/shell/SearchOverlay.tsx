// Global search: the header button or Ctrl/Cmd+K opens a dialog (Radix: focus trapped, Escape
// closes, focus returns to what had it). It searches teams, players and fixtures from ui.json
// (teams.teams, players, fixtures), case- and accent-blind; every word typed must match. Results are
// grouped (teams, players, fixtures), ranked inside a group by how they match (code, then the start
// of the name, then the start of a word, then anywhere), arrows move, Enter opens, and a polite live
// region reads the result count.
import * as Dialog from "@radix-ui/react-dialog";
import { useContext, useEffect, useId, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { DataContext } from "../../data/context";
import { Icon, type IconName } from "../../icons";
import { cx } from "../../lib/cx";
import { num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import type { UiData } from "../../types/ui";
import { Glyph } from "../icons";

// local, so the shell does not pull the Match Hub module into the entry chunk
const fill = (s: string, vars: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

export type Group = "teams" | "players" | "fixtures";
export interface Entry {
  group: Group;
  id: string;
  to: string;
  /** what is shown and announced */
  label: string;
  sub: string;
  /** the code (team code, shirt-less player id), matched first */
  code: string;
  /** the words that are searched: names and codes */
  text: string[];
}

const GROUPS: Group[] = ["teams", "players", "fixtures"];
const ICON: Record<Group, IconName> = { teams: "teams", players: "players", fixtures: "scrub" };
const LABEL: Record<Group, Key> = { teams: "search_teams", players: "search_players", fixtures: "search_fixtures" };
/** Results kept per group. */
export const PER_GROUP = { teams: 5, players: 8, fixtures: 6 } as const;

export const fold = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

/** The index (pure): one entry per team, player and fixture. */
export function searchIndex(ui: UiData): Entry[] {
  const names = Object.fromEntries(ui.teams.teams.map((t) => [t.code, t.name]));
  return [
    ...ui.teams.teams.map((t) => ({
      group: "teams" as const,
      id: t.code,
      to: `/teams/${t.code}`,
      label: t.name,
      sub: t.code,
      code: t.code,
      text: [t.name, t.code],
    })),
    ...ui.players.map((p) => ({
      group: "players" as const,
      id: p.id,
      to: `/players/${p.id}`,
      label: p.name,
      sub: `${p.team} · ${p.position}`,
      code: p.id,
      text: [p.name, p.team, names[p.team] ?? ""],
    })),
    ...ui.fixtures.map(([id, mw, h, a, hg, ag]) => ({
      group: "fixtures" as const,
      id,
      to: `/match/${id}`,
      label: `${h} ${hg}–${ag} ${a}`,
      sub: String(mw),
      code: `${h} ${a}`,
      text: [h, a, names[h] ?? "", names[a] ?? ""],
    })),
  ];
}

/** Rank of one entry for one query word: 0 code, 1 start of a field, 2 start of a word, 3 inside; null
 * when it does not match. */
function rankWord(e: Entry, w: string): number | null {
  if (e.code.split(" ").some((c) => fold(c) === w)) return 0;
  const fields = e.text.map(fold);
  if (fields.some((f) => f.startsWith(w))) return 1;
  if (fields.some((f) => f.split(/[\s'-]+/).some((p) => p.startsWith(w)))) return 2;
  if (fields.some((f) => f.includes(w))) return 3;
  return null;
}

/** The ranked, grouped results of a query (pure, unit-tested). */
export function search(index: readonly Entry[], q: string): Entry[] {
  const words = fold(q).split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const scored: [Entry, number][] = [];
  for (const e of index) {
    let total = 0;
    let ok = true;
    for (const w of words) {
      const r = rankWord(e, w);
      if (r == null) {
        ok = false;
        break;
      }
      total += r;
    }
    if (ok) scored.push([e, total]);
  }
  return GROUPS.flatMap((g) =>
    scored
      .filter(([e]) => e.group === g)
      .sort((a, b) => a[1] - b[1] || a[0].label.localeCompare(b[0].label) || a[0].id.localeCompare(b[0].id))
      .slice(0, PER_GROUP[g])
      .map(([e]) => e),
  );
}

export function SearchOverlay({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  // the shell sits outside the loaded data: until it loads, the index is empty
  const m = useContext(DataContext);
  const { t, lang } = useT();
  const navigate = useNavigate();
  const uid = useId().replace(/:/g, "");
  const opener = useRef<HTMLElement | null>(null);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const index = useMemo(() => (m ? searchIndex(m.ui) : []), [m]);
  const results = useMemo(() => search(index, q), [index, q]);
  const cur = results[Math.min(active, results.length - 1)];
  const go = (e: Entry | undefined) => {
    if (!e) return;
    onOpenChange(false);
    navigate(e.to);
  };
  const onKey = (ev: React.KeyboardEvent) => {
    if (!results.length) return;
    if (ev.key === "ArrowDown") setActive((i) => (i + 1) % results.length);
    else if (ev.key === "ArrowUp") setActive((i) => (i - 1 + results.length) % results.length);
    else if (ev.key === "Home" && ev.ctrlKey) setActive(0);
    else if (ev.key === "Enter") go(cur);
    else return;
    ev.preventDefault();
  };
  useEffect(() => {
    document.getElementById(`${uid}-${cur?.group}-${cur?.id}`)?.scrollIntoView({ block: "nearest" });
  }, [cur, uid]);
  const optionId = (e: Entry) => `${uid}-${e.group}-${e.id}`;
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setQ("");
          setActive(0);
        }
        onOpenChange(o);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="overlay fixed inset-0 z-50 bg-black/65 backdrop-blur-[2px]" />
        <Dialog.Content
          id="search-overlay"
          className="fixed inset-x-3 top-[10vh] z-50 mx-auto flex max-h-[75vh] max-w-[620px] flex-col rounded-2xl border border-line bg-surface-1 elev-2 outline-none"
          onOpenAutoFocus={() => {
            opener.current = document.activeElement as HTMLElement | null;
          }}
          onCloseAutoFocus={(e) => {
            const el = opener.current;
            opener.current = null;
            if (el && el !== document.body && el.isConnected) {
              e.preventDefault();
              el.focus();
            }
          }}
        >
          <Dialog.Title className="sr-only">{t("search_label")}</Dialog.Title>
          <Dialog.Description className="sr-only">{t("search_hint")}</Dialog.Description>
          <div className="flex items-center gap-2 border-b border-line px-4">
            <Icon name="search" className="h-5 w-5 text-ink-3" />
            <input
              type="search"
              role="combobox"
              aria-expanded={results.length > 0}
              aria-controls={`${uid}-list`}
              aria-activedescendant={cur ? optionId(cur) : undefined}
              aria-autocomplete="list"
              aria-label={t("search_label")}
              placeholder={t("search_label")}
              autoComplete="off"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setActive(0);
              }}
              onKeyDown={onKey}
              data-search-input
              className="h-14 min-w-0 flex-1 bg-transparent text-[16px] text-ink outline-none placeholder:text-ink-3"
            />
            <Dialog.Close
              aria-label={t("close")}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-ink-2 hover:text-ink"
            >
              <Glyph name="close" className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <p className="sr-only" aria-live="polite" data-search-count={results.length}>
            {q.trim() ? fill(t("search_count"), { n: num(results.length, lang) }) : ""}
          </p>
          <div id={`${uid}-list`} role="listbox" aria-label={t("search_label")} className="overflow-y-auto p-2">
            {GROUPS.map((g) => {
              const rows = results.filter((e) => e.group === g);
              if (!rows.length) return null;
              return (
                <div key={g} role="group" aria-labelledby={`${uid}-${g}-h`} data-search-group={g}>
                  <p id={`${uid}-${g}-h`} className="eyebrow px-2 pb-1 pt-2">
                    {t(LABEL[g])}
                  </p>
                  {rows.map((e) => {
                    const on = e === cur;
                    return (
                      <div
                        key={e.id}
                        id={optionId(e)}
                        role="option"
                        aria-selected={on}
                        data-search-result={e.id}
                        onMouseEnter={() => setActive(results.indexOf(e))}
                        onClick={() => go(e)}
                        className={cx(
                          "flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl px-2 py-1.5",
                          on ? "bg-surface-3 text-ink" : "text-ink-2",
                        )}
                      >
                        <Icon name={ICON[g]} size={18} className="shrink-0 text-ink-3" />
                        <span className="min-w-0 flex-1 truncate text-[14px] font-semibold">{e.label}</span>
                        <span className="shrink-0 text-[12px] text-ink-3">
                          {g === "fixtures" ? fill(t("search_mw"), { n: num(Number(e.sub), lang) }) : e.sub}
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            })}
            {q.trim() && !results.length && <p className="px-2 py-4 text-[13px] text-ink-3">{t("search_none")}</p>}
          </div>
          <p className="border-t border-line px-4 py-2 text-[11.5px] text-ink-3">{t("search_hint")}</p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
