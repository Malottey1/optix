/* Optix dashboard: plays a match on a clock and shows the verified insight stream.
 *
 * Data (served from the repo root, e.g. `python -m http.server` then /app/):
 *   out/insights.jsonl   timed insights (contracts/insight.schema.json)
 *   out/claims.jsonl     every verification attempt (blocked ones too) for the evidence drawer
 *   out/timeline.json    teams, players, goals, per-minute momentum (computed by engine/)
 *   data/showcase/events.csv  event rows for the evidence table
 * The page computes no statistic: every number shown comes from those files.
 */
(() => {
  "use strict";

  const BASE = "../";
  const FILES = {
    insights: "out/insights.jsonl",
    claims: "out/claims.jsonl",
    timeline: "out/timeline.json",
    events: "data/showcase/events.csv",
  };
  const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const NS = "http://www.w3.org/2000/svg";
  const PX = 105 / 100, PY = 68 / 100;            // data 0-100 -> pitch metres

  const UI = {
    en: { subtitle: "Verified match insights · synthetic data", play: "Play", pause: "Pause", speed: "Speed",
      casual: "Casual", analyst: "Analyst", language: "Language", focus: "Player focus", all_players: "All players",
      focus_pitch: "Focus Pitch", proxy: "Event locations only (no tracking). Every team attacks left to right.",
      momentum: "Momentum tug-of-war", perimeter: "Perimeter Lock", honest: "Standard vs honest stat",
      none_yet: "Nothing yet.", feed: "Live feed", evidence: "Evidence", verified: "Verified",
      with_context: "Verified · context", blocked: "Blocked", rewritten: "Rewritten after a block",
      show_evidence: "Evidence", attempts: "Verification attempts", events: "Evidence events",
      standard: "Standard stat", honest_label: "Honest read", reached_box: "reached the box",
      outside: "pass in the final third", entry: "box entry", level: "Level", insights: "insights",
      attempt: "Attempt", needs: "needs", strategy: "revision", time: "Time", player: "Player", type: "Type",
      from: "From", to: "To", outcome: "Outcome", metric: "Metric", value: "Value", scope: "Scope",
      confidence: "Confidence", baseline: "Baseline", season_points: "Season entries (from the claim's evidence)",
      sample: "Dots: pass end points from the claim's evidence sample.", attacking: "attacking →", momentum_now: "Momentum", pulling: "pulling" },
    es: { subtitle: "Datos del partido verificados · datos sintéticos", play: "Reproducir", pause: "Pausa", speed: "Velocidad",
      casual: "Casual", analyst: "Analista", language: "Idioma", focus: "Jugador", all_players: "Todos los jugadores",
      focus_pitch: "Campo en foco", proxy: "Solo ubicaciones de eventos (sin tracking). Todos los equipos atacan hacia la derecha.",
      momentum: "Tira y afloja del impulso", perimeter: "Cerrojo perimetral", honest: "Dato estándar vs dato honesto",
      none_yet: "Nada todavía.", feed: "En directo", evidence: "Evidencia", verified: "Verificado",
      with_context: "Verificado · contexto", blocked: "Bloqueado", rewritten: "Reescrito tras un bloqueo",
      show_evidence: "Evidencia", attempts: "Intentos de verificación", events: "Eventos de evidencia",
      standard: "Dato estándar", honest_label: "Lectura honesta", reached_box: "llegaron al área",
      outside: "pase en el último tercio", entry: "entrada al área", level: "Igualado", insights: "datos",
      attempt: "Intento", needs: "necesita", strategy: "revisión", time: "Min", player: "Jugador", type: "Tipo",
      from: "Desde", to: "Hasta", outcome: "Resultado", metric: "Métrica", value: "Valor", scope: "Ámbito",
      confidence: "Confianza", baseline: "Referencia", season_points: "Entradas de la temporada (evidencia de la afirmación)",
      sample: "Puntos: destino de los pases de la muestra de evidencia.", attacking: "ataca →", momentum_now: "Impulso", pulling: "empuja" },
    fr: { subtitle: "Analyses de match vérifiées · données synthétiques", play: "Lecture", pause: "Pause", speed: "Vitesse",
      casual: "Grand public", analyst: "Analyste", language: "Langue", focus: "Joueur", all_players: "Tous les joueurs",
      focus_pitch: "Terrain ciblé", proxy: "Positions des événements uniquement (pas de tracking). Chaque équipe attaque vers la droite.",
      momentum: "Bras de fer de la dynamique", perimeter: "Verrou du périmètre", honest: "Stat standard vs stat honnête",
      none_yet: "Rien pour l'instant.", feed: "En direct", evidence: "Preuves", verified: "Vérifié",
      with_context: "Vérifié · contexte", blocked: "Bloqué", rewritten: "Réécrit après un blocage",
      show_evidence: "Preuves", attempts: "Tentatives de vérification", events: "Événements de preuve",
      standard: "Stat standard", honest_label: "Lecture honnête", reached_box: "ont atteint la surface",
      outside: "passe dans le dernier tiers", entry: "entrée dans la surface", level: "Égalité", insights: "analyses",
      attempt: "Tentative", needs: "requiert", strategy: "révision", time: "Min", player: "Joueur", type: "Type",
      from: "De", to: "À", outcome: "Issue", metric: "Métrique", value: "Valeur", scope: "Portée",
      confidence: "Confiance", baseline: "Référence", season_points: "Entrées de la saison (preuves de l'affirmation)",
      sample: "Points : arrivée des passes de l'échantillon de preuves.", attacking: "attaque →", momentum_now: "Dynamique", pulling: "tire" },
  };
  const TYPE_LABEL = {
    en: { matchup_mismatch: "Matchup", perimeter_lock: "Perimeter lock", threat_pass: "Threat pass",
      momentum_shift: "Momentum", rhythm_wave: "Rhythm", volume_vs_value: "Volume vs value",
      set_piece_inflation: "Set pieces", player_focus: "Player", milestone: "Milestone", recap_line: "Recap" },
    es: { matchup_mismatch: "Duelo", perimeter_lock: "Cerrojo perimetral", threat_pass: "Pase de amenaza",
      momentum_shift: "Impulso", rhythm_wave: "Ritmo", volume_vs_value: "Volumen vs valor",
      set_piece_inflation: "Balón parado", player_focus: "Jugador", milestone: "Hito", recap_line: "Resumen" },
    fr: { matchup_mismatch: "Duel", perimeter_lock: "Verrou du périmètre", threat_pass: "Passe dangereuse",
      momentum_shift: "Dynamique", rhythm_wave: "Rythme", volume_vs_value: "Volume vs valeur",
      set_piece_inflation: "Coups de pied arrêtés", player_focus: "Joueur", milestone: "Jalon", recap_line: "Résumé" },
  };

  const state = { t: 0, playing: false, speed: 30, mode: "casual", lang: "en", player: "", selected: null,
    insights: [], attempts: {}, timeline: null, events: {}, lastFrame: 0, renderedKey: "" };
  const $ = (id) => document.getElementById(id);
  const tr = (k) => (UI[state.lang] || UI.en)[k] || UI.en[k] || k;
  const typeLabel = (t) => (TYPE_LABEL[state.lang] || TYPE_LABEL.en)[t] || t;
  // numbers are written as the stream wrote them, with the language's decimal separator
  const num = (v) => (["es", "fr"].includes(state.lang) ? String(v).replace(".", ",") : String(v));

  // ---------- loading ----------

  async function text(path) {
    const r = await fetch(BASE + path);
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.text();
  }
  const jsonl = (s) => s.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));

  function parseCSV(s) {
    const rows = [];
    let row = [], cur = "", q = false;
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (q) {
        if (c === '"' && s[i + 1] === '"') { cur += '"'; i++; }
        else if (c === '"') q = false;
        else cur += c;
      } else if (c === '"') q = true;
      else if (c === ",") { row.push(cur); cur = ""; }
      else if (c === "\n") { row.push(cur); rows.push(row); row = []; cur = ""; }
      else if (c !== "\r") cur += c;
    }
    if (cur || row.length) { row.push(cur); rows.push(row); }
    const head = rows.shift();
    return rows.map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
  }

  async function load() {
    const [ins, cl, tl, ev] = await Promise.all([text(FILES.insights), text(FILES.claims), text(FILES.timeline),
      text(FILES.events)]);
    state.insights = jsonl(ins).sort((a, b) => a.clock.start_sec - b.clock.start_sec);
    for (const a of jsonl(cl)) state.attempts[a.claim.claim_id] = a;
    state.timeline = JSON.parse(tl);
    for (const e of parseCSV(ev)) state.events[e.event_id] = e;
  }

  // ---------- helpers ----------

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const pad = (n) => String(n).padStart(2, "0");
  // elapsed clock -> football time: mm:ss inside each half, then 45+m / 90+m in stoppage time
  const mmss = (sec) => {
    sec = Math.floor(sec);
    const periods = (state.timeline && state.timeline.periods) || [];
    const half = [...periods].reverse().find((p) => sec >= p.start_sec);
    if (!half) return `${pad(Math.floor(sec / 60))}:${pad(sec % 60)}`;
    const base = (half.period - 1) * 2700, into = sec - half.start_sec;
    if (into <= 2700) return `${pad(Math.floor((base + into) / 60))}:${pad((base + into) % 60)}`;
    return `${(base + 2700) / 60}+${Math.ceil((into - 2700) / 60)}`;
  };
  const teamColor = (code) => (code === state.timeline.home.code ? "var(--home)" : "var(--away)");
  const playerName = (pid) => (state.timeline.players[pid] || {}).name || pid;
  const el = (tag, attrs = {}, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  };

  function chain(claimId) {
    // every attempt that led to this claim, oldest first
    const out = [];
    let a = state.attempts[claimId];
    while (a) { out.unshift(a); a = a.revision_of ? state.attempts[a.revision_of] : null; }
    return out;
  }

  function visible() {
    return state.insights.filter((i) => i.clock.start_sec <= state.t
      && (!state.player || (i.player_ids || []).includes(state.player)));
  }

  function display(ins) {
    const r = ins.text.rendered;
    return (r[state.lang] || r.en)[state.mode];
  }

  function statusBadge(status) {
    if (status === "published_with_context") return `<span class="badge warn"><span class="ic" aria-hidden="true">!</span>${esc(tr("with_context"))}</span>`;
    if (status === "blocked") return `<span class="badge crit"><span class="ic" aria-hidden="true">×</span>${esc(tr("blocked"))}</span>`;
    return `<span class="badge good"><span class="ic" aria-hidden="true">✓</span>${esc(tr("verified"))}</span>`;
  }

  // ---------- scoreboard, momentum ----------

  function renderScore() {
    const tl = state.timeline;
    const goals = tl.goals.filter((g) => g.clock_sec <= state.t);
    const g = goals[goals.length - 1];
    $("score").textContent = g ? `${g.score_home} – ${g.score_away}` : "0 – 0";
    $("clock").textContent = mmss(Math.floor(state.t));
    $("scrub").value = Math.floor(state.t);
  }

  function momentumAt(t) {
    let v = 0;
    for (const [s, m] of state.timeline.momentum) { if (s <= t) v = m; else break; }
    return v;
  }

  function renderMomentum() {
    const tl = state.timeline;
    const v = momentumAt(state.t);
    const fill = $("tug-fill");
    const w = Math.abs(v) / 2;                       // half the track = 100
    fill.style.width = `${w}%`;
    fill.style.left = v >= 0 ? `${50 - w}%` : "50%";
    fill.style.background = v >= 0 ? "var(--home)" : "var(--away)";
    const lead = v > 0 ? tl.home.code : v < 0 ? tl.away.code : null;
    $("tug-value").textContent = lead ? `${tr("momentum_now")}: ${lead} ${tr("pulling")} (${num(Math.abs(v))})` : `${tr("momentum_now")}: ${tr("level")} (0)`;

    const svg = $("spark");
    svg.replaceChildren();
    const pts = tl.momentum.filter(([s]) => s <= state.t);
    const X = (s) => (s / tl.duration_sec) * 300, Y = (m) => 30 - (m / 100) * 28;
    el("line", { x1: 0, x2: 300, y1: 30, y2: 30, stroke: "var(--border)", "stroke-width": 1, "vector-effect": "non-scaling-stroke" }, svg);
    if (pts.length > 1) {
      const d = pts.map(([s, m], i) => `${i ? "L" : "M"}${X(s).toFixed(1)},${Y(m).toFixed(1)}`).join("");
      // area above the midline in home colour, below in away colour (clip halves)
      const defs = el("defs", {}, svg);
      const cTop = el("clipPath", { id: "clip-top" }, defs); el("rect", { x: 0, y: 0, width: 300, height: 30 }, cTop);
      const cBot = el("clipPath", { id: "clip-bot" }, defs); el("rect", { x: 0, y: 30, width: 300, height: 30 }, cBot);
      const area = `${d}L${X(pts[pts.length - 1][0]).toFixed(1)},30L${X(pts[0][0]).toFixed(1)},30Z`;
      el("path", { d: area, fill: "var(--home)", opacity: 0.25, "clip-path": "url(#clip-top)" }, svg);
      el("path", { d: area, fill: "var(--away)", opacity: 0.25, "clip-path": "url(#clip-bot)" }, svg);
      el("path", { d, fill: "none", stroke: "var(--text-secondary)", "stroke-width": 2, "vector-effect": "non-scaling-stroke",
        "stroke-linejoin": "round" }, svg);
    }
    $("tug-home").textContent = tl.home.code;
    $("tug-away").textContent = tl.away.code;
  }

  function sparkHover(ev) {
    const tl = state.timeline;
    const svg = $("spark"), tip = $("spark-tip");
    const rect = svg.getBoundingClientRect();
    const frac = (ev.clientX - rect.left) / rect.width;
    const t = Math.min(state.t, Math.max(0, frac * tl.duration_sec));
    const pts = tl.momentum.filter(([s]) => s <= t);
    if (!pts.length) { tip.hidden = true; return; }
    const [s, m] = pts[pts.length - 1];
    const who = m > 0 ? tl.home.code : m < 0 ? tl.away.code : tr("level");
    tip.textContent = `${mmss(s)} · ${who} ${num(Math.abs(m))}`;
    tip.style.left = `${(s / tl.duration_sec) * rect.width}px`;
    tip.hidden = false;
  }

  // ---------- pitch ----------

  function drawPitchBase(svg) {
    svg.replaceChildren();
    const defs = el("defs", {}, svg);
    for (const [id, color] of [["arrow-home", "var(--home)"], ["arrow-away", "var(--away)"], ["arrow-muted", "var(--text-muted)"]]) {
      const m = el("marker", { id, viewBox: "0 0 10 10", refX: 8, refY: 5, markerWidth: 4, markerHeight: 4, orient: "auto-start-reverse" }, defs);
      el("path", { d: "M0,0 L10,5 L0,10 z", fill: color }, m);
    }
    const g = el("g", {}, svg);
    el("rect", { x: 0, y: 0, width: 105, height: 68, class: "pitch-line" }, g);
    el("line", { x1: 52.5, y1: 0, x2: 52.5, y2: 68, class: "pitch-line" }, g);
    el("circle", { cx: 52.5, cy: 34, r: 9.15, class: "pitch-line" }, g);
    for (const left of [true, false]) {
      const x0 = left ? 0 : 105, s = left ? 1 : -1;
      el("rect", { x: left ? 0 : 105 - 16.5, y: 22 * PY, width: 16.5, height: (78 - 22) * PY, class: "pitch-line" }, g);
      el("rect", { x: left ? 0 : 105 - 5.5, y: 24.85, width: 5.5, height: 18.3, class: "pitch-line" }, g);
      el("circle", { cx: x0 + s * 11, cy: 34, r: 0.4, fill: "var(--pitch-line)" }, g);
    }
    el("line", { x1: 66.7 * PX, y1: 0, x2: 66.7 * PX, y2: 68, class: "third-line" }, g);
    return g;
  }

  function pitchInsight() {
    if (state.selected) {
      const s = state.insights.find((i) => i.insight_id === state.selected);
      if (s && s.clock.start_sec <= state.t) return s;
    }
    const withPts = visible().filter((i) => (i.payload.points || []).length);
    return withPts[withPts.length - 1] || null;
  }

  function renderPitch() {
    const svg = $("pitch");
    const ins = pitchInsight();
    const key = `${ins ? ins.insight_id : ""}|${state.lang}`;
    if (key === state.renderedKey) return;
    state.renderedKey = key;
    drawPitchBase(svg);
    svg.setAttribute("viewBox", "-2 -2 109 72");
    if (!ins) { $("pitch-caption").textContent = ""; return; }
    const code = ins.teams.primary;
    const color = teamColor(code);
    const arrow = code === state.timeline.home.code ? "arrow-home" : "arrow-away";
    const p = ins.payload;
    const g = el("g", {}, svg);
    if (p.focus) {
      const f = p.focus;
      if (ins.insight_type === "matchup_mismatch") {
        el("rect", { x: 0, y: f.y_min * PY, width: 105, height: (f.y_max - f.y_min) * PY, fill: color, class: "lane-band" }, g);
      }
      el("rect", { x: f.x_min * PX, y: f.y_min * PY, width: (f.x_max - f.x_min) * PX, height: (f.y_max - f.y_min) * PY, class: "focus-box" }, g);
      // zoom to the focus with a margin, keeping the pitch in view
      const pad = 6;
      const x0 = Math.max(-2, f.x_min * PX - pad), x1 = Math.min(107, f.x_max * PX + pad);
      const y0 = Math.max(-2, f.y_min * PY - pad), y1 = Math.min(70, f.y_max * PY + pad);
      // keep the pitch's own aspect ratio: grow the short side around the focus centre
      const aspect = 109 / 72;
      let w = Math.max(x1 - x0, 40), h = Math.max(y1 - y0, 26);
      if (w / h < aspect) w = h * aspect; else h = w / aspect;
      const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      const vx = Math.min(Math.max(cx - w / 2, -2), 107 - w), vy = Math.min(Math.max(cy - h / 2, -2), 70 - h);
      svg.setAttribute("viewBox", `${vx} ${vy} ${w} ${h}`);
    }
    for (const pt of p.points || []) {
      // in a perimeter lock, plain final-third passes are the muted backdrop for the box entries
      const strong = !(ins.insight_type === "perimeter_lock" && pt.kind === "pass");
      const stroke = strong ? color : "var(--text-muted)";
      if (pt.x_end != null && pt.y_end != null && pt.kind !== "shot") {
        el("line", { x1: pt.x * PX, y1: pt.y * PY, x2: pt.x_end * PX, y2: pt.y_end * PY, stroke,
          class: "pt-line", "marker-end": `url(#${strong ? arrow : "arrow-muted"})`, opacity: strong ? 1 : 0.7 }, g);
      }
      el("circle", { cx: pt.x * PX, cy: pt.y * PY, r: strong ? 0.9 : 0.6, fill: stroke, class: "pt-dot" }, g);
      if (pt.kind === "threat_pass" && pt.value != null) {
        const t = el("text", { x: pt.x_end * PX + 1.2, y: pt.y_end * PY - 1.2, class: "pt-label" }, g);
        t.textContent = `+${num(pt.value)} xT`;
      }
    }
    const cap = ins.insight_type === "matchup_mismatch" ? tr("season_points") : `${code} ${tr("attacking")}`;
    $("pitch-caption").textContent = `${mmss(ins.clock.start_sec)} · ${typeLabel(ins.insight_type)} · ${cap}`;
  }

  // ---------- perimeter lock, standard vs honest ----------

  function latest(pred) {
    const v = visible().filter(pred);
    return v[v.length - 1] || null;
  }

  function renderPerimeter() {
    const box = $("perimeter");
    const ins = latest((i) => i.insight_type === "perimeter_lock");
    if (!ins) { box.className = "empty"; box.textContent = tr("none_yet"); return; }
    const m = ins.payload.metrics;
    const color = teamColor(ins.teams.primary);
    box.className = "";
    box.innerHTML = "";
    const svg = el("svg", { viewBox: `${60 * PX} -1 ${42 * PX} 70`, class: "lock-svg", role: "img",
      "aria-label": `${ins.teams.primary}: ${m.box_entries} / ${m.team_f3_passes}` }, box);
    el("rect", { x: 66.7 * PX, y: 0, width: 33.3 * PX, height: 68, fill: "none", stroke: "var(--pitch-line)", "stroke-width": 0.4 }, svg);
    el("rect", { x: 84 * PX, y: 22 * PY, width: 16 * PX, height: 56 * PY, fill: color, opacity: 0.12, stroke: color, "stroke-width": 0.5 }, svg);
    for (const pt of ins.payload.points || []) {
      const entry = pt.kind === "box_entry";
      el("circle", { cx: pt.x_end * PX, cy: pt.y_end * PY, r: entry ? 1.3 : 0.9, fill: entry ? color : "var(--text-muted)",
        opacity: entry ? 1 : 0.6, stroke: "var(--pitch)", "stroke-width": 0.3 }, svg);
    }
    const stat = document.createElement("div");
    stat.className = "lock-stat";
    stat.innerHTML = `<b>${esc(m.box_entries)}</b><span>/ ${esc(m.team_f3_passes)} ${esc(tr("reached_box"))} · ${esc(ins.teams.primary)} · ${esc(mmss(ins.clock.start_sec))}</span>`;
    const note = document.createElement("p");
    note.className = "small muted";
    note.textContent = tr("sample");
    box.appendChild(stat);
    const lg = document.createElement("div");
    lg.className = "legend";
    lg.innerHTML = `<span><i style="background:${color}"></i>${esc(tr("entry"))}</span><span><i style="background:var(--text-muted)"></i>${esc(tr("outside"))}</span>`;
    box.appendChild(lg);
    box.appendChild(note);
    const p = document.createElement("p");
    p.className = "small muted";
    p.textContent = display(ins);
    box.appendChild(p);
  }

  function renderHonest() {
    const box = $("honest");
    const ins = latest((i) => i.verification_status === "published_with_context" && i.context_chip);
    if (!ins) { box.className = "empty"; box.textContent = tr("none_yet"); return; }
    const chip = ins.context_chip;
    const a = state.attempts[ins.claim_id];
    const unit = a && a.claim.value.unit === "percent" ? "%" : "";
    box.className = "versus";
    box.innerHTML = `
      <div class="std"><div class="tag">${esc(tr("standard"))}</div>
        <div><span class="val">${esc(num(chip.standard_value))}${unit}</span> <span class="small">${esc(chip.standard_metric)}</span></div></div>
      <div class="hon"><div class="tag">${esc(tr("honest_label"))} · ${esc(mmss(ins.clock.start_sec))}</div>
        <p>${esc(display(ins))}</p><div class="small muted"><code>${esc(chip.note_key)}</code></div></div>`;
  }

  // ---------- feed ----------

  function card(ins) {
    const li = document.createElement("li");
    li.className = "card";
    li.dataset.id = ins.insight_id;
    if (ins.insight_id === state.selected) li.setAttribute("aria-current", "true");
    const hist = chain(ins.claim_id);
    const first = hist[0];
    const conf = ins.payload.confidence ? `<span class="badge">${esc(tr("confidence"))}: ${esc(ins.payload.confidence)}</span>` : "";
    let rewrite = "";
    if (hist.length > 1 && first.claim.verification.status === "blocked") {
      const v = first.claim.verification;
      const needs = Object.entries(v.revision_hint || {}).map(([r, ks]) => `${r} ${tr("needs")} ${ks.join(", ")}`).join("; ");
      rewrite = `<div class="rewrite"><b>${esc(tr("rewritten"))}</b>: <s>${esc(first.claim.template_key)}</s>
        → ${esc(ins.text.template_key)}<br><span class="small">${esc(needs || (v.rule_ids || []).join(", "))}</span></div>`;
    }
    const chip = ins.context_chip ? `<span class="chip">${esc(tr("standard"))}: ${esc(ins.context_chip.standard_metric)} ${esc(num(ins.context_chip.standard_value))} · <code>${esc(ins.context_chip.note_key)}</code></span>` : "";
    li.innerHTML = `
      <div class="card-top"><span class="time">${esc(mmss(ins.clock.start_sec))}</span>
        <span class="team-dot" style="background:${teamColor(ins.teams.primary)}" aria-hidden="true"></span><b>${esc(ins.teams.primary)}</b>
        <span class="badge">${esc(typeLabel(ins.insight_type))}</span>${statusBadge(ins.verification_status)}${conf}</div>
      <p>${esc(display(ins))}</p>${chip}${rewrite}
      <div class="card-actions"><button type="button" class="link" data-evidence="${esc(ins.insight_id)}">${esc(tr("show_evidence"))} (${ins.evidence_event_ids.length})</button></div>`;
    return li;
  }

  function renderFeed() {
    const v = visible();
    const key = `${v.length}|${state.mode}|${state.lang}|${state.player}|${state.selected}`;
    if (key === state.feedKey) return;
    state.feedKey = key;
    const feed = $("feed");
    feed.replaceChildren(...v.slice().reverse().map(card));
    $("feed-count").textContent = `${v.length} ${tr("insights")}`;
  }

  // ---------- evidence drawer ----------

  function openDrawer(id) {
    const ins = state.insights.find((i) => i.insight_id === id);
    if (!ins) return;
    const hist = chain(ins.claim_id);
    const final = hist[hist.length - 1] ? hist[hist.length - 1].claim : null;
    const body = $("drawer-body");
    let html = `<p>${esc(display(ins))}</p>`;
    if (final) {
      const val = final.value;
      html += `<dl class="kv">
        <dt>${esc(tr("metric"))}</dt><dd><code>${esc(final.metric)}</code></dd>
        <dt>${esc(tr("value"))}</dt><dd>${esc(num(val.amount))} ${esc(val.unit)}</dd>
        <dt>${esc(tr("scope"))}</dt><dd>${esc(final.scope)}${final.window ? ` · ${mmss(final.window.from_sec)}–${mmss(final.window.to_sec)}` : ""}</dd>
        ${val.baseline != null ? `<dt>${esc(tr("baseline"))}</dt><dd>${esc(num(val.baseline))}${val.baseline_source ? ` (${esc(val.baseline_source.kind)}, n=${esc(val.baseline_source.n)})` : ""}</dd>` : ""}
        ${val.confidence ? `<dt>${esc(tr("confidence"))}</dt><dd>${esc(val.confidence)}</dd>` : ""}
        ${Object.entries(final.supporting_values || {}).map(([k, x]) => `<dt>${esc(k)}</dt><dd>${esc(num(x))}</dd>`).join("")}
      </dl>`;
    }
    html += `<h2>${esc(tr("attempts"))}</h2><ol class="attempts">${hist.map((a) => {
      const v = a.claim.verification;
      const hint = v.revision_hint ? `<br>${Object.entries(v.revision_hint).map(([r, ks]) => `<code>${esc(r)}</code> ${esc(tr("needs"))} <code>${esc(ks.join(", "))}</code>`).join("; ")}` : "";
      return `<li><b>${esc(tr("attempt"))} ${esc(v.attempt)}</b> ${statusBadge(v.status)} <code>${esc(a.claim.template_key)}</code>
        ${a.strategy ? ` · ${esc(tr("strategy"))}: <code>${esc(a.strategy)}</code>` : ""}
        ${(v.rule_ids || []).length ? `<br>${v.rule_ids.map((r) => `<code>${esc(r)}</code>`).join(" ")}` : ""}
        ${v.context_note ? ` → <code>${esc(v.context_note)}</code>` : ""}${hint}</li>`;
    }).join("")}</ol>`;
    const rows = ins.evidence_event_ids.map((eid) => state.events[eid]).filter(Boolean);
    html += `<h2>${esc(tr("events"))}</h2>`;
    if (rows.length) {
      html += `<div class="table-scroll"><table class="ev"><thead><tr><th>${esc(tr("time"))}</th><th>${esc(tr("player"))}</th><th>${esc(tr("type"))}</th>
        <th>${esc(tr("from"))}</th><th>${esc(tr("to"))}</th><th>${esc(tr("outcome"))}</th></tr></thead><tbody>${rows.map((e) => `<tr>
        <td>${esc(mmss(+e.clock_sec))}</td><td>${esc(playerName(e.player_id))}${e.related_player_id ? ` → ${esc(playerName(e.related_player_id))}` : ""}</td><td>${esc(e.event_type)}</td>
        <td>${esc(e.x_start)}, ${esc(e.y_start)}</td><td>${e.x_end ? `${esc(e.x_end)}, ${esc(e.y_end)}` : "–"}</td><td>${esc(e.outcome)}</td></tr>`).join("")}</tbody></table></div>`;
    } else {
      const pts = ins.payload.points || [];
      html += `<p class="small muted">${esc(tr("season_points"))}</p><div class="table-scroll"><table class="ev"><thead><tr><th>ID</th><th>${esc(tr("from"))}</th><th>${esc(tr("to"))}</th></tr></thead><tbody>${pts.map((p) => `<tr>
        <td><code>${esc(p.event_id)}</code></td><td>${esc(p.x)}, ${esc(p.y)}</td><td>${esc(p.x_end)}, ${esc(p.y_end)}</td></tr>`).join("")}</tbody></table></div>`;
    }
    body.innerHTML = html;
    $("drawer").hidden = false;
    $("drawer").querySelector(".close").focus();
  }

  function closeDrawer() { $("drawer").hidden = true; }

  // ---------- chrome ----------

  function applyI18n() {
    document.documentElement.lang = state.lang;
    for (const n of document.querySelectorAll("[data-i18n]")) {
      if (n.classList.contains("empty") || n.id === "perimeter" || n.id === "honest") continue;
      n.textContent = tr(n.dataset.i18n);
    }
    $("play").querySelector("span").textContent = state.playing ? tr("pause") : tr("play");
    for (const b of document.querySelectorAll("[data-mode]")) b.setAttribute("aria-pressed", String(b.dataset.mode === state.mode));
    state.feedKey = ""; state.renderedKey = "";
  }

  function fillPlayers() {
    const sel = $("player");
    const ids = [...new Set(state.insights.flatMap((i) => i.player_ids || []))];
    ids.sort((a, b) => playerName(a).localeCompare(playerName(b)));
    for (const pid of ids) {
      const o = document.createElement("option");
      o.value = pid;
      o.textContent = `${playerName(pid)} (${(state.timeline.players[pid] || {}).team || ""})`;
      sel.appendChild(o);
    }
  }

  function render() {
    renderScore();
    renderMomentum();
    renderPitch();
    renderPerimeter();
    renderHonest();
    renderFeed();
  }

  function tick(now) {
    if (!state.playing) return;
    const dt = state.lastFrame ? (now - state.lastFrame) / 1000 : 0;
    state.lastFrame = now;
    state.t = Math.min(state.timeline.duration_sec, state.t + dt * state.speed);
    render();
    if (state.t >= state.timeline.duration_sec) { setPlaying(false); return; }
    requestAnimationFrame(tick);
  }

  function setPlaying(on) {
    state.playing = on;
    state.lastFrame = 0;
    $("play").setAttribute("aria-pressed", String(on));
    $("play").querySelector("span").textContent = on ? tr("pause") : tr("play");
    if (on) requestAnimationFrame(tick);
  }

  function bind() {
    $("play").addEventListener("click", () => {
      if (state.t >= state.timeline.duration_sec) state.t = 0;
      setPlaying(!state.playing);
    });
    $("speed").addEventListener("change", (e) => { state.speed = +e.target.value; });
    $("scrub").addEventListener("input", (e) => { state.t = +e.target.value; render(); });
    for (const b of document.querySelectorAll("[data-mode]")) {
      b.addEventListener("click", () => { state.mode = b.dataset.mode; applyI18n(); render(); });
    }
    $("lang").addEventListener("change", (e) => { state.lang = e.target.value; applyI18n(); render(); });
    $("player").addEventListener("change", (e) => { state.player = e.target.value; state.selected = null; render(); });
    $("feed").addEventListener("click", (e) => {
      const ev = e.target.closest("[data-evidence]");
      if (ev) { openDrawer(ev.dataset.evidence); return; }
      const c = e.target.closest(".card");
      if (c) { state.selected = c.dataset.id; render(); }
    });
    $("drawer").addEventListener("click", (e) => { if (e.target.closest("[data-close]")) closeDrawer(); });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });
    $("spark").addEventListener("mousemove", sparkHover);
    $("spark").addEventListener("mouseleave", () => { $("spark-tip").hidden = true; });
  }

  async function main() {
    try {
      await load();
    } catch (err) {
      document.querySelector(".layout").innerHTML = `<p class="panel">Could not load the stream (${esc(err.message)}).
        Run <code>python -m agents.run_match --match m_showcase --out out/insights.jsonl</code> and serve the repo root.</p>`;
      return;
    }
    const tl = state.timeline;
    $("home-code").textContent = tl.home.code;
    $("away-code").textContent = tl.away.code;
    $("home-code").title = tl.home.name;
    $("away-code").title = tl.away.name;
    $("scrub").max = tl.duration_sec;
    fillPlayers();
    // URL options (also used for screenshots): ?t=2760&mode=analyst&lang=es&player=NTG_07&select=ins_0012&drawer=1&play=1
    const q = new URLSearchParams(location.search);
    if (q.has("t")) state.t = Math.min(tl.duration_sec, Math.max(0, +q.get("t")));
    if (["analyst", "casual"].includes(q.get("mode"))) state.mode = q.get("mode");
    if (UI[q.get("lang")]) { state.lang = q.get("lang"); $("lang").value = state.lang; }
    if (q.get("player")) { state.player = q.get("player"); $("player").value = state.player; }
    if (q.get("select")) state.selected = q.get("select");
    if (q.get("theme")) document.documentElement.dataset.theme = q.get("theme");
    bind();
    applyI18n();
    render();
    if (q.get("drawer") && state.selected) openDrawer(state.selected);
    if (q.get("play") === "1" && !REDUCED) setPlaying(true);
    document.body.dataset.ready = "1";
  }

  main();
})();
