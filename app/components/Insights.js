// The verified insight stream: cards, the before/after view of rewritten claims, and the
// evidence drawer listing the exact events behind a claim.
import { html, React } from "../lib/html.js";
import { clock, cx, num } from "../lib/format.js";
import { useT } from "../lib/i18n.js";
import { select, useReplay } from "../lib/replay.js";
import { useSettings } from "../lib/settings.js";
import { Chip, Panel, Segmented, StatusChip, TeamDot } from "./ui.js";

const sideOf = (tl, code) => (code === tl.home.code ? "home" : "away");
const text = (ins, lang, tone) => ((ins.text.rendered[lang] || ins.text.rendered.en) || {})[tone];

export function reasonFor(data, ruleIds, lang) {
  const r = data.ui.reasons[lang] || data.ui.reasons.en;
  return (ruleIds || []).map((id) => r[id]).filter(Boolean)[0] || null;
}

function EvidenceInline({ data, ins, lang, t }) {
  const rows = ins.evidence_event_ids.map((id) => data.ui.evidence[id]).filter(Boolean).slice(0, 4);
  if (!rows.length) return null;
  return html`<ul class="mt-3 space-y-1 border-t border-line pt-3 text-[12px] text-ink-2" data-evidence-inline>
    ${rows.map((e) => html`<li key=${e.event_id} data-event-id=${e.event_id} class="flex min-w-0 gap-2">
      <span class="num w-14 shrink-0 text-ink-3">${e.match_id === data.timeline.match_id ? clock(e.clock_sec, data.timeline.periods) : e.match_id}</span>
      <span class="min-w-0 truncate"><b class="font-semibold text-ink">${e.player || e.team}</b> · ${e.event_type} · ${e.outcome}</span>
    </li>`)}
  </ul>`;
}

export const InsightCard = React.memo(function InsightCard({ data, ins, selected, onEvidence, fresh }) {
  const { t, typeLabel, lang } = useT();
  const evidenceOpen = useSettings((s) => s.evidenceOpen);
  const tl = data.timeline;
  const rw = data.ui.rewrites[ins.insight_id];
  const [view, setView] = React.useState("after");
  const hist = data.chain(ins.claim_id);
  const status = rw ? "revised" : ins.verification_status;
  const before = rw && view === "before";
  const headline = before ? (rw.original[lang] || rw.original.en).casual : text(ins, lang, "casual");
  const reason = rw ? reasonFor(data, rw.rule_ids, lang) : null;
  const conf = ins.payload.confidence;
  return html`<li data-insight-id=${ins.insight_id} data-type=${ins.insight_type} data-status=${status}
      aria-current=${selected ? "true" : undefined}
      class=${cx("card group rounded-2xl border bg-surface-2 card-pad transition-colors", fresh && "card-enter",
        selected ? "border-accent/60 ring-1 ring-accent/30" : "border-line hover:border-line-strong")}>
    <div class="flex flex-wrap items-center gap-2 text-[12px]">
      <time class="num font-bold text-ink">${clock(ins.clock.start_sec, tl.periods)}</time>
      <span class="inline-flex items-center gap-1.5 font-semibold text-ink-2"><${TeamDot} side=${sideOf(tl, ins.teams.primary)} />${ins.teams.primary}</span>
      <${Chip}>${typeLabel(ins.insight_type)}<//>
      <span class="ml-auto"><${StatusChip} status=${status} /></span>
    </div>
    <button type="button" onClick=${() => select(selected ? null : ins.insight_id)}
        aria-pressed=${String(Boolean(selected))}
        class="mt-2.5 block w-full rounded-lg text-left">
      <p data-role="headline" lang=${lang}
          class=${cx("text-[15.5px] font-semibold leading-snug", before ? "text-ink-2 line-through decoration-block/70" : "text-ink")}>
        ${headline}</p>
    </button>
    ${rw && html`<div class="mt-3 rounded-xl border border-revise/25 bg-revise-soft px-3 py-2.5" data-rewrite>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <span class="text-[12px] font-semibold text-revise">${before ? t("original") : t("allowed")}</span>
        <${Segmented} label=${t("rewritten")} name=${`rw-${ins.insight_id}`} value=${view} onChange=${setView}
          options=${[{ value: "before", label: t("before") }, { value: "after", label: t("after") }]} />
      </div>
      ${reason && html`<p class="mt-2 text-[12.5px] leading-snug text-ink-2"><b class="font-semibold text-ink">${t("why")}:</b> ${reason}</p>`}
    </div>`}
    <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[12px] text-ink-3">
      ${conf && html`<span>${t("confidence")}: <b class="font-semibold text-ink-2">${conf}</b></span>`}
      <span>${num(ins.evidence_event_ids.length, lang)} ${ins.evidence_event_ids.length === 1 ? t("event") : t("events")}</span>
      <span>${num(hist.length, lang)} ${t("attempt")}${hist.length > 1 ? "s" : ""}</span>
      <button type="button" data-evidence=${ins.insight_id} onClick=${() => onEvidence(ins.insight_id)}
          class="ml-auto inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 font-semibold text-ink-2 hover:border-accent/60 hover:text-ink">
        ${t("open_evidence")}<span aria-hidden="true">→</span></button>
    </div>
    ${evidenceOpen && html`<${EvidenceInline} data=${data} ins=${ins} lang=${lang} t=${t} />`}
  </li>`;
});

export function Feed({ data, onEvidence }) {
  const { t, lang } = useT();
  const n = useReplay((s) => data.visibleCount(s.t));
  const selected = useReplay((s) => s.selected);
  const seen = React.useRef(n);
  const fresh = n > seen.current ? new Set(data.insights.slice(seen.current, n).map((i) => i.insight_id)) : new Set();
  React.useEffect(() => { seen.current = n; }, [n]);
  const shown = data.insights.slice(0, n).reverse();
  return html`<${Panel} id="feed-panel" title=${t("stream")}
      actions=${html`<span id="feed-count" class="num whitespace-nowrap rounded-full bg-accent-soft px-2.5 py-0.5 text-[12px] font-bold text-accent">
        ${num(n, lang)} ${t("insights")}</span>`}
      className="flex min-h-0 flex-col">
    ${shown.length
      ? html`<ol id="feed" aria-live="polite" aria-relevant="additions" class="stack-gap flex flex-col">
          ${shown.map((ins) => html`<${InsightCard} key=${ins.insight_id} data=${data} ins=${ins}
              selected=${selected === ins.insight_id} fresh=${fresh.has(ins.insight_id)} onEvidence=${onEvidence} />`)}
        </ol>`
      : html`<p id="feed" class="rounded-xl border border-dashed border-line px-4 py-8 text-center text-[13px] text-ink-3">${t("none_yet")}</p>`}
  <//>`;
}

// ---------- evidence drawer ----------

function Kv({ k, v }) {
  return html`<div class="flex justify-between gap-4 border-b border-line py-1.5 text-[13px]">
    <dt class="text-ink-3">${k}</dt><dd class="num m-0 text-right font-semibold text-ink">${v}</dd></div>`;
}

export function EvidenceDrawer({ data, id, onClose }) {
  const { t, typeLabel, lang } = useT();
  const ref = React.useRef(null);
  const ins = id ? data.byId[id] : null;
  React.useEffect(() => {
    if (!ins) return undefined;
    const prev = document.activeElement;
    ref.current && ref.current.querySelector("[data-close]").focus();
    const key = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && ref.current) {
        const f = ref.current.querySelectorAll("button, [href], input, select, [tabindex]:not([tabindex='-1'])");
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); prev && prev.focus && prev.focus(); };
  }, [id]);
  if (!ins) return null;
  const tl = data.timeline;
  const hist = data.chain(ins.claim_id);
  const final = hist[hist.length - 1].claim;
  const v = final.value;
  const rows = ins.evidence_event_ids.map((eid) => data.ui.evidence[eid]).filter(Boolean);
  const reasons = data.ui.reasons[lang] || data.ui.reasons.en;
  const inMatch = (e) => e.match_id === tl.match_id;
  return html`<div class="fixed inset-0 z-50" role="presentation">
    <div class="absolute inset-0 bg-black/60" onClick=${onClose} aria-hidden="true"></div>
    <aside ref=${ref} id="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title" data-insight-id=${ins.insight_id}
        class="slide-over absolute inset-y-0 right-0 flex w-full max-w-[560px] flex-col border-l border-line bg-surface-1 shadow-2xl">
      <header class="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
        <div class="min-w-0">
          <p class="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-3">${t("evidence")} · ${typeLabel(ins.insight_type)} ·
            <span class="num">${clock(ins.clock.start_sec, tl.periods)}</span></p>
          <h2 id="drawer-title" class="mt-1 text-[17px] font-semibold leading-snug">${text(ins, lang, "casual")}</h2>
        </div>
        <button type="button" data-close onClick=${onClose} aria-label=${t("close")}
            class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-ink-2 hover:text-ink">✕</button>
      </header>
      <div class="flex-1 space-y-5 overflow-y-auto px-5 py-4">
        <p class="text-[14px] leading-relaxed text-ink-2" lang=${lang}>${text(ins, lang, "analyst")}</p>
        <dl class="m-0">
          <${Kv} k=${t("metric")} v=${html`<code class="text-[12px]">${final.metric}</code>`} />
          <${Kv} k=${t("value")} v=${`${num(v.amount, lang)} ${v.unit}`} />
          <${Kv} k=${t("scope")} v=${final.window ? `${final.scope} · ${clock(final.window.from_sec, tl.periods)}–${clock(final.window.to_sec, tl.periods)}` : final.scope} />
          ${v.baseline != null && html`<${Kv} k=${t("baseline")} v=${`${num(v.baseline, lang)}${v.baseline_source ? ` (${v.baseline_source.kind}, n=${v.baseline_source.n})` : ""}`} />`}
          ${v.confidence && html`<${Kv} k=${t("confidence")} v=${v.confidence} />`}
          ${Object.entries(final.supporting_values || {}).map(([k, x]) => html`<${Kv} key=${k} k=${k} v=${num(x, lang)} />`)}
        </dl>
        <section aria-labelledby="attempts-h">
          <h3 id="attempts-h" class="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-3">${t("attempts")}</h3>
          <ol class="mt-2 space-y-2">
            ${hist.map((a) => {
              const ver = a.claim.verification;
              const rs = ver.rule_ids || [];
              return html`<li key=${a.claim.claim_id} class="rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-[13px]">
                <div class="flex flex-wrap items-center gap-2"><b class="font-semibold">${t("attempt")} ${ver.attempt}</b>
                  <${StatusChip} status=${ver.status === "blocked" ? "blocked" : ver.status} label=${ver.status === "blocked" ? t("blocked") : undefined} />
                  <code class="text-[11.5px] text-ink-3">${a.claim.template_key}</code></div>
                ${rs.length > 0 && html`<p class="mt-1.5 text-[12.5px] text-ink-2">${t("rules")}: ${rs.map((r) => html`<code key=${r} class="mr-1 text-[11.5px]">${r}</code>`)}</p>`}
                ${ver.status === "blocked" && rs.length > 0 && reasons[rs[0]] && html`<p class="mt-1 text-[12.5px] text-ink-2">${reasons[rs[0]]}</p>`}
              </li>`;
            })}
          </ol>
        </section>
        <section aria-labelledby="events-h">
          <h3 id="events-h" class="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-3">${t("evidence_events")} · ${num(rows.length, lang)}</h3>
          <div class="mt-2 overflow-x-auto rounded-xl border border-line">
            <table class="w-full min-w-[460px] border-collapse text-[12.5px]">
              <thead class="bg-surface-2 text-left text-ink-3">
                <tr><th class="px-3 py-2 font-semibold">${t("time")}</th><th class="px-3 py-2 font-semibold">${t("player")}</th>
                  <th class="px-3 py-2 font-semibold">${t("type")}</th><th class="px-3 py-2 font-semibold">${t("outcome")}</th>
                  <th class="px-3 py-2 font-semibold">ID</th></tr>
              </thead>
              <tbody>
                ${rows.map((e) => html`<tr key=${e.event_id} data-event-id=${e.event_id} class="border-t border-line">
                  <td class="num whitespace-nowrap px-3 py-1.5">${inMatch(e) ? clock(e.clock_sec, tl.periods) : e.match_id}</td>
                  <td class="px-3 py-1.5">${e.player || e.team}${e.related_player ? html` <span class="text-ink-3">→ ${e.related_player}</span>` : ""}</td>
                  <td class="px-3 py-1.5">${e.event_type}</td><td class="px-3 py-1.5">${e.outcome}</td>
                  <td class="px-3 py-1.5"><code class="text-[11px] text-ink-3">${e.event_id}</code></td>
                </tr>`)}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </aside>
  </div>`;
}
