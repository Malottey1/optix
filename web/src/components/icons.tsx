// Inline SVG icons (no icon font, no emoji). Decorative: aria-hidden; the control carries the label.
import { cx } from "../lib/cx";

const PATHS = {
  live: "M12 9.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6ZM5.6 5.6a9 9 0 0 0 0 12.8M18.4 5.6a9 9 0 0 1 0 12.8M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7",
  teams: "M4 5h16v14H4zM12 5v14M4 9.5h3v5H4M20 9.5h-3v5h3",
  players: "M12 4.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7ZM5 20c1.2-3.6 3.9-5.5 7-5.5s5.8 1.9 7 5.5",
  tech: "M4 7h7M4 17h4M14 7h6M12 17h8M12.5 5.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6ZM10 15.2a1.8 1.8 0 1 1 0 3.6 1.8 1.8 0 0 1 0-3.6Z",
  settings:
    "M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6ZM19.4 13.5l1.6 1.2-1.8 3.1-1.9-.7a7 7 0 0 1-2 1.2l-.3 2h-3.6l-.3-2a7 7 0 0 1-2-1.2l-1.9.7L3.4 14.7 5 13.5a7 7 0 0 1 0-3L3.4 9.3l1.8-3.1 1.9.7a7 7 0 0 1 2-1.2l.3-2h3.6l.3 2a7 7 0 0 1 2 1.2l1.9-.7 1.8 3.1-1.6 1.2a7 7 0 0 1 0 3Z",
  play: "M8 5.5v13l10.5-6.5L8 5.5Z",
  pause: "M8 5h3v14H8zM13 5h3v14h-3z",
  restart: "M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5",
  close: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5l4.2 4.2L19 7",
  info: "M12 8h.01M11 12h1v5h1M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z",
  rewrite: "M4 12a8 8 0 0 1 13.7-5.6L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.6L4 15.5M4 20v-4.5h4.5",
  block: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18ZM5.6 5.6l12.8 12.8",
  arrow: "M5 12h14M13 6l6 6-6 6",
  swap: "M7 7h12l-3-3M17 17H5l3 3",
  evidence: "M9 4h6l4 4v12H5V4h4ZM14 4v5h5M8.5 13h7M8.5 16.5h5",
  ball: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Zm0 5 3.8 2.8-1.5 4.5H9.7l-1.5-4.5L12 8Z",
  layers: "M12 4 3 9l9 5 9-5-9-5ZM3 14l9 5 9-5",
  shield: "M12 3l7.5 3v5.5c0 4.6-3.2 8.3-7.5 9.5-4.3-1.2-7.5-4.9-7.5-9.5V6L12 3Zm-3.5 9 2.5 2.5 4.5-5",
  chart: "M4 19h16M7 16v-5M11.5 16V8M16 16v-3",
  flag: "M6 21V4M6 4h11l-2 4 2 4H6",
  cloud: "M7 18h10.5a4 4 0 0 0 .6-8 6 6 0 0 0-11.5 1.5A3.3 3.3 0 0 0 7 18Z",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({
  name,
  className,
  strokeWidth = 1.8,
}: {
  name: IconName;
  className?: string;
  strokeWidth?: number;
}) {
  const filled = name === "play" || name === "pause";
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={cx("shrink-0", className ?? "h-5 w-5")}
      fill={filled ? "currentColor" : "none"}
      stroke={filled ? "none" : "currentColor"}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className={cx("shrink-0", className ?? "h-8 w-8")}>
      <rect width="32" height="32" rx="9" fill="var(--surface-3)" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="var(--accent)" strokeWidth="2.6" />
      <path d="M16 7.5v5M16 19.5v5M7.5 16h5M19.5 16h5" stroke="var(--accent)" strokeWidth="1.6" opacity="0.55" />
      <circle cx="16" cy="16" r="2.8" fill="var(--ink)" />
    </svg>
  );
}
