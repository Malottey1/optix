// The Focus Pitch: the evidence of the insight in focus (the selected card, else the latest card
// with points), drawn in its team's attacking frame, plus a ball marker at the latest on-ball event
// location with a short trail of the events before it. The ball and trail move through refs.
import { AnimatePresence, m as motion } from "motion/react";
import { useRef } from "react";
import { Icon } from "../../components/icons";
import { Arrowheads, InsightLayer, PitchLines, PX, PY, sideColor } from "../../components/pitch/Pitch";
import { Chip, StatusChip, TeamDot } from "../../components/ui/badge";
import { Panel } from "../../components/ui/card";
import { useData } from "../../data/context";
import type { MatchModel } from "../../data/model";
import { clock } from "../../lib/format";
import { useT } from "../../lib/i18n";
import { useReplay, useReplayFrame, type ReplayState } from "../../state/replay";
import type { Insight } from "../../types/ui";
import { statusOf, textOf } from "./shared";

const TRAIL = 5;

export function pitchInsightId(m: MatchModel, s: Pick<ReplayState, "t" | "selected">): string | null {
  if (s.selected) {
    const sel = m.byId[s.selected];
    if (sel && sel.clock.start_sec <= s.t) return s.selected;
  }
  return m.latest(s.t, (i) => (i.payload.points ?? []).length > 0)?.insight_id ?? null;
}

function BallLayer({ frameTeam }: { frameTeam: string }) {
  const m = useData();
  const ball = useRef<SVGGElement>(null);
  const trail = useRef<SVGPolylineElement>(null);
  const lastIdx = useRef(-2);
  useReplayFrame(
    (s) => {
      const i = m.trackIndex(s.t);
      if (i === lastIdx.current) return;
      lastIdx.current = i;
      const pts: string[] = [];
      let head: [number, number] | null = null;
      for (let k = Math.max(0, i - TRAIL + 1); k <= i; k++) {
        const [, x, y, team] = m.track[k]!;
        const fx = (team === frameTeam ? x : 100 - x) * PX;
        const fy = (team === frameTeam ? y : 100 - y) * PY;
        pts.push(`${fx.toFixed(2)},${fy.toFixed(2)}`);
        head = [fx, fy];
      }
      if (ball.current) {
        ball.current.style.opacity = head ? "1" : "0";
        if (head) ball.current.setAttribute("transform", `translate(${head[0].toFixed(2)} ${head[1].toFixed(2)})`);
        const e = m.track[i];
        if (e) ball.current.dataset.team = e[3];
      }
      if (trail.current) trail.current.setAttribute("points", pts.join(" "));
    },
    [m, frameTeam],
  );
  return (
    <g data-layer="ball" aria-hidden="true">
      <polyline
        ref={trail}
        fill="none"
        stroke="rgba(255,255,255,0.35)"
        strokeWidth="0.35"
        strokeDasharray="0.9 0.9"
        strokeLinejoin="round"
      />
      <g ref={ball} style={{ opacity: 0 }}>
        <circle r="2.2" fill="rgba(255,255,255,0.10)" />
        <circle r="1" fill="#ffffff" stroke="var(--bg)" strokeWidth="0.3" />
      </g>
    </g>
  );
}

function Caption({ ins }: { ins: Insight | null }) {
  const m = useData();
  const { t, lang, typeLabel } = useT();
  if (!ins) {
    return <p className="text-[13.5px] text-ink-3">{t("none_yet")}</p>;
  }
  const status = statusOf(m, ins);
  const label = {
    published: t("verified"),
    published_with_context: t("with_context"),
    revised: t("rewritten"),
    blocked: t("blocked"),
  }[status];
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={ins.insight_id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.2 }}
        className="min-w-0"
        data-insight-id={ins.insight_id}
      >
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <time className="display text-[16px] font-semibold leading-none text-ink">
            {clock(ins.clock.start_sec, m.timeline.periods)}
          </time>
          <span className="inline-flex items-center gap-1.5 font-semibold text-ink-2">
            <TeamDot side={m.sideOf(ins.teams.primary)} />
            {ins.teams.primary}
          </span>
          <Chip>{typeLabel(ins.insight_type)}</Chip>
          <StatusChip status={status} label={label} />
        </div>
        <p
          id="pitch-caption"
          lang={lang}
          className="mt-2 text-[16px] font-semibold leading-snug text-ink sm:text-[18px]"
        >
          {textOf(ins.text.rendered, lang, "casual")}
        </p>
      </motion.div>
    </AnimatePresence>
  );
}

export function FocusPitch() {
  const m = useData();
  const { t } = useT();
  const tl = m.timeline;
  const id = useReplay((s) => pitchInsightId(m, s));
  const ins = id ? m.byId[id]! : null;
  const team = ins ? ins.teams.primary : tl.home.code;
  const side = m.sideOf(team);
  return (
    <Panel
      id="focus"
      title={t("focus_pitch")}
      subtitle={t("pitch_note")}
      actions={
        <span className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface-2 px-2.5 py-1 text-[12px] font-semibold text-ink-2">
          <TeamDot side={side} />
          {team} {t("attacking")}
          <Icon name="arrow" className="h-3.5 w-3.5" />
        </span>
      }
    >
      <figure className="m-0">
        <div className="relative">
          <svg
            id="pitch"
            viewBox="-2.5 -2 110 72"
            role="img"
            aria-label={`${t("focus_pitch")}: ${team} ${t("attacking")}`}
            className="mx-auto block h-auto max-h-[62vh] w-full rounded-xl"
            data-frame-team={team}
            data-team={team}
          >
            <Arrowheads id="focus" />
            <PitchLines />
            <InsightLayer insight={ins} side={side} markerId="focus" />
            <BallLayer frameTeam={team} />
          </svg>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute right-2 top-2 rounded-md px-1.5 py-0.5 text-[10.5px] font-bold uppercase tracking-[0.12em]"
            style={{ color: sideColor(side), background: "rgba(5,8,15,0.6)" }}
          >
            {team} →
          </span>
        </div>
        <figcaption className="mt-4 rounded-xl border border-line bg-surface-2 px-4 py-3">
          <Caption ins={ins} />
        </figcaption>
        <p className="mt-2.5 flex items-center gap-1.5 text-[12px] text-ink-3">
          <Icon name="ball" className="h-3.5 w-3.5" />
          {t("ball_note")}
        </p>
      </figure>
    </Panel>
  );
}
