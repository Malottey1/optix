// App chrome: brand, navigation (top on large screens, bottom bar on small ones), settings tray.
import { html, React } from "../lib/html.js";
import { cx } from "../lib/format.js";
import { useT } from "../lib/i18n.js";
import { LANGS, setSetting, useSettings } from "../lib/settings.js";
import { ROUTES } from "../lib/router.js";
import { Segmented } from "./ui.js";

const ICONS = {
  live: html`<svg viewBox="0 0 24 24" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7"/></svg>`,
  teams: html`<svg viewBox="0 0 24 24" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16M3 12h4M17 12h4"/></svg>`,
  players: html`<svg viewBox="0 0 24 24" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c1.2-3.6 3.9-5.5 7-5.5s5.8 1.9 7 5.5"/></svg>`,
  tech: html`<svg viewBox="0 0 24 24" class="h-5 w-5" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 7h7M4 17h4M14 7h6M12 17h8"/><circle cx="12.5" cy="7" r="1.8"/><circle cx="10" cy="17" r="1.8"/></svg>`,
};

function Brand() {
  const { t } = useT();
  return html`<a href="#/live" class="flex min-w-0 items-center gap-2.5 rounded-lg">
    <svg viewBox="0 0 32 32" class="h-8 w-8 shrink-0" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--surface-3)" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="var(--accent)" strokeWidth="2.6" />
      <circle cx="16" cy="16" r="3" fill="var(--ink)" />
    </svg>
    <span class="min-w-0">
      <span class="block text-[17px] font-bold leading-none tracking-tight">Optix</span>
      <span class="mt-1 hidden truncate text-[11.5px] text-ink-3 sm:block">${t("brand_sub")}</span>
    </span>
  </a>`;
}

function NavLinks({ route, compact }) {
  const { t } = useT();
  return ROUTES.map((r) => html`<a key=${r} href=${`#/${r}`} data-route=${r} aria-current=${route === r ? "page" : undefined}
      class=${cx(compact
        ? "flex flex-1 flex-col items-center gap-0.5 rounded-lg py-1.5 text-[11px] font-semibold"
        : "inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-[13.5px] font-semibold",
        route === r ? (compact ? "text-accent" : "bg-surface-3 text-ink") : "text-ink-3 hover:text-ink")}>
    ${ICONS[r]}<span>${compact ? t(`nav_${r}`) : t(`nav_${r}_long`)}</span>
  </a>`);
}

function Toggle({ id, label, checked, onChange }) {
  return html`<label for=${id} class="flex cursor-pointer items-center justify-between gap-4 py-2.5">
    <span class="text-[14px] text-ink">${label}</span>
    <span class="relative inline-flex">
      <input id=${id} type="checkbox" role="switch" class="peer sr-only" checked=${checked} onChange=${(e) => onChange(e.target.checked)} />
      <span aria-hidden="true" class="h-6 w-11 rounded-full border border-line-strong bg-surface-3 transition-colors peer-checked:border-accent peer-checked:bg-accent/80 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent"></span>
      <span aria-hidden="true" class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-ink transition-transform peer-checked:translate-x-5"></span>
    </span>
  </label>`;
}

const LANG_NAMES = { en: "English", es: "Español", fr: "Français" };

function SettingsTray({ open, onClose }) {
  const { t } = useT();
  const s = useSettings((x) => x);
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!open) return undefined;
    const prev = document.activeElement;
    ref.current && ref.current.querySelector("[data-close]").focus();
    const key = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); prev && prev.focus && prev.focus(); };
  }, [open]);
  if (!open) return null;
  return html`<div class="fixed inset-0 z-50">
    <div class="absolute inset-0 bg-black/60" onClick=${onClose} aria-hidden="true"></div>
    <aside ref=${ref} id="settings" role="dialog" aria-modal="true" aria-labelledby="settings-title"
        class="slide-over absolute inset-y-0 right-0 flex w-full max-w-[380px] flex-col border-l border-line bg-surface-1 shadow-2xl">
      <header class="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 id="settings-title" class="text-[16px] font-semibold">${t("settings")}</h2>
        <button type="button" data-close onClick=${onClose} aria-label=${t("close")}
            class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-2 hover:text-ink">✕</button>
      </header>
      <div class="flex-1 overflow-y-auto px-5 py-4">
        <fieldset class="border-0 p-0">
          <legend class="mb-2 text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-3">${t("language")}</legend>
          <div class="grid grid-cols-3 gap-2">
            ${LANGS.map((l) => html`<label key=${l} class=${cx("cursor-pointer rounded-xl border px-3 py-2 text-center text-[13px] font-semibold",
                s.lang === l ? "border-accent bg-accent-soft text-ink" : "border-line text-ink-2 hover:border-line-strong")}>
              <input type="radio" name="lang" value=${l} class="sr-only" checked=${s.lang === l} data-lang=${l}
                onChange=${() => setSetting("lang", l)} />${LANG_NAMES[l]}</label>`)}
          </div>
        </fieldset>
        <div class="mt-5 divide-y divide-line border-y border-line">
          <${Toggle} id="set-motion" label=${t("reduced_motion")} checked=${s.reducedMotion} onChange=${(v) => setSetting("reducedMotion", v)} />
          <${Toggle} id="set-evidence" label=${t("evidence_default")} checked=${s.evidenceOpen} onChange=${(v) => setSetting("evidenceOpen", v)} />
          <${Toggle} id="set-contrast" label=${t("high_contrast")} checked=${s.highContrast} onChange=${(v) => setSetting("highContrast", v)} />
          <div class="flex items-center justify-between gap-4 py-2.5">
            <span class="text-[14px] text-ink">${t("density")}</span>
            <${Segmented} label=${t("density")} name="density" value=${s.density} onChange=${(v) => setSetting("density", v)}
              options=${[{ value: "comfortable", label: t("comfortable") }, { value: "compact", label: t("compact") }]} />
          </div>
        </div>
        <p class="mt-4 text-[12.5px] leading-relaxed text-ink-3">${t("settings_note")}</p>
      </div>
    </aside>
  </div>`;
}

export function Shell({ route, children }) {
  const { t } = useT();
  const [open, setOpen] = React.useState(false);
  return html`<div class="min-h-screen pb-20 lg:pb-0">
    <a href="#main" class="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">${t("skip")}</a>
    <header class="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur-md">
      <div class="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6">
        <${Brand} />
        <nav aria-label="Main" class="ml-6 hidden items-center gap-1 lg:flex"><${NavLinks} route=${route} /></nav>
        <button id="open-settings" type="button" onClick=${() => setOpen(true)} aria-haspopup="dialog"
            class="ml-auto inline-flex h-10 items-center gap-2 rounded-full border border-line px-3.5 text-[13.5px] font-semibold text-ink-2 hover:border-line-strong hover:text-ink">
          <svg viewBox="0 0 24 24" class="h-[18px] w-[18px]" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>
          <span class="hidden sm:inline">${t("settings")}</span><span class="sr-only sm:hidden">${t("settings")}</span>
        </button>
      </div>
    </header>
    <main id="main" tabindex="-1" class="mx-auto max-w-[1440px] px-4 py-5 outline-none sm:px-6 sm:py-6">${children}</main>
    <nav aria-label="Main" class="fixed inset-x-0 bottom-0 z-40 flex gap-1 border-t border-line bg-bg/95 px-2 pb-[max(env(safe-area-inset-bottom),6px)] pt-1.5 backdrop-blur-md lg:hidden">
      <${NavLinks} route=${route} compact=${true} />
    </nav>
    <${SettingsTray} open=${open} onClose=${() => setOpen(false)} />
  </div>`;
}
