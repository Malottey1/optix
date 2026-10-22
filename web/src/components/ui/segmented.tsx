// Single-choice segmented control on Radix ToggleGroup (arrow keys move between options).
import * as TG from "@radix-ui/react-toggle-group";
import { cx } from "../../lib/cx";

export function Segmented<V extends string>({
  label,
  value,
  options,
  onChange,
  name,
  size = "sm",
  className,
}: {
  label: string;
  value: V;
  options: { value: V; label: string }[];
  onChange: (v: V) => void;
  name: string;
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <TG.Root
      type="single"
      aria-label={label}
      value={value}
      onValueChange={(v) => v && onChange(v as V)}
      className={cx("inline-flex shrink-0 rounded-full border border-line bg-surface-2 p-0.5", className)}
    >
      {options.map((o) => (
        <TG.Item
          key={o.value}
          value={o.value}
          data-name={name}
          data-value={o.value}
          className={cx(
            "rounded-full font-semibold text-ink-2 transition-colors hover:text-ink data-[state=on]:bg-ink data-[state=on]:text-bg",
            size === "sm" ? "px-2.5 py-1 text-[12px]" : "px-3.5 py-1.5 text-[13px]",
          )}
        >
          {o.label}
        </TG.Item>
      ))}
    </TG.Root>
  );
}
