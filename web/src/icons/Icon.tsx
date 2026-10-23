// <Icon name size title className />: the Optix icon set (docs/icons.md). 24 x 24 viewBox, stroke 1.75,
// round caps and joins, no fill except small dots, colour from currentColor (the card and lane
// icons use the --card-yellow, --card-red and --lane-fill tokens). Decorative by default
// (aria-hidden); with a `title` it becomes role="img" with that accessible name.
import { useId, type CSSProperties } from "react";
import { cx } from "../lib/cx";
import type { IconName } from "./names";
import { ICONS } from "./registry";

export function Icon({
  name,
  size = 20,
  title,
  className,
  style,
}: {
  name: IconName;
  size?: number;
  title?: string;
  className?: string;
  style?: CSSProperties;
}) {
  const id = useId();
  const Glyph = ICONS[name];
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      data-icon={name}
      className={cx("shrink-0", className)}
      style={style}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      {...(title ? { role: "img", "aria-labelledby": id } : { "aria-hidden": true })}
    >
      {title && <title id={id}>{title}</title>}
      <Glyph />
    </svg>
  );
}
