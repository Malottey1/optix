// A side sheet on Radix Dialog: focus trap, Escape, scroll lock and labelling come from Radix.
import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";
import { cx } from "../../lib/cx";
import { Icon } from "../icons";

export function Sheet({
  open,
  onOpenChange,
  id,
  title,
  eyebrow,
  description,
  closeLabel,
  children,
  width = "max-w-[600px]",
  attrs,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  id: string;
  title: ReactNode;
  eyebrow?: ReactNode;
  description?: ReactNode;
  closeLabel: string;
  children: ReactNode;
  width?: string;
  attrs?: Record<string, string>;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay fixed inset-0 z-50 bg-black/65 backdrop-blur-[2px]" />
        <Dialog.Content
          id={id}
          {...attrs}
          aria-describedby={description ? undefined : undefined}
          className={cx(
            "sheet fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-line bg-surface-1 elev-2 outline-none",
            width,
          )}
        >
          <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
            <div className="min-w-0">
              {eyebrow && <div className="eyebrow">{eyebrow}</div>}
              <Dialog.Title className="mt-1 text-[17px] font-semibold leading-snug text-ink">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-1 text-[13px] text-ink-3">{description}</Dialog.Description>
              ) : (
                <Dialog.Description className="sr-only">{title}</Dialog.Description>
              )}
            </div>
            <Dialog.Close
              data-close
              aria-label={closeLabel}
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-ink-2 hover:border-line-strong hover:text-ink"
            >
              <Icon name="close" className="h-4 w-4" />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
