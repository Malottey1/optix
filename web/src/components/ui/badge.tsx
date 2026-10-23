import type { ReactNode } from "react";
import { cx } from "../../lib/cx";
import { Icon, type IconName } from "../../icons";

export function Chip({ children, className, title }: { children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex max-w-full items-center gap-1 rounded-full border border-line bg-surface-2 px-2 py-0.5 text-[11.5px] font-medium text-ink-2",
        className,
      )}
    >
      {children}
    </span>
  );
}

export type Status = "published" | "published_with_context" | "revised" | "blocked";

const STATUS: Record<Status, { cls: string; icon: IconName }> = {
  published: { cls: "bg-pass-soft text-pass border-pass/30", icon: "verdict-passed" },
  published_with_context: { cls: "bg-muted-soft text-muted border-muted/35", icon: "verdict-context" },
  revised: { cls: "bg-revise-soft text-revise border-revise/35", icon: "verdict-revised" },
  blocked: { cls: "bg-block-soft text-block border-block/35", icon: "verdict-blocked" },
};

export function StatusChip({ status, label, className }: { status: Status; label: ReactNode; className?: string }) {
  const s = STATUS[status];
  return (
    <span
      data-status={status}
      className={cx(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11.5px] font-semibold",
        s.cls,
        className,
      )}
    >
      <Icon name={s.icon} className="h-3.5 w-3.5" />
      {label}
    </span>
  );
}

export function TeamDot({ side, className }: { side: "home" | "away"; className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        "inline-block h-2.5 w-2.5 shrink-0 rounded-full",
        side === "home" ? "bg-home" : "bg-away",
        className,
      )}
    />
  );
}
