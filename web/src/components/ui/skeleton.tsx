import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("skeleton", className)} />;
}

export function Empty({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      data-state="empty"
      className={cx(
        "rounded-xl border border-dashed border-line-strong/70 px-4 py-6 text-center text-[13px] leading-relaxed text-ink-3",
        className,
      )}
    >
      {children}
    </div>
  );
}
