// App chrome: brand, navigation (top bar on large screens, bottom bar on small ones), settings.
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router";
import { cx } from "../../lib/cx";
import { useT, type Key } from "../../lib/i18n";
import { Icon, Logo, type IconName } from "../icons";
import { SettingsSheet } from "./SettingsSheet";

export const ROUTES = ["live", "teams", "players", "tech"] as const;
export type Route = (typeof ROUTES)[number];
const ICON: Record<Route, IconName> = { live: "live", teams: "teams", players: "players", tech: "tech" };

function NavLinks({ compact }: { compact?: boolean }) {
  const { t } = useT();
  return ROUTES.map((r) => (
    <NavLink
      key={r}
      to={`/${r}`}
      data-route={r}
      className={({ isActive }) =>
        cx(
          compact
            ? "flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-xl py-1.5 text-[11px] font-semibold"
            : "inline-flex items-center gap-2 rounded-full px-3.5 py-2 text-[13.5px] font-semibold transition-colors",
          isActive
            ? compact
              ? "text-accent"
              : "bg-surface-3 text-ink shadow-[inset_0_0_0_1px_var(--line-strong)]"
            : "text-ink-3 hover:text-ink",
        )
      }
    >
      <Icon name={ICON[r]} className={compact ? "h-[22px] w-[22px]" : "h-[18px] w-[18px]"} />
      <span className="truncate">{t(`nav_${r}${compact ? "" : "_long"}` as Key)}</span>
    </NavLink>
  ));
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen pb-24 lg:pb-0">
      <a
        href="#main"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main")?.focus();
        }}
        className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink"
      >
        {t("skip")}
      </a>
      <header className="sticky top-0 z-40 border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1680px] items-center gap-4 px-4 sm:px-6">
          <NavLink to="/live" className="flex min-w-0 items-center gap-2.5 rounded-lg">
            <Logo />
            <span className="min-w-0">
              <span className="block text-[17px] font-bold leading-none tracking-tight text-ink">Optix</span>
              <span className="mt-1 hidden truncate text-[11.5px] text-ink-3 sm:block">{t("brand_sub")}</span>
            </span>
          </NavLink>
          <nav aria-label="Main" className="ml-6 hidden items-center gap-1 lg:flex">
            <NavLinks />
          </nav>
          <button
            id="open-settings"
            type="button"
            onClick={() => setOpen(true)}
            aria-haspopup="dialog"
            className="ml-auto inline-flex h-10 items-center gap-2 rounded-full border border-line px-3.5 text-[13.5px] font-semibold text-ink-2 hover:border-line-strong hover:text-ink"
          >
            <Icon name="settings" className="h-[18px] w-[18px]" />
            <span className="hidden sm:inline">{t("settings")}</span>
            <span className="sr-only sm:hidden">{t("settings")}</span>
          </button>
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-[1680px] px-4 py-5 outline-none sm:px-6 sm:py-6">
        {children}
      </main>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-40 flex gap-1 border-t border-line bg-bg/95 px-2 pb-[max(env(safe-area-inset-bottom),8px)] pt-1.5 backdrop-blur-md lg:hidden"
      >
        <NavLinks compact />
      </nav>
      <SettingsSheet open={open} onOpenChange={setOpen} />
    </div>
  );
}
