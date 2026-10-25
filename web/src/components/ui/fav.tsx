// The favourite star (a toggle button, never inside a link) and the "Following" filter chip.
import { useT } from "../../lib/i18n";
import { cx } from "../../lib/cx";
import { num } from "../../lib/format";
import { toggleFavourite, useFavourites, type FavKind } from "../../state/favourites";
import { Glyph } from "../icons";

const fill = (s: string, vars: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

export function FavStar({
  kind,
  id,
  name,
  className,
}: {
  kind: FavKind;
  id: string;
  name: string;
  className?: string;
}) {
  const { t } = useT();
  const on = useFavourites((s) => s[kind].includes(id));
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={fill(t("fav_follow"), { name })}
      data-fav={`${kind}:${id}`}
      onClick={() => toggleFavourite(kind, id)}
      className={cx(
        "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-ink-3 hover:text-ink",
        on ? "border-accent-line text-accent" : "border-line bg-surface-1/80",
        className,
      )}
    >
      <Glyph name="star" filled={on} className="h-[18px] w-[18px]" />
    </button>
  );
}

export function FollowingChip({ on, count, onChange }: { on: boolean; count: number; onChange: (v: boolean) => void }) {
  const { t, lang } = useT();
  return (
    <button
      type="button"
      aria-pressed={on}
      data-following-chip
      onClick={() => onChange(!on)}
      className={cx(
        "inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold",
        on ? "border-accent-line bg-accent/10 text-ink" : "border-line text-ink-2 hover:text-ink",
      )}
    >
      <Glyph name="star" filled={on} className="h-4 w-4" />
      {t("fav_following")} <span className="num text-ink-3">{num(count, lang)}</span>
    </button>
  );
}
