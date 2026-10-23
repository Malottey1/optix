// Club crest for the five fictional clubs (web/public/brand/teams, made by tools/make_brand_assets.py).
// Below 40 px a crest's lettering is unreadable and two of the crests differ only by outline, so a
// mini-mark is drawn instead: a disc in the club's accent with its code. The same mini-mark is the
// fallback when the image fails or the code is not one of the five.
// Accessibility: when the club's name or code is shown beside the badge, pass `named` and the badge is
// decorative (alt=""); otherwise its alternative text is the club name.
// Team accents (--team-*) appear only here, next to a crest or code, never alone and never to mark a
// verdict: passed / revised / blocked keep their own colours and icons.
import { useState } from "react";
import { cx } from "../../lib/cx";

export const TEAM_NAMES: Record<string, string> = {
  AUR: "Aurelia Rovers",
  NTG: "Northgate Town",
  CAL: "Calder Athletic",
  VES: "Veston United",
  HAR: "Harbor Wanderers",
};

export const MINI_BELOW = 40;

export function badgeSrc(code: string, size: number): string {
  return `./brand/teams/badge-${code.toLowerCase()}-${size <= 48 ? 96 : 192}.webp`;
}

export function TeamBadge({
  code,
  size = 32,
  named = false,
  className,
}: {
  code: string;
  size?: number;
  named?: boolean;
  className?: string;
}) {
  const c = code.toUpperCase();
  const [failed, setFailed] = useState(false);
  const name = TEAM_NAMES[c] ?? c;
  const known = c in TEAM_NAMES;
  if (!known || failed || size < MINI_BELOW) {
    return (
      <span
        data-team-badge={c}
        data-badge="mini"
        role={named ? undefined : "img"}
        aria-label={named ? undefined : name}
        aria-hidden={named ? true : undefined}
        className={cx(
          "inline-grid shrink-0 select-none place-items-center rounded-full font-display font-bold leading-none tracking-[0.02em] text-[#05080f]",
          className,
        )}
        style={{
          width: size,
          height: size,
          fontSize: Math.max(9, Math.round(size * 0.37)),
          background: known ? `var(--team-${c.toLowerCase()})` : "var(--ink-3)",
        }}
      >
        {c}
      </span>
    );
  }
  return (
    <img
      data-team-badge={c}
      data-badge="crest"
      src={badgeSrc(c, size)}
      width={size}
      height={size}
      alt={named ? "" : name}
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={cx("shrink-0 object-contain", className)}
    />
  );
}
