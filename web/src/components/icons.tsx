// Interface glyphs that are not on the Optix icon sheet (close, arrow, swap, the ball marker, cloud,
// star). Search is in the icon set (<Icon name="search">).
// The sheet's 54 icons live in src/icons (<Icon>); these follow the same rules: 24 x 24, stroke 1.75,
// round caps and joins, currentColor, decorative (aria-hidden; the control carries the label).
import { cx } from "../lib/cx";
import { MARK, WORDMARK } from "./brand/logoPaths";

const PATHS = {
  close: "M6 6l12 12M18 6 6 18",
  arrow: "M5 12h14M13 6l6 6-6 6",
  swap: "M7 7h12l-3-3M17 17H5l3 3",
  ball: "M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Zm0 5 3.8 2.8-1.5 4.5H9.7l-1.5-4.5L12 8Z",
  cloud: "M7 18h10.5a4 4 0 0 0 .6-8 6 6 0 0 0-11.5 1.5A3.3 3.3 0 0 0 7 18Z",
  star: "M12 3.5l2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.5Z",
} as const;

export type GlyphName = keyof typeof PATHS;

export function Glyph({ name, className, filled }: { name: GlyphName; className?: string; filled?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      className={cx("shrink-0", className ?? "h-5 w-5")}
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

/** The traced Optix logo (tools/make_brand_assets.py), drawn inline so it takes currentColor. */
export function Logo({ variant = "mark", className }: { variant?: "mark" | "wordmark"; className?: string }) {
  const logo = variant === "mark" ? MARK : WORDMARK;
  return (
    <svg viewBox={logo.viewBox} aria-hidden="true" fill="currentColor" className={cx("shrink-0", className)}>
      {logo.paths.map((p, i) => (
        <path key={i} d={p.d} transform={`translate(${p.t})`} />
      ))}
    </svg>
  );
}
