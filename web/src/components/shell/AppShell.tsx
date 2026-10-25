// App chrome: brand, navigation (a floating top bar from NAV_BREAKPOINT up, a bottom tab bar below
// it), search (button or Ctrl/Cmd+K) and settings, both as icon buttons in the bar.
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { cx } from "../../lib/cx";
import { useT, type Key } from "../../lib/i18n";
import { Icon, type IconName } from "../../icons";
import { Logo } from "../icons";
import { SettingsSheet } from "./SettingsSheet";

// its own chunk, loaded the first time search opens
const SearchOverlay = lazy(() => import("./SearchOverlay").then((m) => ({ default: m.SearchOverlay })));

/** The primary nav. The Tech page is reached from Settings ("Technical details") and from Home. */
export const ROUTES = ["home", "fixtures", "teams", "players"] as const;
export type Route = (typeof ROUTES)[number];
const ICON: Record<Route, IconName> = { home: "home", fixtures: "fixtures", teams: "teams", players: "players" };
/** A nav entry is also active on its sub-routes (a match hub belongs to Fixtures). */
const ACTIVE_ON: Record<Route, RegExp> = {
  home: /^\/?$/,
  fixtures: /^\/(fixtures|match)(\/|$)/,
  teams: /^\/teams(\/|$)/,
  players: /^\/players(\/|$)/,
};
const PATH: Record<Route, string> = { home: "/", fixtures: "/fixtures", teams: "/teams", players: "/players" };

/** At this width and up the nav is the floating top bar; below it, the bottom tab bar. */
export const NAV_BREAKPOINT = 720;

// 200 ms colour changes (none under reduced motion: index.css), and the 2 px accent focus ring
const ITEM = "transition-colors duration-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

function NavLinks({ compact }: { compact?: boolean }) {
  const { t } = useT();
  const { pathname } = useLocation();
  return ROUTES.map((r) => {
    const isActive = ACTIVE_ON[r].test(pathname);
    return (
      // Link, not NavLink: NavLink drops aria-current on the sub-routes ACTIVE_ON adds
      <Link
        key={r}
        to={PATH[r]}
        data-route={r}
        data-nav-item={r}
        aria-current={isActive ? "page" : undefined}
        className={cx(
          ITEM,
          compact
            ? "relative flex min-h-[52px] min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-xl text-[11px] font-medium"
            : "inline-flex h-10 items-center gap-2 rounded-full px-3 text-[13.5px] font-medium min-[860px]:px-3.5",
          // active: mint on a soft mint fill, plus an outline (compact: a bar on top) so the marker
          // does not rely on colour alone
          isActive
            ? compact
              ? "bg-accent-soft text-accent before:absolute before:inset-x-5 before:top-0 before:h-0.5 before:rounded-full before:bg-accent"
              : "bg-accent-soft text-accent shadow-[inset_0_0_0_1px_var(--accent-line)]"
            : "text-nav-ink hover:bg-white/[0.06] hover:text-ink",
        )}
      >
        <Icon name={ICON[r]} size={compact ? 22 : 18} />
        <span className="truncate">{t(`nav_${r}` as Key)}</span>
      </Link>
    );
  });
}

/** Search and Settings: icon buttons in an outlined circle, named for screen readers. */
function RoundButton({
  id,
  icon,
  label,
  onClick,
  shortcut,
}: {
  id: string;
  icon: IconName;
  label: string;
  onClick: () => void;
  shortcut?: string;
}) {
  return (
    <button
      id={id}
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-haspopup="dialog"
      aria-keyshortcuts={shortcut}
      className={cx(
        ITEM,
        "inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-nav-line min-[720px]:h-10 min-[720px]:w-10 text-nav-ink hover:bg-white/[0.06] hover:text-ink",
      )}
    >
      <Icon name={icon} size={18} />
    </button>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  // Ctrl/Cmd+K opens search from anywhere
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearched(true);
        setSearching(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div className="min-h-screen pb-24 min-[720px]:pb-0">
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
      {/* the floating bar: the strip around the pill is transparent, so the page shows through */}
      <header className="pointer-events-none sticky top-0 z-40 px-4 pt-3 sm:px-6 min-[720px]:pt-5">
        <div
          data-nav-bar
          className="pointer-events-auto mx-auto flex h-14 max-w-[1200px] items-center gap-3 rounded-[24px] border border-nav-line bg-nav px-3 pl-4 backdrop-blur-md elev-nav min-[720px]:grid min-[720px]:h-16 min-[720px]:grid-cols-[1fr_auto_1fr] min-[720px]:gap-4 min-[720px]:pl-5"
        >
          <div className="flex min-w-0 items-center gap-4">
            <Link to="/" data-route="home" className={cx(ITEM, "flex shrink-0 items-center rounded-lg")}>
              <Logo variant="wordmark" className="h-8 w-auto text-accent" />
              <span className="sr-only">Optix, {t("nav_home")}</span>
            </Link>
            <span aria-hidden="true" className="hidden h-6 w-px bg-nav-line min-[720px]:block" />
          </div>
          <nav aria-label="Main" className="hidden items-center gap-1.5 min-[720px]:flex min-[1000px]:gap-2">
            <NavLinks />
          </nav>
          <div className="ml-auto flex items-center justify-end gap-2">
            <RoundButton
              id="open-search"
              icon="search"
              label={t("search")}
              shortcut="Control+K Meta+K"
              onClick={() => {
                setSearched(true);
                setSearching(true);
              }}
            />
            <RoundButton id="open-settings" icon="settings" label={t("settings")} onClick={() => setOpen(true)} />
          </div>
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className="mx-auto max-w-[1680px] px-4 py-5 outline-none sm:px-6 sm:py-6 min-[720px]:pt-4"
      >
        {children}
      </main>
      <nav
        aria-label="Main"
        data-tab-bar
        className="fixed inset-x-0 bottom-0 z-40 flex gap-1 border-t border-nav-line bg-nav px-2 pb-[max(env(safe-area-inset-bottom),8px)] pt-1.5 backdrop-blur-md min-[720px]:hidden"
      >
        <NavLinks compact />
      </nav>
      <SettingsSheet open={open} onOpenChange={setOpen} />
      {searched && (
        <Suspense fallback={null}>
          <SearchOverlay open={searching} onOpenChange={setSearching} />
        </Suspense>
      )}
    </div>
  );
}
