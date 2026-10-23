import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

/** A titled surface. The title is an h2 unless `level` says otherwise. */
export function Panel({
  id,
  title,
  eyebrow,
  subtitle,
  actions,
  children,
  className,
  bodyClassName,
  subtitleClassName,
  level = 2,
}: {
  id?: string;
  title?: ReactNode;
  eyebrow?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  bodyClassName?: string;
  /** e.g. "wide:hidden" where a dense layout drops the subtitle (the caption still explains). */
  subtitleClassName?: string;
  level?: 2 | 3;
}) {
  const H = level === 2 ? "h2" : "h3";
  const hid = id ? `${id}-title` : undefined;
  return (
    <section
      id={id}
      aria-labelledby={title ? hid : undefined}
      className={cx("min-w-0 rounded-2xl border border-line bg-surface-1 elev-1", className)}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 px-[var(--pad)] pt-[var(--pad)]">
          <div className="min-w-0">
            {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
            {title && (
              <H id={hid} className="text-[15px] font-semibold tracking-tight text-ink">
                {title}
              </H>
            )}
            {subtitle && (
              <p className={cx("mt-1 max-w-prose text-[13px] leading-snug text-ink-3", subtitleClassName)}>
                {subtitle}
              </p>
            )}
          </div>
          {actions}
        </header>
      )}
      <div className={cx("pad", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Stat({
  value,
  label,
  className,
  tone = "ink",
}: {
  value: ReactNode;
  label: ReactNode;
  className?: string;
  tone?: "ink" | "accent" | "revise" | "muted";
}) {
  const color = { ink: "text-ink", accent: "text-accent", revise: "text-revise", muted: "text-ink-3" }[tone];
  return (
    <div className={cx("min-w-0 rounded-xl border border-line bg-surface-2 px-3.5 py-3", className)}>
      <dd className={cx("display m-0 text-[30px] font-bold leading-none", color)}>{value}</dd>
      <dt className="mt-1.5 text-[12px] leading-snug text-ink-3">{label}</dt>
    </div>
  );
}
