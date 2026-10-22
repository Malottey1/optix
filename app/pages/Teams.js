// #/teams: every team's style fingerprint (season) and a head-to-head lane matchup. All numbers
// come from out/ui.json (engine/profiles.py, engine/style_labels.py, engine/matchup.py). Lanes are
// named from the attacker's point of view on both sides of a matchup.
import { html, React } from "../lib/html.js";
import { cx, num } from "../lib/format.js";
import { useT } from "../lib/i18n.js";
import { Chip, Empty, Panel, RuleTip } from "../components/ui.js";
import { PX, PY, LANE_EDGES, FINAL_THIRD_X } from "../components/Pitch.js";

const LANE_NAME = { left_flank: "Left flank", left_half_space: "Left half-space", center: "Centre",
  right_half_space: "Right half-space", right_flank: "Right flank" };

const pct = (v, lang) => (v == null ? "–" : `${num(v, lang)}%`);
const signed = (v, lang) => (v == null ? "–" : `${v > 0 ? "+" : ""}${num(v, lang)}`);

/** Lane shares as bars, one row per lane (attacker's left flank on top), league share as a tick. */
function LaneBars({ lanes, order, label, field = "share", league = "league", accent = "var(--accent)", id }) {
  const { lang } = useT();
  const max = Math.max(...order.map((l) => Math.max(lanes[l][field] || 0, lanes[l][league] || 0)), 1);
  return html`<div role="group" aria-label=${label}>
    <svg viewBox="0 0 220 110" class="block h-auto w-full" data-chart=${id} aria-hidden="true">
      ${order.map((l, i) => {
        const v = lanes[l][field] || 0, lg = lanes[l][league] || 0;
        const y = i * 22 + 4;
        return html`<g key=${l} data-lane=${l} data-value=${lanes[l][field]}>
          <rect x="96" y=${y} width="110" height="14" rx="3" fill="var(--surface-3)" />
          <rect x="96" y=${y} width=${(v / max) * 110} height="14" rx="3" fill=${accent} opacity="0.85" />
          <line x1=${96 + (lg / max) * 110} x2=${96 + (lg / max) * 110} y1=${y - 2} y2=${y + 16} stroke="var(--ink)" strokeWidth="1.5" />
          <text x="0" y=${y + 11} fill="var(--ink-2)" fontSize="10.5">${LANE_NAME[l]}</text>
        </g>`;
      })}
    </svg>
    <table class="sr-only"><caption>${label}</caption><tbody>
      ${order.map((l) => html`<tr key=${l}><th>${LANE_NAME[l]}</th><td>${pct(lanes[l][field], lang)}</td><td>${pct(lanes[l][league], lang)}</td></tr>`)}
    </tbody></table>
  </div>`;
}

const LABEL_NAME = { tempo: "Tempo", press: "Press", directness: "Passing", territory: "Territory", counter: "Counters" };

function TeamCard({ team, order, index }) {
  const { lang } = useT();
  const top = order.reduce((a, l) => ((team.entry_lanes[l].effect || -99) > (team.entry_lanes[a].effect || -99) ? l : a), order[0]);
  const e = team.entry_lanes[top];
  const soft = team.soft_lane;
  return html`<article data-team=${team.code} class="flex min-w-0 flex-col rounded-2xl border border-line bg-surface-1 card-pad">
    <header class="flex items-baseline justify-between gap-2">
      <div class="min-w-0"><h3 class="text-[22px] font-bold leading-none tracking-tight">${team.code}</h3>
        <p class="mt-1 truncate text-[13px] text-ink-3">${team.name}</p></div>
      <span class="num shrink-0 text-[12px] text-ink-3">${num(team.matches, lang)} matches</span>
    </header>
    <div class="mt-3 flex flex-wrap gap-1.5">
      ${team.labels.map((l) => html`<${RuleTip} key=${l.id} id=${`rule-${team.code}-${l.id}`}
          prefix=${LABEL_NAME[l.id]} label=${l.direction === "typical" ? "typical" : l.label}
          muted=${l.direction === "typical"} end=${index >= 3}
          rule=${html`<span class="block font-semibold">${l.label}</span>
            <span class="mt-1 block">${l.rule}</span>
            <span class="num mt-1.5 block text-ink-2">${team.code}: ${num(l.value, lang)}${l.unit} · league ${num(l.league, lang)}${l.unit}
              · ${l.interval ? `95% interval ${num(l.interval[0], lang)}–${num(l.interval[1], lang)}${l.unit}` : ""} · n=${l.n} · confidence ${l.confidence}</span>`} />`)}
    </div>
    <div class="mt-4">
      <p class="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-3">Attacks from</p>
      <p class="mt-1 text-[13px] text-ink-2"><b class="text-ink">${LANE_NAME[top]}</b> · ${pct(e.share, lang)} of final-third entries
        (league ${pct(e.league, lang)})</p>
      <div class="mt-2"><${LaneBars} lanes=${team.entry_lanes} order=${order} id=${`attack-${team.code}`}
          label=${`${team.code} final-third entries by lane`} /></div>
    </div>
    <div class="mt-3 border-t border-line pt-3">
      <p class="text-[12px] font-semibold uppercase tracking-[0.08em] text-ink-3">Concedes</p>
      ${soft ? html`<p class="mt-1 text-[13px] text-ink-2" data-soft-lane=${soft.lane}>Soft lane: <b class="text-revise">${LANE_NAME[soft.lane]}</b>,
          opponents complete ${pct(soft.rate, lang)} of entries there (league ${pct(soft.league, lang)}, n=${soft.attempted}, ${soft.confidence}).</p>`
        : html`<p class="mt-1 text-[13px] text-ink-3">No lane passes the soft-lane rule.</p>`}
    </div>
  </article>`;
}

const RANK = { high: 3, medium: 2, low: 1 };

function Matchup({ ui }) {
  const { lang } = useT();
  const codes = ui.teams.teams.map((t) => t.code);
  const first = ui.teams.head_to_head.find((h) => h.claim && h.claim.status !== "blocked") || ui.teams.head_to_head[0];
  const [att, setAtt] = React.useState(first.attacker);
  const [dfn, setDfn] = React.useState(first.defender);
  const h = ui.teams.head_to_head.find((x) => x.attacker === att && x.defender === dfn);
  const order = ui.teams.lanes;
  const pick = (setter, other, v) => { if (v === other) { setAtt(dfn); setDfn(att); } else setter(v); };
  const sel = "h-10 rounded-xl border border-line bg-surface-2 px-3 text-[14px] font-semibold text-ink";
  return html`<${Panel} id="h2h" title="Head to head"
      subtitle="Where the attacker's habit meets the defender's soft spot, over the season. Lanes are named from the attacker's point of view: the defender's own right flank is the attacker's left flank, so both sides of a lane describe the same strip of grass.">
    <div class="flex flex-wrap items-end gap-3">
      <label class="flex flex-col gap-1 text-[12px] font-semibold text-ink-3">Attacker
        <select id="h2h-attacker" class=${sel} value=${att} onChange=${(e) => pick(setAtt, dfn, e.target.value)}>
          ${codes.map((c) => html`<option key=${c} value=${c}>${c}</option>`)}</select></label>
      <button type="button" onClick=${() => { setAtt(dfn); setDfn(att); }} aria-label="Swap attacker and defender"
          class="mb-0.5 inline-flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-2 hover:text-ink">⇄</button>
      <label class="flex flex-col gap-1 text-[12px] font-semibold text-ink-3">Defender
        <select id="h2h-defender" class=${sel} value=${dfn} onChange=${(e) => pick(setDfn, att, e.target.value)}>
          ${codes.map((c) => html`<option key=${c} value=${c}>${c}</option>`)}</select></label>
      ${h.claim && html`<span class="ml-auto"><${Chip}>Verifier: ${h.claim.status === "published" ? "passed" : h.claim.status.replace(/_/g, " ")}<//></span>`}
    </div>
    <div class="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <figure class="m-0">
        <svg viewBox="-2 -2 109 72" class="block h-auto w-full rounded-xl" role="img" data-chart="h2h-pitch"
            aria-label=${`${att} attacking ${dfn}: lane mismatch${h.top ? `, top lane ${LANE_NAME[h.top]}` : ", none"}`}>
          <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
          <line x1="52.5" x2="52.5" y1="0" y2="68" stroke="var(--pitch-line)" strokeWidth="0.35" />
          ${order.map((l, i) => {
            const v = h.lanes[l];
            const y0 = LANE_EDGES[i] * PY, y1 = LANE_EDGES[i + 1] * PY;
            const top = l === h.top;
            const both = v.attack_pp > 0 && v.completion_pp > 0;
            return html`<g key=${l} data-lane=${l} data-mismatch=${v.mismatch_pp} data-top=${String(top)}>
              <rect x=${FINAL_THIRD_X * PX} y=${y0} width=${(100 - FINAL_THIRD_X) * PX} height=${y1 - y0}
                  fill=${top ? "var(--revise)" : both ? "var(--accent)" : "transparent"} opacity=${top ? 0.28 : both ? 0.1 : 0} />
              <line x1="0" x2="105" y1=${y1} y2=${y1} stroke="var(--pitch-line)" strokeWidth="0.25" strokeDasharray="0.8 0.8" />
              <text x="3" y=${(y0 + y1) / 2 + 1} fill="var(--ink-2)" fontSize="2.6">${LANE_NAME[l]}</text>
              <text x="103" y=${(y0 + y1) / 2 + 1.2} fill=${top ? "var(--revise)" : "var(--ink)"} fontSize="3" fontWeight="700"
                  textAnchor="end">${signed(v.mismatch_pp, lang)}</text>
            </g>`;
          })}
          <rect x="0" y="0" width="105" height="68" fill="none" stroke="var(--pitch-line)" strokeWidth="0.35" />
          <line x1=${FINAL_THIRD_X * PX} x2=${FINAL_THIRD_X * PX} y1="0" y2="68" stroke="var(--pitch-line)" strokeWidth="0.3" strokeDasharray="1.2 1.2" />
          <rect x=${84 * PX} y=${22 * PY} width=${16 * PX} height=${56 * PY} fill="none" stroke="var(--pitch-line)" strokeWidth="0.35" />
        </svg>
        <figcaption class="mt-2 text-[12.5px] text-ink-3">${att} attacking left to right. Figure per lane: mismatch in percentage points
          (attacker's lift in entries + defender's lift in completion conceded); a lane counts only when both lifts are positive.</figcaption>
      </figure>
      <div class="min-w-0">
        ${h.claim && h.claim.text
          ? html`<p class="text-[16px] font-semibold leading-snug" data-role="matchup-sentence" lang=${lang}>${(h.claim.text[lang] || h.claim.text.en).casual}</p>
              <p class="mt-2 text-[13px] leading-relaxed text-ink-2" lang=${lang}>${(h.claim.text[lang] || h.claim.text.en).analyst}</p>
              <p class="mt-2 text-[12px] text-ink-3">Confidence ${h.claim.confidence} · ${num(h.claim.evidence_event_ids.length, lang)} evidence events</p>`
          : html`<${Empty}>No lane where ${att}'s attacking habit and ${dfn}'s soft spot line up.<//>`}
        <div class="mt-4 overflow-x-auto rounded-xl border border-line">
          <table class="w-full min-w-[420px] border-collapse text-[12.5px]" data-table="h2h">
            <thead class="bg-surface-2 text-left text-ink-3"><tr>
              <th class="px-3 py-2 font-semibold">Lane</th><th class="px-3 py-2 font-semibold">${att} share</th>
              <th class="px-3 py-2 font-semibold">League</th><th class="px-3 py-2 font-semibold">${dfn} completion conceded</th>
              <th class="px-3 py-2 font-semibold">League</th><th class="px-3 py-2 font-semibold">Mismatch</th></tr></thead>
            <tbody>${order.map((l) => {
              const v = h.lanes[l];
              return html`<tr key=${l} data-lane=${l} class=${cx("border-t border-line", l === h.top && "bg-revise-soft")}>
                <td class="px-3 py-1.5 font-semibold">${LANE_NAME[l]}</td><td class="num px-3 py-1.5">${pct(v.attack_share, lang)}</td>
                <td class="num px-3 py-1.5 text-ink-3">${pct(v.league_share, lang)}</td><td class="num px-3 py-1.5">${pct(v.completion, lang)}</td>
                <td class="num px-3 py-1.5 text-ink-3">${pct(v.league_completion, lang)}</td>
                <td class="num px-3 py-1.5 font-semibold">${signed(v.mismatch_pp, lang)}</td></tr>`;
            })}</tbody>
          </table>
        </div>
      </div>
    </div>
  <//>`;
}

export function TeamsPage({ data }) {
  const { lang } = useT();
  const ui = data.ui;
  return html`<div class="stack-gap flex flex-col" data-page="teams">
    <header>
      <h1 class="text-[26px] font-bold tracking-tight sm:text-[30px]">Team Board</h1>
      <p class="mt-1 max-w-3xl text-[14px] leading-relaxed text-ink-2">Style fingerprints from the season's event data
        (${num(ui.teams.matches, lang)} matches, ${num(ui.teams.teams.length, lang)} fictional teams). Every label is derived from the team's
        metrics by a fixed rule; hover or focus a label to read it.</p>
    </header>
    <div class="stack-gap grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5">
      ${ui.teams.teams.map((t, i) => html`<${TeamCard} key=${t.code} team=${t} order=${ui.teams.lanes} index=${i} />`)}
    </div>
    <${Matchup} ui=${ui} />
  </div>`;
}
