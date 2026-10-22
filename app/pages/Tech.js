// #/tech: how the pipeline works, the verification ledger of the showcase stream, the measured
// numbers (parsed from the generated reports in docs/, not retyped) and what is not built yet.
import { html, React } from "../lib/html.js";
import { cell, clock, cx, num } from "../lib/format.js";
import { useT } from "../lib/i18n.js";
import { Chip, Panel, StatusChip } from "../components/ui.js";

const OUTCOME = {
  passed: { status: "published", label: "Passed" },
  passed_with_context: { status: "published_with_context", label: "Passed with context" },
  revised: { status: "revised", label: "Revised" },
  blocked: { status: "blocked", label: "Blocked" },
};

function Node({ x, y, w, title, sub, tone = "line" }) {
  const stroke = { line: "var(--line-strong)", accent: "var(--accent)", revise: "var(--revise)" }[tone];
  return html`<g>
    <rect x=${x} y=${y} width=${w} height="66" rx="12" fill="var(--surface-2)" stroke=${stroke} strokeWidth="1.5" />
    <text x=${x + 14} y=${y + 27} fill="var(--ink)" fontSize="15" fontWeight="700">${title}</text>
    <text x=${x + 14} y=${y + 48} fill="var(--ink-3)" fontSize="11.5">${sub}</text>
  </g>`;
}

function Pipeline({ ledger, langs }) {
  const { lang } = useT();
  const arrow = (x1, x2, y) => html`<path d=${`M${x1},${y} L${x2 - 8},${y}`} stroke="var(--ink-3)" strokeWidth="1.5" markerEnd="url(#tech-arrow)" />`;
  return html`<${Panel} id="pipeline" title="Pipeline"
      subtitle="Math first, language second: the engine computes every number; the Verifier checks the language-free claim object; only then is it written in each language, and a guard re-checks every number in every sentence.">
    <div class="overflow-x-auto">
      <svg viewBox="0 0 1060 210" class="block h-auto w-full min-w-[760px]" role="img" data-chart="pipeline"
          aria-label="Events to Analyst to Verifier to Narrative and number guard to the insight stream; blocked claims go back to the Analyst for revision">
        <defs><marker id="tech-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--ink-3)" /></marker></defs>
        <${Node} x=${10} y=${30} w=${150} title="Event stream" sub="synthetic events" />
        <${Node} x=${200} y=${30} w=${180} title="Analyst" sub="claim objects from engine/" />
        <${Node} x=${420} y=${30} w=${200} title="Verifier" sub="fact check + context check" tone="accent" />
        <${Node} x=${660} y=${30} w=${200} title="Narrative" sub="templates, number guard" />
        <${Node} x=${900} y=${30} w=${150} title="Insight stream" sub="timed, with evidence" tone="accent" />
        ${arrow(160, 200, 63)}${arrow(380, 420, 63)}${arrow(620, 660, 63)}${arrow(860, 900, 63)}
        <path d="M520,96 C520,170 290,170 290,104" fill="none" stroke="var(--revise)" strokeWidth="1.5" strokeDasharray="5 4" markerEnd="url(#tech-arrow)" />
        <text x="405" y="182" fill="var(--revise)" fontSize="12.5" textAnchor="middle" fontWeight="600">blocked → revised claim, re-verified</text>
      </svg>
    </div>
    <dl class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      ${[["Claim attempts", ledger.attempts], ["Blocked, then revised", ledger.blocked_attempts], ["Insights published", ledger.total - ledger.counts.blocked],
        ["Languages, number-guarded", langs]].map(([k, v]) => html`<div key=${k} class="rounded-xl border border-line bg-surface-2 px-4 py-3">
          <dd class="num m-0 text-[28px] font-bold leading-none">${num(v, lang)}</dd><dt class="mt-1.5 text-[12.5px] text-ink-3">${k}</dt></div>`)}
    </dl>
  <//>`;
}

function Ledger({ data }) {
  const { lang, typeLabel } = useT();
  const L = data.ui.ledger;
  const periods = data.timeline.periods;
  return html`<${Panel} id="ledger" title="Verification ledger"
      subtitle="Every claim in the showcase stream and what the Verifier decided. A revised claim was blocked on its first attempt by the rule shown, rewritten with the context it asked for, and passed on the next attempt.">
    <div class="flex flex-wrap gap-2">
      ${Object.entries(OUTCOME).map(([k, o]) => html`<span key=${k} class="inline-flex items-center gap-2" data-outcome-count=${k}>
        <${StatusChip} status=${o.status} label=${o.label} /><b class="num text-[15px]">${num(L.counts[k], lang)}</b></span>`)}
    </div>
    <div class="mt-4 max-h-[460px] overflow-auto rounded-xl border border-line">
      <table class="w-full min-w-[720px] border-collapse text-[12.5px]" data-table="ledger">
        <thead class="sticky top-0 bg-surface-2 text-left text-ink-3"><tr>
          <th class="px-3 py-2 font-semibold">Time</th><th class="px-3 py-2 font-semibold">Insight</th><th class="px-3 py-2 font-semibold">Team</th>
          <th class="px-3 py-2 font-semibold">Metric</th><th class="px-3 py-2 font-semibold">Outcome</th>
          <th class="px-3 py-2 font-semibold">Deciding rule</th><th class="px-3 py-2 font-semibold">Templates</th></tr></thead>
        <tbody>${L.rows.map((r) => html`<tr key=${r.claim_id} data-claim-id=${r.claim_id} data-outcome=${r.outcome} class="border-t border-line">
          <td class="num whitespace-nowrap px-3 py-1.5">${clock(r.clock_sec, periods)}</td>
          <td class="px-3 py-1.5">${r.insight_type ? typeLabel(r.insight_type) : "—"}</td><td class="px-3 py-1.5">${r.team}</td>
          <td class="px-3 py-1.5"><code class="text-[11.5px]">${r.metric}</code></td>
          <td class="px-3 py-1.5"><${StatusChip} status=${OUTCOME[r.outcome].status} label=${OUTCOME[r.outcome].label} /></td>
          <td class="px-3 py-1.5">${r.rule_ids.length ? r.rule_ids.map((x) => html`<code key=${x} class="mr-1 text-[11.5px] text-revise">${x}</code>`) : html`<span class="text-ink-3">none fired</span>`}</td>
          <td class="px-3 py-1.5 text-ink-3"><code class="text-[11px]">${r.template_keys.join(" → ")}</code></td></tr>`)}</tbody>
      </table>
    </div>
  <//>`;
}

function ReportTable({ t, lang, open }) {
  return html`<details open=${open} class="rounded-xl border border-line bg-surface-2">
    <summary class="cursor-pointer px-4 py-2.5 text-[13px] font-semibold text-ink-2 hover:text-ink">${cell(t.heading, lang)}
      <span class="num ml-2 font-normal text-ink-3">(${num(t.rows.length, lang)} rows)</span></summary>
    <div class="max-h-[420px] overflow-auto border-t border-line">
      <table class="w-full border-collapse text-[12px]" data-table="report">
        <thead class="sticky top-0 bg-surface-3 text-left text-ink-3"><tr>${t.headers.map((h, i) => html`<th key=${i} class="whitespace-nowrap px-3 py-1.5 font-semibold">${h}</th>`)}</tr></thead>
        <tbody>${t.rows.map((r, i) => html`<tr key=${i} class="border-t border-line">${r.map((c, j) => html`<td key=${j}
            class=${cx("num px-3 py-1 align-top", j === 0 ? "font-semibold" : "whitespace-nowrap", /\bok\b/.test(c) && "text-pass")}>${cell(c, lang)}</td>`)}</tr>`)}</tbody>
      </table>
    </div>
  </details>`;
}

function Measured({ reports }) {
  const { lang } = useT();
  return html`<${Panel} id="measured" title="Measured numbers"
      subtitle="Read from the generated reports in docs/ (realism targets, multi-seed robustness, Verifier recall with the hold-out and Wilson intervals). Nothing here is retyped.">
    <div class="stack-gap flex flex-col">
      ${reports.map((r, k) => html`<section key=${r.file} data-report=${r.file} class="min-w-0">
        <h3 class="text-[16px] font-bold">${r.title} <code class="ml-1 text-[11.5px] font-normal text-ink-3">${r.file}</code></h3>
        <p class="mt-1 text-[13px] leading-relaxed text-ink-2">${cell(r.intro, lang)}</p>
        ${r.notes.filter((n) => /Reading/.test(n.heading)).length > 0 && html`<ul class="mt-3 space-y-2">
          ${r.notes.filter((n) => /Reading/.test(n.heading)).map((n, i) => html`<li key=${i}
              class="rounded-xl border border-accent/25 bg-accent-soft px-3.5 py-2.5 text-[13px] leading-relaxed text-ink">${cell(n.text, lang)}</li>`)}
        </ul>`}
        <div class="mt-3 space-y-2">${r.tables.map((t, i) => html`<${ReportTable} key=${i} t=${t} lang=${lang} open=${k === 0 && i === 0} />`)}</div>
      </section>`)}
    </div>
  <//>`;
}

const PLANNED = [
  ["Azure hosting", "The dashboard and engine run locally today (a static file server and Python). No Azure resource exists for this repo."],
  ["Event Hubs ingestion", "Events are read from CSV files and replayed in process; there is no live event feed."],
  ["Application Insights telemetry", "Agent logs are written to out/agent_log.jsonl only."],
  ["Microsoft Agent Framework", "The agents are plain Python classes in one process; no agent framework is wired in."],
  ["LLM phrasing", "Every sentence comes from fixed templates in agents/templates/. A language model would only reword verified facts behind the same number guard; it is not built."],
];

export function TechPage({ data }) {
  const ui = data.ui;
  return html`<div class="stack-gap flex flex-col" data-page="tech">
    <header>
      <h1 class="text-[26px] font-bold tracking-tight sm:text-[30px]">Tech Blueprint</h1>
      <p class="mt-1 max-w-3xl text-[14px] leading-relaxed text-ink-2">How a sentence earns its place on screen, what the
        Verifier decided for every claim in the showcase match, and how well the engine and the Verifier measure up.</p>
    </header>
    <${Pipeline} ledger=${ui.ledger} langs=${Object.keys(ui.reasons).length} />
    <${Ledger} data=${data} />
    <${Measured} reports=${ui.measured} />
    <${Panel} id="planned" title="Planned Azure integration (not built)"
        subtitle="Listed so nobody mistakes the plan for the product. None of this exists in the repo yet.">
      <ul class="grid grid-cols-1 gap-3 md:grid-cols-2">
        ${PLANNED.map(([k, v]) => html`<li key=${k} data-planned class="rounded-xl border border-dashed border-line-strong px-4 py-3">
          <div class="flex items-center gap-2"><${Chip}>Planned<//><b class="text-[14px]">${k}</b></div>
          <p class="mt-1.5 text-[13px] leading-relaxed text-ink-3">${v}</p></li>`)}
      </ul>
    <//>
  </div>`;
}
