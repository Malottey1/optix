// #/players: involvement, pass quality and chances created per player, from event data only
// (out/ui.json, engine/metrics.py). The Verifier's player rules add the context that stops a
// volume passer or a corner taker from being misread.
import { html, React } from "../lib/html.js";
import { cx, num } from "../lib/format.js";
import { useT } from "../lib/i18n.js";
import { Chip, Panel, Segmented, StatusChip } from "../components/ui.js";

const RULE_TITLE = { wide_forward_passes: "Volume, not value", set_piece_inflation: "Chances from dead balls" };
const SORTS = {
  involvement: { label: "Involvement", key: "involvement" },
  forward: { label: "Forward passes", key: "forward_passes" },
  chances: { label: "Chances created", key: "chances" },
};

function ContextCard({ data, p, c }) {
  const { lang } = useT();
  const [view, setView] = React.useState("after");
  const reason = (data.ui.reasons[lang] || data.ui.reasons.en)[c.rule];
  const txt = (view === "before" ? c.original : c.text)[lang] || (view === "before" ? c.original : c.text).en;
  const rows = c.evidence_event_ids.map((id) => data.ui.evidence[id]).filter(Boolean).slice(0, 5);
  return html`<article data-player=${p.id} data-rule=${c.rule} class="flex min-w-0 flex-col rounded-2xl border border-line bg-surface-1 card-pad">
    <div class="flex flex-wrap items-center gap-2">
      <${StatusChip} status="revised" label=${RULE_TITLE[c.rule]} />
      <span class="ml-auto text-[12px] font-semibold text-ink-3">${p.team} · ${p.position}</span>
    </div>
    <h3 class="mt-2 text-[18px] font-bold tracking-tight">${p.name}</h3>
    <p class=${cx("mt-2 text-[14.5px] font-semibold leading-snug", view === "before" ? "text-ink-2 line-through decoration-block/70" : "text-ink")}
        data-role="player-sentence" lang=${lang}>${txt.casual}</p>
    <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
      <span class="text-[12px] font-semibold text-revise">${view === "before" ? "The plain stat (blocked)" : "What the Verifier lets out"}</span>
      <${Segmented} label="Before or after verification" name=${`pv-${p.id}-${c.rule}`} value=${view} onChange=${setView}
        options=${[{ value: "before", label: "Before" }, { value: "after", label: "After" }]} />
    </div>
    ${reason && html`<p class="mt-2 text-[12.5px] leading-snug text-ink-2"><b class="text-ink">Why:</b> ${reason}</p>`}
    <dl class="mt-3 grid grid-cols-3 gap-2 text-center">
      ${c.rule === "wide_forward_passes"
        ? [["Forward passes", num(p.forward_passes, lang)], ["Ending wide", `${num(p.wide_share, lang)}%`], ["Pass quality", `${num(p.pass_quality_ratio, lang)}×`]]
            .map(([k, v]) => html`<div key=${k} class="rounded-xl bg-surface-2 px-2 py-2"><dd class="num m-0 text-[20px] font-bold">${v}</dd><dt class="mt-0.5 text-[11px] text-ink-3">${k}</dt></div>`)
        : [["Chances", num(p.chances, lang)], ["Set pieces", num(p.chances_set_piece, lang)], ["Open play", num(p.chances_open_play, lang)]]
            .map(([k, v]) => html`<div key=${k} class="rounded-xl bg-surface-2 px-2 py-2"><dd class="num m-0 text-[20px] font-bold">${v}</dd><dt class="mt-0.5 text-[11px] text-ink-3">${k}</dt></div>`)}
    </dl>
    <details class="mt-3 text-[12.5px]">
      <summary class="cursor-pointer font-semibold text-ink-2 hover:text-ink">Evidence (${num(c.evidence_event_ids.length, lang)} events)</summary>
      <ul class="mt-2 space-y-1 text-ink-2">
        ${rows.map((e) => html`<li key=${e.event_id} data-event-id=${e.event_id} class="flex min-w-0 gap-2">
          <code class="shrink-0 text-[11px] text-ink-3">${e.event_id}</code><span class="truncate">${e.event_type} · ${e.outcome}</span></li>`)}
      </ul>
    </details>
  </article>`;
}

export function PlayersPage({ data }) {
  const { lang } = useT();
  const players = data.ui.players;
  const teams = [...new Set(players.map((p) => p.team))].sort();
  const [team, setTeam] = React.useState("all");
  const [sort, setSort] = React.useState("involvement");
  const [all, setAll] = React.useState(false);
  const flagged = players.flatMap((p) => p.checks.filter((c) => c.fired).map((c) => ({ p, c })));
  flagged.sort((a, b) => (a.c.rule === "wide_forward_passes" ? -1 : 0) - (b.c.rule === "wide_forward_passes" ? -1 : 0)
    || b.p.chances - a.p.chances);
  const key = SORTS[sort].key;
  const rows = players.filter((p) => team === "all" || p.team === team)
    .slice().sort((a, b) => (b[key] || 0) - (a[key] || 0) || a.name.localeCompare(b.name));
  const shown = all ? rows : rows.slice(0, 15);
  const fired = new Set(flagged.map((f) => f.p.id));
  const th = "px-3 py-2 text-left font-semibold whitespace-nowrap";
  const td = "num px-3 py-1.5 whitespace-nowrap";
  return html`<div class="stack-gap flex flex-col" data-page="players">
    <header>
      <h1 class="text-[26px] font-bold tracking-tight sm:text-[30px]">Player Deck</h1>
      <p class="mt-1 max-w-3xl text-[14px] leading-relaxed text-ink-2">Involvement, pass quality and chances created, from event
        data only, season totals. The data has no minutes played, so these are totals, not rates per minute, and no tracking, so there are no
        distance, speed or fitness figures.</p>
    </header>
    <${Panel} id="context" title="Context the Verifier adds"
        subtitle="Player claims that are true but would mislead on their own. The Verifier holds the plain stat back until the sentence carries the context.">
      <div class="stack-gap grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
        ${flagged.map(({ p, c }) => html`<${ContextCard} key=${`${p.id}-${c.rule}`} data=${data} p=${p} c=${c} />`)}
      </div>
    <//>
    <${Panel} id="deck" title="All players"
        actions=${html`<span class="num whitespace-nowrap text-[12px] text-ink-3">${num(rows.length, lang)} players</span>`}>
      <div class="flex flex-wrap items-center gap-3">
        <label class="flex items-center gap-2 text-[12.5px] font-semibold text-ink-3">Team
          <select id="player-team" value=${team} onChange=${(e) => setTeam(e.target.value)}
              class="h-9 rounded-xl border border-line bg-surface-2 px-3 text-[13.5px] font-semibold text-ink">
            <option value="all">All</option>${teams.map((t) => html`<option key=${t} value=${t}>${t}</option>`)}</select></label>
        <${Segmented} label="Sort by" name="sort" value=${sort} onChange=${setSort}
          options=${Object.entries(SORTS).map(([value, s]) => ({ value, label: s.label }))} />
      </div>
      <div class="mt-4 overflow-x-auto rounded-xl border border-line">
        <table class="w-full min-w-[860px] border-collapse text-[13px]" data-table="players">
          <thead class="bg-surface-2 text-ink-3"><tr>
            <th class=${th}>Player</th><th class=${th}>Team</th><th class=${th}>Pos</th>
            <th class=${th} title="Actions credited to the player: on-ball actions, duels, pressures, fouls, saves">Involvement</th>
            <th class=${th}>Team share</th><th class=${th}>Passes</th><th class=${th}>Completed</th>
            <th class=${th}>Forward</th><th class=${th}>Wide</th>
            <th class=${th} title="Share of forward passes into high-threat central cells, against the league rate">Pass quality</th>
            <th class=${th}>Chances</th><th class=${th}>Open play</th><th class=${th}>Set piece</th><th class=${th}>Verifier</th></tr></thead>
          <tbody>${shown.map((p) => html`<tr key=${p.id} data-player=${p.id} class="border-t border-line">
            <td class="px-3 py-1.5 font-semibold whitespace-nowrap">${p.name}</td><td class="px-3 py-1.5">${p.team}</td>
            <td class="px-3 py-1.5 text-ink-3">${p.position}</td><td class=${cx(td, "font-semibold")}>${num(p.involvement, lang)}</td>
            <td class=${td}>${p.team_share == null ? "–" : `${num(p.team_share, lang)}%`}</td><td class=${td}>${num(p.passes, lang)}</td>
            <td class=${td}>${p.pass_completion == null ? "–" : `${num(p.pass_completion, lang)}%`}</td>
            <td class=${td}>${num(p.forward_passes, lang)}</td><td class=${td}>${p.wide_share == null ? "–" : `${num(p.wide_share, lang)}%`}</td>
            <td class=${td}>${p.pass_quality_ratio == null ? "–" : `${num(p.pass_quality_ratio, lang)}×`}</td>
            <td class=${td}>${num(p.chances, lang)}</td><td class=${td}>${num(p.chances_open_play, lang)}</td><td class=${td}>${num(p.chances_set_piece, lang)}</td>
            <td class="px-3 py-1.5">${fired.has(p.id) ? html`<${Chip} className="border-revise/40 text-revise">context added<//>` : html`<span class="text-ink-3">—</span>`}</td>
          </tr>`)}</tbody>
        </table>
      </div>
      ${rows.length > 15 && html`<button type="button" onClick=${() => setAll(!all)} id="players-more"
          class="mt-3 rounded-full border border-line px-3.5 py-1.5 text-[13px] font-semibold text-ink-2 hover:text-ink">
        ${all ? "Show fewer" : "Show all players"}</button>`}
    <//>
  </div>`;
}
