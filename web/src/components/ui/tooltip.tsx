// Radix Tooltip: opens on hover and on keyboard focus; the content is the trigger's description.
import * as T from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export const TooltipProvider = T.Provider;

export function Tip({
  content,
  children,
  side = "top",
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
}) {
  return (
    <T.Root delayDuration={150}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          sideOffset={6}
          collisionPadding={12}
          className="tooltip z-[60] max-w-[min(320px,calc(100vw-24px))] rounded-xl border border-line-strong bg-surface-3 px-3 py-2.5 text-[12.5px] leading-relaxed text-ink elev-2"
        >
          {content}
          <T.Arrow className="fill-[var(--surface-3)]" />
        </T.Content>
      </T.Portal>
    </T.Root>
  );
}
