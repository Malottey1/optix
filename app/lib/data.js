// Loads the pre-generated showcase stream and engine outputs (written by agents.run_match):
//   out/insights.jsonl  timed insights (contracts/insight.schema.json)
//   out/claims.jsonl    every verification attempt, blocked ones too
//   out/timeline.json   teams, players, goals, periods, per-minute momentum
//   out/ui.json         teams, players, ledger, rewrites, rule reasons, evidence rows, reports
// All paths are relative to the page (served from the repo root at /app/).
const BASE = "../out/";
const FILES = { insights: "insights.jsonl", claims: "claims.jsonl", timeline: "timeline.json", ui: "ui.json" };

async function text(name) {
  const r = await fetch(BASE + name);
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
  return r.text();
}

const jsonl = (s) => s.split("\n").filter((l) => l.trim()).map((l) => JSON.parse(l));

export async function loadAll() {
  const [ins, cl, tl, ui] = await Promise.all([text(FILES.insights), text(FILES.claims), text(FILES.timeline), text(FILES.ui)]);
  const insights = jsonl(ins).sort((a, b) => a.clock.start_sec - b.clock.start_sec);
  const attempts = {};
  for (const a of jsonl(cl)) attempts[a.claim.claim_id] = a;
  const timeline = JSON.parse(tl);
  const data = JSON.parse(ui);
  const chain = (claimId) => {
    const out = [];
    let a = attempts[claimId];
    while (a) {
      out.unshift(a);
      a = a.revision_of ? attempts[a.revision_of] : null;
    }
    return out;
  };
  const byId = Object.fromEntries(insights.map((i) => [i.insight_id, i]));
  const startTimes = insights.map((i) => i.clock.start_sec);
  // the latest track entry at or before t (binary search; the track is in clock order)
  const track = data.track || [];
  const ballAt = (t) => {
    let lo = 0, hi = track.length - 1, best = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (track[mid][0] <= t) { best = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return best < 0 ? null : track[best];
  };
  const visibleCount = (t) => {
    let n = 0;
    while (n < startTimes.length && startTimes[n] <= t) n++;
    return n;
  };
  return { insights, attempts, timeline, ui: data, chain, byId, ballAt, visibleCount };
}
