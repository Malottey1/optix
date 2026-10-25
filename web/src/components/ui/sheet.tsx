// A side sheet on Radix Dialog: focus trap, Escape, scroll lock and labelling come from Radix.
// Sheets open from plain buttons (no Dialog.Trigger), so the opener is remembered here and gets
// focus back on close; Radix alone would send it to the body.
import * as Dialog from "@radix-ui/react-dialog";
import { useRef, type ReactNode } from "react";
import { cx } from "../../lib/cx";
import { Glyph } from "../icons";

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
  bottomOnPhone = false,
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
  /** below 640 px: a bottom sheet (thumb reach) instead of a full-height side sheet */
  bottomOnPhone?: boolean;
}) {
  const opener = useRef<HTMLElement | null>(null);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay fixed inset-0 z-50 bg-black/65 backdrop-blur-[2px]" />
        <Dialog.Content
          id={id}
          {...attrs}
          aria-describedby={description ? undefined : undefined}
          className={cx(
            "sheet fixed z-50 flex w-full flex-col border-line bg-surface-1 elev-2 outline-none",
            bottomOnPhone
              ? "inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl border-t sm:inset-x-auto sm:inset-y-0 sm:right-0 sm:max-h-none sm:rounded-none sm:border-l sm:border-t-0"
              : "inset-y-0 right-0 border-l",
            width,
          )}
          data-bottom-sheet={bottomOnPhone ? "phone" : undefined}
          onOpenAutoFocus={() => {
            // fires before focus moves into the sheet: the active element is still the opener
            opener.current = document.activeElement as HTMLElement | null;
          }}
          onCloseAutoFocus={(e) => {
            const el = opener.current;
            opener.current = null;
            if (el && el !== document.body && el.isConnected) {
              e.preventDefault();
              el.focus();
            }
          }}
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
              <Glyph name="close" className="h-4 w-4" />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto overscroll-contain px-5 py-5">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
