// Live Center widgets. Each one subscribes to the slice of the replay clock it needs, so a frame
// re-renders only the clock text, the scrubber and whatever actually changed.
import { html, React } from "../lib/html.js";
import { clock, cx, num } from "../lib/format.js";
import { useT } from "../lib/i18n.js";
import { replay, seek, setPlaying, setSpeed, SPEEDS, useReplay } from "../lib/replay.js";
import { Arrowheads, Ball, InsightLayer, PitchLines, PX, PY, FINAL_THIRD_X, BOX } from "./Pitch.js";
import { Panel, Segmented, TeamDot } from "./ui.js";

const sideOf = (tl, code) => (code === tl.home.code ? "home" : "away");

// ---------- scoreboard and transport ----------

export function Scoreboard({ data }) {
  const { t } = useT();
  const tl = data.timeline;
  const goalIdx = useReplay((s) => tl.goals.filter((g) => g.clock_sec <= s.t).length);
  const sec = useReplay((s) => Math.floor(s.t));
  const playing = useReplay((s) => s.playing);
  const g = tl.goals[goalIdx - 1];
  const over = sec >= tl.duration_sec;
  const p2 = tl.periods.find((p) => p.period === 2);
  const ht = p2 && sec > tl.periods[0].end_sec && sec < p2.start_sec;
  const state = over ? t("full_time") : ht ? t("half_time") : playing ? t("live") : t("paused");
  return html`<div class=${cx("relative overflow-hidden rounded-2xl border border-line bg-surface-1", playing && "is-playing")}>
    <div class="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent"></div>
    <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-4 sm:gap-6 sm:px-6 sm:py-5">
      <div class="flex min-w-0 items-center gap-3">
        <span aria-hidden="true" class="hidden h-10 w-1.5 rounded-full bg-home sm:block"></span>
        <div class="min-w-0">
          <div class="text-[26px] font-bold leading-none tracking-tight sm:text-[34px]">${tl.home.code}</div>
          <div class="mt-1 truncate text-[12.5px] text-ink-3 sm:text-[13.5px]">${tl.home.name}</div>
        </div>
      </div>
      <div class="text-center">
        <div id="score" data-testid="score" aria-live="polite"
            class="num text-[40px] font-bold leading-none tracking-tight sm:text-[56px]">
          ${g ? g.score_home : 0}<span class="mx-2 text-ink-3 sm:mx-3">–</span>${g ? g.score_away : 0}</div>
        <div class="mt-2 flex items-center justify-center gap-2 text-[12.5px] font-semibold">
          <span class="live-dot"></span>
          <span class="uppercase tracking-[0.12em] text-accent">${state}</span>
          <span id="clock" class="num rounded-md bg-surface-3 px-1.5 py-0.5 text-ink">${clock(sec, tl.periods)}</span>
        </div>
      </div>
      <div class="flex min-w-0 items-center justify-end gap-3 text-right">
        <div class="min-w-0">
          <div class="text-[26px] font-bold leading-none tracking-tight sm:text-[34px]">${tl.away.code}</div>
          <div class="mt-1 truncate text-[12.5px] text-ink-3 sm:text-[13.5px]">${tl.away.name}</div>
        </div>
        <span aria-hidden="true" class="hidden h-10 w-1.5 rounded-full bg-away sm:block"></span>
      </div>
    </div>
  </div>`;
}

function Scrubber({ data }) {
  const { t } = useT();
  const tl = data.timeline;
  const sec = useReplay((s) => Math.floor(s.t));
  return html`<label class="flex min-w-0 flex-1 items-center gap-3">
    <span class="sr-only">${t("scrub")}</span>
    <input id="scrub" type="range" class="scrub" min="0" max=${tl.duration_sec} step="1" value=${sec}
      aria-valuetext=${clock(sec, tl.periods)}
      onInput=${(e) => seek(+e.target.value)} />
  </label>`;
}

export function Transport({ data }) {
  const { t } = useT();
  const playing = useReplay((s) => s.playing);
  const speed = useReplay((s) => s.speed);
  return html`<div class="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface-1 px-3 py-2.5 sm:flex-nowrap sm:px-4">
    <button id="play" type="button" aria-pressed=${String(playing)} onClick=${() => setPlaying(!playing)}
        class="inline-flex h-10 min-w-[104px] items-center justify-center gap-2 rounded-full bg-accent px-4 text-[14px] font-bold text-accent-ink hover:brightness-110">
      <span aria-hidden="true">${playing ? "❚❚" : "▶"}</span><span>${playing ? t("pause") : t("play")}</span>
    </button>
    <button type="button" onClick=${() => { setPlaying(false); seek(0); }} aria-label=${t("restart")}
        class="inline-flex h-10 w-10 items-center justify-center rounded-full border border-line text-ink-2 hover:text-ink">
      <svg viewBox="0 0 24 24" class="h-[18px] w-[18px]" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 4v4.5h4.5"/></svg>
    </button>
    <${Scrubber} data=${data} />
    <${Segmented} label=${t("speed")} name="speed" value=${speed} onChange=${setSpeed}
      options=${Object.keys(SPEEDS).map((k) => ({ value: k, label: t(k) }))} />
  </div>`;
}

// ---------- focus pitch ----------

function pitchInsightId(data, s) {
  const n = data.visibleCount(s.t);
  if (s.selected) {
    const sel = data.byId[s.selected];
    if (sel && sel.clock.start_sec <= s.t) return s.selected;
  }
  for (let i = n - 1; i >= 0; i--) if ((data.insights[i].payload.points || []).length) return data.insights[i].insight_id;
  return null;
}

function BallLayer({ data, frameTeam }) {
  const entry = useReplay((s) => data.ballAt(s.t));
  return html`<${Ball} entry=${entry} frameTeam=${frameTeam} />`;
}

export function FocusPitch({ data }) {
  const { t, typeLabel, lang } = useT();
  const tl = data.timeline;
  const id = useReplay((s) => pitchInsightId(data, s));
  const ins = id ? data.byId[id] : null;
  const team = ins ? ins.teams.primary : tl.home.code;
  const side = sideOf(tl, team);
  const caption = ins
    ? `${clock(ins.clock.start_sec, tl.periods)} · ${typeLabel(ins.insight_type)} · ${team} ${t("attacking")} →`
    : `${team} ${t("attacking")} →`;
  return html`<${Panel} id="focus" title=${t("focus_pitch")} subtitle=${t("pitch_note")}
      actions=${html`<span class="inline-flex items-center gap-2 whitespace-nowrap text-[12px] font-semibold text-ink-2">
        <${TeamDot} side=${side} />${team} →</span>`}>
    <figure class="m-0">
      <svg id="pitch" viewBox="-2 -2 109 72" role="img" aria-label=${`${t("focus_pitch")}: ${caption}`}
          class="block h-auto w-full rounded-xl" data-frame-team=${team}>
        <${Arrowheads} id="focus" />
        <${PitchLines} />
        <${InsightLayer} insight=${ins} side=${side} markerId="focus" />
        <${BallLayer} data=${data} frameTeam=${team} />
      </svg>
      <figcaption class="mt-3 flex flex-wrap items-center justify-between gap-2 text-[12.5px] text-ink-3">
        <span id="pitch-caption" class="font-medium text-ink-2">${caption}</span>
        <span>${t("ball_note")}</span>
      </figcaption>
    </figure>
  <//>`;
}

// ---------- momentum ----------

const MomentumChart = React.memo(function MomentumChart({ data, upto }) {
  const tl = data.timeline;
  const pts = tl.momentum.filter(([s]) => s <= upto);
  const X = (s) => (s / tl.duration_sec) * 300;
  const Y = (m) => 32 - (m / 100) * 28;
  const d = pts.map(([s, m], i) => `${i ? "L" : "M"}${X(s).toFixed(1)},${Y(m).toFixed(1)}`).join("");
  const area = pts.length > 1 ? `${d}L${X(pts[pts.length - 1][0]).toFixed(1)},32L${X(pts[0][0]).toFixed(1)},32Z` : "";
  return html`<svg id="momentum-chart" viewBox="0 0 300 64" preserveAspectRatio="none" class="block h-16 w-full" aria-hidden="true">
    <defs>
      <clipPath id="mom-top"><rect x="0" y="0" width="300" height="32" /></clipPath>
      <clipPath id="mom-bot"><rect x="0" y="32" width="300" height="32" /></clipPath>
    </defs>
    <line x1="0" x2="300" y1="32" y2="32" stroke="var(--line-strong)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
    ${tl.periods.slice(1).map((p) => html`<line key=${p.period} x1=${X(p.start_sec)} x2=${X(p.start_sec)} y1="0" y2="64"
        stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" strokeDasharray="3 3" />`)}
    ${area && html`<path d=${area} fill="var(--home)" opacity="0.28" clipPath="url(#mom-top)" />`}
    ${area && html`<path d=${area} fill="var(--away)" opacity="0.28" clipPath="url(#mom-bot)" />`}
    ${pts.length > 1 && html`<path d=${d} fill="none" stroke="var(--ink-2)" strokeWidth="1.5" vectorEffect="non-scaling-stroke"
        strokeLinejoin="round" />`}
    ${pts.map(([s, m]) => html`<circle key=${s} data-minute-sec=${s} data-value=${m} cx=${X(s)} cy=${Y(m)} r="0" />`)}
  </svg>`;
});

export function Momentum({ data }) {
  const { t, lang } = useT();
  const tl = data.timeline;
  // one engine value per minute: re-render once per minute of match time, not per frame
  const idx = useReplay((s) => {
    let i = -1;
    for (let k = 0; k < tl.momentum.length && tl.momentum[k][0] <= s.t; k++) i = k;
    return i;
  });
  const [sec, v] = idx >= 0 ? tl.momentum[idx] : [0, 0];
  const w = Math.abs(v) / 2;
  const lead = v > 0 ? tl.home.code : v < 0 ? tl.away.code : null;
  return html`<${Panel} id="momentum" title=${t("momentum")} subtitle=${t("momentum_note")}>
    <div class="flex items-end justify-between gap-3">
      <div class="num text-[30px] font-bold leading-none" data-testid="momentum-value">${num(Math.abs(v), lang)}</div>
      <div class="text-right text-[13px] font-semibold text-ink-2">
        ${lead ? html`<span class="inline-flex items-center gap-1.5"><${TeamDot} side=${v > 0 ? "home" : "away"} />${lead} ${t("pulling")}</span>`
          : t("level")}
      </div>
    </div>
    <div class="mt-3 flex items-center gap-2 text-[11.5px] font-bold">
      <span class="w-9 text-home">${tl.home.code}</span>
      <svg viewBox="0 0 200 12" preserveAspectRatio="none" class="h-3 flex-1" role="img"
          aria-label=${`${t("momentum")}: ${lead || t("level")} ${num(Math.abs(v), lang)}`}>
        <rect x="0" y="0" width="200" height="12" rx="6" fill="var(--surface-3)" />
        <rect data-momentum=${v} x=${v >= 0 ? 100 - w : 100} y="0" width=${w} height="12" rx="3"
            fill=${v >= 0 ? "var(--home)" : "var(--away)"} />
        <line x1="100" x2="100" y1="0" y2="12" stroke="var(--ink-3)" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      </svg>
      <span class="w-9 text-right text-away">${tl.away.code}</span>
    </div>
    <div class="mt-3"><${MomentumChart} data=${data} upto=${sec} /></div>
  <//>`;
}

// ---------- perimeter lock ----------

export function PerimeterLock({ data }) {
  const { t, lang } = useT();
  const tl = data.timeline;
  const id = useReplay((s) => {
    const n = data.visibleCount(s.t);
    for (let i = n - 1; i >= 0; i--) if (data.insights[i].insight_type === "perimeter_lock") return data.insights[i].insight_id;
    return null;
  });
  const ins = id ? data.byId[id] : null;
  if (!ins) {
    return html`<${Panel} id="perimeter" title=${t("perimeter")}>
      <div class="flex h-[170px] items-center justify-center rounded-xl border border-dashed border-line text-[13px] text-ink-3"
          data-state="empty">${t("lock_none")}</div>
    <//>`;
  }
  const m = ins.payload.metrics;
  const side = sideOf(tl, ins.teams.primary);
  const color = side === "home" ? "var(--home)" : "var(--away)";
  return html`<${Panel} id="perimeter" title=${t("perimeter")}
      actions=${html`<span class="whitespace-nowrap text-[12px] font-semibold text-ink-3">${clock(ins.clock.start_sec, tl.periods)}</span>`}>
    <div class="grid grid-cols-[auto_1fr] items-center gap-4" data-insight-id=${ins.insight_id}>
      <div>
        <div class="num text-[40px] font-bold leading-none" data-testid="lock-entries">
          ${m.box_entries}<span class="text-[20px] text-ink-3"> / ${m.team_f3_passes}</span></div>
        <div class="mt-1.5 max-w-[11rem] text-[12.5px] leading-snug text-ink-2">
          <span class="inline-flex items-center gap-1.5 font-semibold text-ink"><${TeamDot} side=${side} />${ins.teams.primary}</span>
          · ${t("f3_passes")} ${t("reached_box")}</div>
      </div>
      <svg viewBox=${`${60 * PX} -1 ${42 * PX} 70`} class="ml-auto block h-[190px] w-auto max-w-full" role="img"
          aria-label=${`${t("perimeter")}: ${ins.teams.primary} ${m.box_entries} / ${m.team_f3_passes}`}>
        <rect x=${FINAL_THIRD_X * PX} y="0" width=${(100 - FINAL_THIRD_X) * PX} height="68" fill="var(--pitch)"
            stroke="var(--pitch-line)" strokeWidth="0.4" />
        <rect x=${BOX.x * PX} y=${BOX.y0 * PY} width=${(100 - BOX.x) * PX} height=${(BOX.y1 - BOX.y0) * PY}
            fill=${color} opacity="0.14" stroke=${color} strokeWidth="0.5" />
        ${(ins.payload.points || []).map((pt) => {
          const entry = pt.kind === "box_entry";
          return html`<circle key=${pt.event_id} data-event-id=${pt.event_id} data-kind=${pt.kind} data-team=${ins.teams.primary}
              cx=${pt.x_end * PX} cy=${pt.y_end * PY} r=${entry ? 1.4 : 0.9}
              fill=${entry ? color : "var(--ink-3)"} opacity=${entry ? 1 : 0.6} stroke="var(--pitch)" strokeWidth="0.3" />`;
        })}
      </svg>
    </div>
    <div class="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-ink-3">
      <span class="inline-flex items-center gap-1.5"><span aria-hidden="true" class="h-2.5 w-2.5 rounded-full" style=${{ background: color }}></span>${t("box_entries")}</span>
      <span class="inline-flex items-center gap-1.5"><span aria-hidden="true" class="h-2.5 w-2.5 rounded-full bg-ink-3"></span>${t("f3_passes")}</span>
    </div>
  <//>`;
}
