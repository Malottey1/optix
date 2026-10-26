// The focus panels: the focus-metric readout (one large value for the replay clock, a plain one-liner,
// a sparkline of the metric's existing series) and the "Player so far" card. Both only read series
// and events already in the data (docs/personalization.md); nothing here is a new metric.
import { useMemo } from "react";
import { useData } from "../../data/context";
import { soFarFromEvents, soFarFromLog, type SoFar } from "../../data/events";
import { useEventFile } from "../../data/matchContext";
import { SHOWCASE_ID, type MatchFile } from "../../data/matches";
import { lastAtOrBefore } from "../../data/model";
import { Icon, type IconName } from "../../icons";
import { clock, num } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import { CONFIG, type MetricId } from "../../lib/personalize";
import { stressAt } from "../../lib/viz";
import { useReplay } from "../../state/replay";
import { useFan } from "../../state/view";
import type { Period } from "../../types/ui";
import { shotStats } from "../viz/ShotBlocks";
import { metricLabel } from "./controls";

const fill = (s: string, vars: Record<string, string>) => s.replace(/\{(\w+)\}/g, (_, k: string) => vars[k] ?? "");

type Pt = [number, number];

/** A small polyline of a series (no numbers: the value is the readout's). */
function Spark({ lines, x1, zero = false }: { lines: { pts: Pt[]; color: string }[]; x1: number; zero?: boolean }) {
  const all = lines.flatMap((l) => l.pts.map((p) => p[1]));
  const lo = Math.min(0, ...all);
  const hi = Math.max(1e-9, ...all);
  const X = (x: number) => (x / Math.max(1, x1)) * 200;
  const Y = (y: number) => 38 - ((y - lo) / (hi - lo || 1)) * 36;
  return (
    <svg viewBox="0 0 200 40" preserveAspectRatio="none" className="block h-10 w-full" aria-hidden="true" data-spark>
      {zero && lo < 0 && <line x1="0" x2="200" y1={Y(0)} y2={Y(0)} stroke="var(--line-strong)" strokeDasharray="3 3" />}
      {lines.map((l, i) =>
        l.pts.length > 1 ? (
          <polyline
            key={i}
            points={l.pts.map((p) => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ")}
            fill="none"
            stroke={l.color}
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        ) : null,
      )}
    </svg>
  );
}

interface Reading {
  values: { label: string; text: string; raw: number | string }[];
  lines: { pts: Pt[]; color: string }[];
  x1: number;
  zero?: boolean;
  line: string;
  at: string;
}

function ReadoutCard({ metric, r }: { metric: MetricId; r: Reading }) {
  const { t } = useT();
  const fan = useFan();
  return (
    <section
      aria-labelledby="metric-readout-h"
      data-metric-readout={metric}
      className="rounded-2xl border border-accent-line bg-surface-1 px-4 py-3"
    >
      <div className="flex items-center gap-2">
        <Icon name={CONFIG.metrics[metric].icon as IconName} size={18} />
        <h2 id="metric-readout-h" className="min-w-0 flex-1 text-[14px] font-semibold text-ink">
          {metricLabel(metric, fan, t)}
        </h2>
        <span className="text-[12px] text-ink-3">{fill(t("so_far_at"), { clock: r.at })}</span>
      </div>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-5 gap-y-1">
        {r.values.map((v) => (
          <span key={v.label} className="inline-flex items-baseline gap-1.5" data-readout-value={v.raw}>
            {v.label && <span className="text-[12px] font-semibold text-ink-3">{v.label}</span>}
            <b className="display num text-[34px] font-semibold leading-none text-ink">{v.text}</b>
          </span>
        ))}
      </div>
      <Spark lines={r.lines} x1={r.x1} zero={r.zero} />
      <p className="text-[12.5px] leading-snug text-ink-2">{r.line}</p>
      <p className="mt-0.5 text-[11.5px] text-ink-3">{t("metric_ref_none")}</p>
    </section>
  );
}

const mmss = (sec: number) => {
  const s = Math.max(0, Math.round(sec));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};

/** The live hub's readout for the replay clock (re-renders only when the shown value changes). */
export function LiveMetricReadout({ metric }: { metric: MetricId }) {
  const m = useData();
  const { t, lang } = useT();
  const tl = m.timeline;
  const v = m.ui.visuals;
  const codes = [tl.home.code, tl.away.code];
  const opp = (c: string) => (c === tl.home.code ? tl.away.code : tl.home.code);
  // the selector returns a key that changes only when the readout would
  const key = useReplay((s) => {
    if (metric === "momentum") return String(lastAtOrBefore(tl.momentum, s.t, (x) => x[0]));
    if (metric === "xg") return String(lastAtOrBefore(v.shots, s.t, (x) => x[1]));
    if (metric === "rhythm") return String(lastAtOrBefore(v.rhythm, s.t, (x) => x[2]));
    return codes.map((c) => Math.round(stressAt(v.stress[opp(c)] ?? [], s.t))).join("|") + `|${Math.floor(s.t / 60)}`;
  });
  const r = useMemo<Reading>(() => {
    const t0 = useReplay.getState().t;
    const at = clock(t0, tl.periods);
    const colors = ["var(--home)", "var(--away)"];
    if (metric === "momentum") {
      const i = Number(key);
      const pts = tl.momentum.slice(0, i + 1);
      const val = i >= 0 ? tl.momentum[i]![1] : 0;
      return {
        values: [{ label: "", text: num(val, lang), raw: val }],
        lines: [{ pts, color: "var(--accent)" }],
        x1: tl.duration_sec,
        zero: true,
        line: fill(t("ml_momentum"), { home: tl.home.code, away: tl.away.code }),
        at,
      };
    }
    if (metric === "xg") {
      const shown = v.shots.slice(0, Number(key) + 1);
      return {
        values: codes.map((c) => {
          const x = shotStats(shown.filter((s) => s[2] === c)).xg;
          return { label: c, text: num(x, lang), raw: x };
        }),
        lines: codes.map((c, k) => {
          let acc = 0;
          const pts: Pt[] = [[0, 0]];
          for (const s of shown.filter((s) => s[2] === c)) pts.push([s[1], (acc += s[6])]);
          return { pts, color: colors[k]! };
        }),
        x1: tl.duration_sec,
        line: t("ml_xg"),
        at,
      };
    }
    if (metric === "rhythm") {
      const i = Number(key);
      const val = i >= 0 ? v.rhythm[i]![3] : 0;
      return {
        values: [{ label: "", text: num(val, lang), raw: val }],
        lines: [{ pts: v.rhythm.slice(0, i + 1).map((x) => [x[2], x[3]] as Pt), color: "var(--accent)" }],
        x1: tl.duration_sec,
        line: t("ml_rhythm"),
        at,
      };
    }
    return {
      values: codes.map((c) => {
        const sec = stressAt(v.stress[opp(c)] ?? [], t0);
        return { label: c, text: mmss(sec), raw: mmss(sec) };
      }),
      lines: codes.map((c, k) => ({
        pts: [
          [0, 0] as Pt,
          ...(v.stress[opp(c)] ?? [])
            .filter((sp) => sp[1] <= t0)
            .map((sp) => [sp[1], stressAt(v.stress[opp(c)]!, sp[1])] as Pt),
        ],
        color: colors[k]!,
      })),
      x1: tl.duration_sec,
      line: t("ml_stress"),
      at,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` is the replay position that matters
  }, [metric, key, lang]);
  return <ReadoutCard metric={metric} r={r} />;
}

/** A played match's readout: its momentum series up to the hub clock (?t=) or full time. */
export function FinalMetricReadout({ file, metric, at }: { file: MatchFile; metric: MetricId; at: number }) {
  const { t, lang } = useT();
  if (metric !== "momentum") return null;
  const series = file.momentum as Pt[];
  const i = lastAtOrBefore(series, at, (x) => x[0]);
  const val = i >= 0 ? series[i]![1] : 0;
  return (
    <ReadoutCard
      metric={metric}
      r={{
        values: [{ label: "", text: num(val, lang), raw: val }],
        lines: [{ pts: series.slice(0, i + 1), color: "var(--accent)" }],
        x1: file.duration_sec,
        zero: true,
        line: fill(t("ml_momentum"), { home: file.header.home.code, away: file.header.away.code }),
        at: clock(at, file.periods as Period[]),
      }}
    />
  );
}

const ROWS: [keyof SoFar, Key][] = [
  ["passes", "sf_passes"],
  ["shots", "sf_shots"],
  ["xg", "mt_xg"],
  ["key_passes", "sf_key"],
  ["goals", "sf_goals"],
  ["cards", "sf_cards"],
  ["subs", "sf_subs"],
];

function SoFarCard({
  pid,
  name,
  at,
  counts,
  note,
}: {
  pid: string;
  name: string;
  at: string;
  counts: SoFar | null;
  note?: string;
}) {
  const { t, lang } = useT();
  const fan = useFan();
  return (
    <section
      aria-labelledby="so-far-h"
      data-so-far={pid}
      className="rounded-2xl border border-line bg-surface-1 px-4 py-3"
    >
      <div className="flex items-center gap-2">
        <Icon name="players" size={18} />
        <h2 id="so-far-h" className="min-w-0 flex-1 truncate text-[14px] font-semibold text-ink">
          {t("so_far_title")}: {name}
        </h2>
        <span className="text-[12px] text-ink-3" data-so-far-at>
          {fill(t("so_far_at"), { clock: at })}
        </span>
      </div>
      {counts ? (
        <dl className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-6">
          {ROWS.filter(([k]) => counts[k] !== null).map(([k, label]) => (
            <div
              key={k}
              className="rounded-xl border border-line bg-surface-2 px-2 py-1.5"
              data-count={k}
              data-value={counts[k]!}
            >
              <dt className="truncate text-[11px] text-ink-3">{k === "xg" && fan ? t("gl_xg") : t(label)}</dt>
              <dd className="display num text-[20px] font-semibold leading-none text-ink">{num(counts[k]!, lang)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="mt-2 text-[12.5px] text-ink-3">{t("sf_loading")}</p>
      )}
      {note && <p className="mt-2 text-[11.5px] text-ink-3">{note}</p>}
    </section>
  );
}

/** Live hub: the followed player's counts up to the replay clock, from the showcase event file. */
export function LivePlayerSoFar({ pid }: { pid: string }) {
  const m = useData();
  const ev = useEventFile(SHOWCASE_ID);
  const rows = ev.data?.rows;
  const ci = ev.data ? ev.data.cols.indexOf("clock_sec") : 1;
  const i = useReplay((s) => (rows ? lastAtOrBefore(rows, s.t, (r) => r[ci]!) : -1));
  const upto = rows && i >= 0 ? rows[i]![ci]! : 0;
  const counts = useMemo(
    () => (ev.data ? soFarFromEvents(ev.data, m.ui.visuals.shots, pid, upto) : null),
    [ev.data, m.ui.visuals.shots, pid, upto],
  );
  return (
    <SoFarCard
      pid={pid}
      name={m.timeline.players[pid]?.name ?? pid}
      at={clock(upto, m.timeline.periods)}
      counts={counts}
    />
  );
}

/** Final hub: what the played match's file keeps (shots, goals, cards, substitutions). */
export function FinalPlayerSoFar({ file, pid, at }: { file: MatchFile; pid: string; at: number }) {
  const { t } = useT();
  const counts = useMemo(() => soFarFromLog(file, pid, at), [file, pid, at]);
  return (
    <SoFarCard
      pid={pid}
      name={String(file.players[pid]?.[0] ?? pid)}
      at={clock(at, file.periods as Period[])}
      counts={counts}
      note={t("sf_log_note")}
    />
  );
}
