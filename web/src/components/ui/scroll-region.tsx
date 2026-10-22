import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

/** A scrollable box a keyboard can reach and scroll (axe: scrollable-region-focusable). */
export function ScrollRegion({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className={cx("overflow-auto rounded-xl border border-line focus-visible:outline-2", className)}
    >
      {children}
    </div>
  );
}
