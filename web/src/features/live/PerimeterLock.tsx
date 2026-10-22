// Perimeter Lock: territory is not threat. For the latest perimeter_lock insight at the clock it
// shows how many of the side's final-third passes reached the box, the box entries against the
// other final-third passes on a final-third map, and the standard stat (field tilt) muted beside it.
import { AnimatePresence, m as motion } from "motion/react";
import { BOX, FINAL_THIRD_X, PX, PY, sideColor } from "../../components/pitch/Pitch";
import { TeamDot } from "../../components/ui/badge";
import { Panel } from "../../components/ui/card";
import { Empty } from "../../components/ui/skeleton";
import { Tip } from "../../components/ui/tooltip";
import { useData } from "../../data/context";
import { clock, num, words } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { useReplay } from "../../state/replay";
import { PCT_METRICS } from "./shared";

export function PerimeterLock() {
  const m = useData();
  const { t, lang } = useT();
  const tl = m.timeline;
  const id = useReplay((s) => m.latest(s.t, (i) => i.insight_type === "perimeter_lock")?.insight_id ?? null);
  const ins = id ? m.byId[id]! : null;
  if (!ins) {
    return (
      <Panel id="perimeter" title={t("perimeter")} subtitle={t("perimeter_note")}>
        <Empty className="flex min-h-[150px] items-center justify-center">{t("lock_none")}</Empty>
      </Panel>
    );
  }
  const mt = ins.payload.metrics ?? {};
  const side = m.sideOf(ins.teams.primary);
  const color = sideColor(side);
  const chip = ins.context_chip;
  const pts = ins.payload.points ?? [];
  return (
    <Panel
      id="perimeter"
      title={t("perimeter")}
      subtitle={t("perimeter_note")}
      actions={
        <span className="display shrink-0 text-[15px] font-semibold text-ink-3">
          {clock(ins.clock.start_sec, tl.periods)}
        </span>
      }
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={ins.insight_id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          data-insight-id={ins.insight_id}
          data-claim-id={ins.claim_id}
          className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4"
        >
          <div className="min-w-0">
            <div className="flex items-baseline gap-1.5" data-testid="lock-entries">
              <span className="display text-[52px] font-bold leading-none" style={{ color }}>
                {num(mt.box_entries as number, lang)}
              </span>
              <span className="display text-[26px] font-semibold leading-none text-ink-3">
                / {num(mt.team_f3_passes as number, lang)}
              </span>
            </div>
            <p className="mt-1.5 text-[13px] leading-snug text-ink-2">
              <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
                <TeamDot side={side} />
                {ins.teams.primary}
              </span>{" "}
              · {t("f3_passes")} {t("reached_box")}
            </p>
            {chip?.standard_metric != null && chip.standard_value != null && (
              <Tip content={t("standard_note")}>
                <button
                  type="button"
                  className="mt-3 inline-flex max-w-full flex-wrap items-center gap-x-2 gap-y-0.5 rounded-lg border border-dashed border-line-strong px-2.5 py-1.5 text-left text-[12px] text-ink-3 hover:text-ink-2"
                >
                  <span className="eyebrow !text-[10.5px]">{t("standard_stat")}</span>
                  <span>
                    {words(chip.standard_metric)}{" "}
                    <b className="num font-semibold text-ink-2">
                      {num(chip.standard_value, lang)}
                      {PCT_METRICS.has(chip.standard_metric) ? "%" : ""}
                    </b>
                  </span>
                </button>
              </Tip>
            )}
          </div>
          <svg
            viewBox={`${FINAL_THIRD_X * PX - 1} -1 ${(100 - FINAL_THIRD_X) * PX + 3} 70`}
            className="block h-[170px] w-auto"
            role="img"
            aria-label={`${t("perimeter")}: ${ins.teams.primary} ${num(mt.box_entries as number, lang)} / ${num(mt.team_f3_passes as number, lang)}`}
          >
            <rect
              x={FINAL_THIRD_X * PX}
              y="0"
              width={(100 - FINAL_THIRD_X) * PX}
              height="68"
              fill="var(--pitch)"
              stroke="var(--pitch-line)"
              strokeWidth="0.4"
            />
            <rect
              x={BOX.x * PX}
              y={BOX.y0 * PY}
              width={(100 - BOX.x) * PX}
              height={(BOX.y1 - BOX.y0) * PY}
              fill={color}
              opacity="0.16"
              stroke={color}
              strokeWidth="0.5"
            />
            {pts.map((pt) => {
              const entry = pt.kind === "box_entry";
              const x = pt.x_end ?? pt.x;
              const y = pt.y_end ?? pt.y;
              return (
                <circle
                  key={pt.event_id}
                  data-event-id={pt.event_id}
                  data-kind={pt.kind}
                  data-team={ins.teams.primary}
                  cx={x * PX}
                  cy={y * PY}
                  r={entry ? 1.7 : 1}
                  fill={entry ? color : "var(--ink-3)"}
                  opacity={entry ? 1 : 0.55}
                  stroke="var(--pitch)"
                  strokeWidth="0.3"
                />
              );
            })}
          </svg>
        </motion.div>
      </AnimatePresence>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-3">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          {t("box_entries")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-ink-3" />
          {t("other_passes")}
        </span>
      </div>
    </Panel>
  );
}
