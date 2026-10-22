import * as T from "@radix-ui/react-tabs";
import type { ReactNode } from "react";
import { cx } from "../../lib/cx";

export const Tabs = T.Root;
export const TabsContent = T.Content;

export function TabsList({ label, children, className }: { label: string; children: ReactNode; className?: string }) {
  return (
    <T.List
      aria-label={label}
      className={cx(
        "flex max-w-full gap-1 overflow-x-auto rounded-full border border-line bg-surface-2 p-0.5",
        className,
      )}
    >
      {children}
    </T.List>
  );
}

export function TabsTrigger({ value, children }: { value: string; children: ReactNode }) {
  return (
    <T.Trigger
      value={value}
      className="inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1.5 text-[12.5px] font-semibold text-ink-2 hover:text-ink data-[state=active]:bg-ink data-[state=active]:text-bg"
    >
      {children}
    </T.Trigger>
  );
}
