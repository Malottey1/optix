import type { ButtonHTMLAttributes } from "react";
import { cx } from "../../lib/cx";

type Variant = "primary" | "outline" | "ghost" | "quiet";
type Size = "sm" | "md" | "icon" | "icon-sm";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-ink hover:brightness-110 font-bold",
  outline: "border border-line bg-surface-2 text-ink-2 hover:border-line-strong hover:text-ink font-semibold",
  ghost: "text-ink-2 hover:bg-surface-3 hover:text-ink font-semibold",
  quiet: "border border-line text-ink-2 hover:border-accent-line hover:text-ink font-semibold",
};
const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[12.5px] gap-1.5",
  md: "h-10 px-4 text-[14px] gap-2",
  icon: "h-10 w-10",
  "icon-sm": "h-8 w-8",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({ variant = "outline", size = "md", className, type = "button", ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full transition-[color,background-color,border-color,filter] duration-150 disabled:opacity-50",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    />
  );
}
