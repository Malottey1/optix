// Small shared pieces: panels, chips, status chips, tooltips, skeletons and empty states.
import { html } from "../lib/html.js";
import { cx } from "../lib/format.js";
import { useT } from "../lib/i18n.js";

export function Panel({ title, subtitle, actions, children, className = "", id, labelledby }) {
  const hid = id ? `${id}-title` : undefined;
  return html`<section id=${id} aria-labelledby=${labelledby || hid}
      class=${cx("rounded-2xl border border-line bg-surface-1 shadow-[0_1px_0_rgba(255,255,255,0.03)_inset,0_10px_30px_rgba(0,0,0,0.25)]", className)}>
    ${title && html`<header class="flex items-start justify-between gap-3 px-4 pt-4 sm:px-5">
      <div class="min-w-0">
        <h2 id=${hid} class="text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">${title}</h2>
        ${subtitle && html`<p class="mt-1 text-[12.5px] leading-snug text-ink-3">${subtitle}</p>`}
      </div>
      ${actions}
    </header>`}
    <div class="card-pad sm:px-5">${children}</div>
  </section>`;
}

const STATUS = {
  published: { cls: "bg-pass-soft text-pass border-pass/30", icon: "✓", key: "verified" },
  published_with_context: { cls: "bg-accent-soft text-accent border-accent/30", icon: "!", key: "with_context" },
  revised: { cls: "bg-revise-soft text-revise border-revise/30", icon: "↻", key: "rewritten" },
  blocked: { cls: "bg-block-soft text-block border-block/30", icon: "×", key: "blocked" },
};

export function StatusChip({ status, label }) {
  const { t } = useT();
  const s = STATUS[status] || STATUS.published;
  return html`<span data-status=${status}
      class=${cx("inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11.5px] font-semibold", s.cls)}>
    <span aria-hidden="true">${s.icon}</span>${label || t(s.key)}
  </span>`;
}

export function Chip({ children, className = "", title }) {
  return html`<span title=${title}
      class=${cx("inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[11.5px] font-medium text-ink-2", className)}>
    ${children}</span>`;
}

export function TeamDot({ side, className = "" }) {
  return html`<span aria-hidden="true" class=${cx("inline-block h-2.5 w-2.5 shrink-0 rounded-full", side === "home" ? "bg-home" : "bg-away", className)}></span>`;
}

/** A label with its rule in a tooltip (hover or keyboard focus); the rule is also the accessible description. */
export function RuleTip({ id, label, rule, className = "" }) {
  return html`<span class=${cx("tip inline-flex", className)}>
    <button type="button" aria-describedby=${id}
        class="inline-flex items-center gap-1 rounded-full border border-line bg-surface-2 px-2.5 py-1 text-[12px] font-semibold text-ink hover:border-line-strong">
      ${label}<span aria-hidden="true" class="text-ink-3">ⓘ</span>
    </button>
    <span role="tooltip" id=${id} class="tip-body">${rule}</span>
  </span>`;
}

export function Skeleton({ className = "" }) {
  return html`<div aria-hidden="true" class=${cx("skeleton", className)}></div>`;
}

export function Empty({ children }) {
  return html`<p class="rounded-xl border border-dashed border-line px-4 py-6 text-center text-[13px] text-ink-3">${children}</p>`;
}

export function NotAvailable() {
  const { t } = useT();
  return html`<${Empty}>${t("not_available")}<//>`;
}

export function Segmented({ label, value, options, onChange, name }) {
  return html`<div role="radiogroup" aria-label=${label} class="inline-flex rounded-full border border-line bg-surface-2 p-0.5">
    ${options.map((o) => html`<button key=${o.value} type="button" role="radio" aria-checked=${String(value === o.value)}
        data-name=${name} data-value=${o.value}
        onClick=${() => onChange(o.value)}
        class=${cx("rounded-full px-3 py-1 text-[12px] font-semibold transition-colors",
          value === o.value ? "bg-ink text-bg" : "text-ink-2 hover:text-ink")}>${o.label}</button>`)}
  </div>`;
}
