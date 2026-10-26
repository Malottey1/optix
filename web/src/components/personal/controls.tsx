// Personalization controls: the Fan | Analyst view switch (Match Hub header and Settings), the
// "Following: <name>" chip, the "Focus on this player" button and the focus-metric picker. They only
// change what is shown (state/view.ts); every number still comes from the data.
import { Icon, type IconName } from "../../icons";
import { cx } from "../../lib/cx";
import { useT, type Key } from "../../lib/i18n";
import { CONFIG, METRICS, type MetricId, type Mode } from "../../lib/personalize";
import { setFocus, setMetric, setMode, useView } from "../../state/view";
import { Glyph } from "../icons";
import { Segmented } from "../ui/segmented";

const fill = (s: string, vars: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

export function ModeToggle({ className }: { className?: string }) {
  const { t } = useT();
  const mode = useView((s) => s.mode);
  return (
    <Segmented<Mode>
      label={t("mode_label")}
      name="view-mode"
      value={mode}
      onChange={setMode}
      className={className}
      options={[
        { value: "fan", label: t("mode_fan") },
        { value: "analyst", label: t("mode_analyst") },
      ]}
    />
  );
}

/** "Following: <name> ×": shown while a player is focused; the button stops the focus. */
export function FollowChip({ name }: { name: string }) {
  const { t } = useT();
  return (
    <span
      data-following
      className="inline-flex min-h-[32px] items-center gap-1 rounded-full border border-accent-line bg-accent-soft pl-3 pr-1 text-[12px] font-semibold text-ink"
    >
      {fill(t("following"), { name })}
      <button
        type="button"
        aria-label={fill(t("following_remove"), { name })}
        title={fill(t("following_remove"), { name })}
        onClick={() => setFocus(null)}
        data-following-remove
        className="inline-flex h-7 w-7 items-center justify-center rounded-full text-ink-2 hover:bg-surface-3 hover:text-ink"
      >
        <Glyph name="close" className="h-3.5 w-3.5" />
      </button>
    </span>
  );
}

export function FocusButton({ id, className }: { id: string; className?: string }) {
  const { t } = useT();
  const on = useView((s) => s.focus === id);
  return (
    <button
      type="button"
      aria-pressed={on}
      data-focus-player={id}
      onClick={() => setFocus(on ? null : id)}
      className={cx(
        "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border px-4 text-[13px] font-semibold",
        on
          ? "border-accent-line bg-accent-soft text-ink"
          : "border-line text-ink-2 hover:border-accent-line hover:text-ink",
        className,
      )}
    >
      <Icon name="players" size={18} />
      {on ? t("focus_on") : t("focus_player")}
    </button>
  );
}

/** The metric's name: fan wording from the glossary in Fan view, the metric's own name otherwise. */
export function metricLabel(id: MetricId, fan: boolean, t: (k: Key) => string): string {
  const gl = CONFIG.glossary[id];
  return fan && gl ? t(gl as Key) : t(`mt_${id}` as Key);
}

/** None plus every metric with a series in this hub (`final`: only those a played match carries). */
export function MetricPicker({ final = false, className }: { final?: boolean; className?: string }) {
  const { t } = useT();
  const metric = useView((s) => s.metric);
  const fan = useView((s) => s.mode === "fan");
  const offered = METRICS.filter((id) => !final || CONFIG.metrics[id].final);
  const btn = (on: boolean) =>
    cx(
      "inline-flex min-h-[32px] items-center gap-1.5 rounded-full border px-2.5 text-[12px] font-semibold",
      on ? "border-accent-line bg-accent-soft text-ink" : "border-line text-ink-3 hover:text-ink",
    );
  return (
    <div
      role="group"
      aria-label={t("metric_focus")}
      data-metric-picker
      className={cx("flex flex-wrap gap-1.5", className)}
    >
      <button
        type="button"
        aria-pressed={metric === null}
        data-metric="none"
        onClick={() => setMetric(null)}
        className={btn(metric === null)}
      >
        {t("metric_none")}
      </button>
      {offered.map((id) => (
        <button
          key={id}
          type="button"
          aria-pressed={metric === id}
          data-metric={id}
          onClick={() => setMetric(metric === id ? null : id)}
          className={btn(metric === id)}
        >
          <Icon name={CONFIG.metrics[id].icon as IconName} size={16} />
          {metricLabel(id, fan, t)}
        </button>
      ))}
    </div>
  );
}
