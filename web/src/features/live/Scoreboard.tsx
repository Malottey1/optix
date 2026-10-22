// Match header: teams, score, phase and clock, scorers so far, and the momentum tug-of-war.
// The clock text moves every frame through a ref; everything else re-renders only on a goal,
// a phase change or a new momentum minute.
import { useRef } from "react";
import { TeamDot } from "../../components/ui/badge";
import { useData } from "../../data/context";
import { lastAtOrBefore } from "../../data/model";
import { cx } from "../../lib/cx";
import { clock, num, phase } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import { useReplay, useReplayFrame } from "../../state/replay";

const PHASE_KEY: Record<ReturnType<typeof phase>, Key> = {
  pre: "pre_match",
  first: "first_half",
  half: "half_time",
  second: "second_half",
  full: "full_time",
};

export function useMomentumAt() {
  const m = useData();
  const mom = m.timeline.momentum;
  const i = useReplay((s) => lastAtOrBefore(mom, s.t, (x) => x[0]));
  return i >= 0 ? mom[i]! : ([0, 0] as [number, number]);
}

function ClockText({ className }: { className?: string }) {
  const m = useData();
  const ref = useRef<HTMLSpanElement>(null);
  const last = useRef("");
  useReplayFrame(
    (s) => {
      const c = clock(s.t, m.timeline.periods);
      if (ref.current && c !== last.current) {
        ref.current.textContent = c;
        last.current = c;
      }
    },
    [m],
  );
  return <span id="clock" ref={ref} className={className} aria-live="off" />;
}

export function MomentumTug({ className }: { className?: string }) {
  const m = useData();
  const { t, lang } = useT();
  const tl = m.timeline;
  const [, v] = useMomentumAt();
  const lead = v > 0 ? tl.home.code : v < 0 ? tl.away.code : null;
  const w = Math.min(100, Math.abs(v)) / 2;
  return (
    <div className={cx("flex items-center gap-3", className)} data-testid="momentum-bar">
      <span className="eyebrow hidden shrink-0 sm:inline">{t("momentum")}</span>
      <span className="w-9 shrink-0 text-right text-[12px] font-bold text-home">{tl.home.code}</span>
      <svg
        viewBox="0 0 200 12"
        preserveAspectRatio="none"
        className="h-3 min-w-0 flex-1"
        role="img"
        aria-label={`${t("momentum")}: ${lead ? `${lead} ${t("pulling")}` : t("level")} ${num(Math.abs(v), lang)}`}
      >
        <rect x="0" y="0" width="200" height="12" rx="6" fill="var(--surface-3)" />
        <rect
          data-momentum={v}
          x={v >= 0 ? 100 - w : 100}
          y="1.5"
          width={w}
          height="9"
          rx="4.5"
          fill={v >= 0 ? "var(--home)" : "var(--away)"}
          style={{ transition: "x 400ms ease, width 400ms ease" }}
        />
        <line
          x1="100"
          x2="100"
          y1="0"
          y2="12"
          stroke="var(--ink-3)"
          strokeWidth="1.2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <span className="w-9 shrink-0 text-[12px] font-bold text-away">{tl.away.code}</span>
      <span className="display w-[4.5rem] shrink-0 text-right text-[18px] font-semibold leading-none text-ink">
        {lead ? (
          <>
            <span className={v > 0 ? "text-home" : "text-away"}>{lead}</span> {num(Math.abs(v), lang)}
          </>
        ) : (
          <span className="text-[13px] font-semibold text-ink-3">{t("level")}</span>
        )}
      </span>
    </div>
  );
}

function Scorers({ side }: { side: "home" | "away" }) {
  const m = useData();
  const tl = m.timeline;
  const n = useReplay((s) => tl.goals.filter((g) => g.clock_sec <= s.t).length);
  const code = tl[side].code;
  const goals = tl.goals.slice(0, n).filter((g) => g.team === code);
  if (!goals.length) return null;
  return (
    <ul
      className={cx(
        "mt-2 hidden flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-ink-3 md:flex",
        side === "away" && "justify-end",
      )}
    >
      {goals.map((g) => (
        <li key={g.event_id} data-event-id={g.event_id} className="whitespace-nowrap">
          <span className="text-ink-2">{tl.players[g.player_id]?.name ?? g.player_id}</span>{" "}
          <span className="num">{clock(g.clock_sec, tl.periods)}</span>
        </li>
      ))}
    </ul>
  );
}

export function Scoreboard() {
  const m = useData();
  const { t } = useT();
  const tl = m.timeline;
  const goalIdx = useReplay((s) => tl.goals.filter((g) => g.clock_sec <= s.t).length);
  const ph = useReplay((s) => phase(s.t, tl.periods, tl.duration_sec));
  const playing = useReplay((s) => s.playing);
  const g = tl.goals[goalIdx - 1];
  return (
    <section
      aria-label={`${tl.home.name} ${tl.away.name}`}
      data-playing={String(playing)}
      className="relative overflow-hidden rounded-2xl border border-line bg-surface-1 elev-1"
    >
      <div aria-hidden="true" className="absolute inset-y-0 left-0 w-1 bg-home" />
      <div aria-hidden="true" className="absolute inset-y-0 right-0 w-1 bg-away" />
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 px-4 pb-3 pt-4 sm:gap-8 sm:px-7 sm:pt-5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <TeamDot side="home" className="hidden sm:inline-block" />
            <span className="display text-[30px] font-bold leading-none text-ink sm:text-[44px]">{tl.home.code}</span>
          </div>
          <div className="mt-1 hidden truncate text-[14px] text-ink-3 sm:block">{tl.home.name}</div>
          <Scorers side="home" />
        </div>
        <div className="text-center">
          <div
            id="score"
            data-testid="score"
            aria-live="polite"
            className="display text-[48px] font-bold leading-[0.9] text-ink sm:text-[76px]"
          >
            {g ? g.score_home : 0}
            <span className="mx-2 text-ink-3 sm:mx-3">–</span>
            {g ? g.score_away : 0}
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-[12px] font-semibold">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-accent-line bg-accent-soft px-2 py-0.5 uppercase tracking-[0.1em] text-accent">
              <span className="pulse-dot" aria-hidden="true" />
              {t("replay")}
            </span>
            <span className="text-ink-2">{t(PHASE_KEY[ph])}</span>
            <ClockText className="display min-w-[3.4rem] rounded-md bg-surface-3 px-1.5 py-0.5 text-[16px] font-semibold leading-tight text-ink" />
          </div>
        </div>
        <div className="min-w-0 text-right">
          <div className="flex items-center justify-end gap-2">
            <span className="display text-[30px] font-bold leading-none text-ink sm:text-[44px]">{tl.away.code}</span>
            <TeamDot side="away" className="hidden sm:inline-block" />
          </div>
          <div className="mt-1 hidden truncate text-[14px] text-ink-3 sm:block">{tl.away.name}</div>
          <Scorers side="away" />
        </div>
      </div>
      <div className="border-t border-line px-4 py-2.5 sm:px-7">
        <MomentumTug />
      </div>
      <p className="sr-only">{t("replay_note")}</p>
    </section>
  );
}
