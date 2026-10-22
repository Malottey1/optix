// #/teams: every team's style fingerprint over the season and a head-to-head lane matchup. All
// numbers come from ui.json (engine/profiles.py, engine/style_labels.py, engine/matchup.py).
// Lanes are always named from the attacker's point of view; the defender's own name for the same
// strip of grass is the mirror (left and right swap), shown beside it.
import { useState } from "react";
import { Icon } from "../../components/icons";
import { BOX, FINAL_THIRD_X, LANE_EDGES, LANE_NAMES, MIRROR, PX, PY, PitchLines } from "../../components/pitch/Pitch";
import { Chip, StatusChip } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Panel } from "../../components/ui/card";
import { ScrollRegion } from "../../components/ui/scroll-region";
import { Empty } from "../../components/ui/skeleton";
import { Tip } from "../../components/ui/tooltip";
import { useData } from "../../data/context";
import { cx } from "../../lib/cx";
import { num, pct, signed } from "../../lib/format";
import { useT } from "../../lib/i18n";
import type { HeadToHead as H2H, Lang, StyleLabel, TeamProfile } from "../../types/ui";
import { textOf } from "../live/shared";

const LABEL_NAME: Record<string, string> = {
  tempo: "Tempo",
  press: "Press",
  directness: "Passing",
  territory: "Territory",
  counter: "Counters",
};
const UNIT: Record<string, string> = { tempo: " s per pass" };

function LabelChip({ team, l, lang }: { team: TeamProfile; l: StyleLabel; lang: Lang }) {
  const typical = l.direction === "typical";
  const unit = l.unit || UNIT[l.id] || "";
  return (
    <Tip
      content={
        <span className="block">
          <span className="block font-semibold">{l.label}</span>
          <span className="mt-1 block text-ink-2">{l.rule}</span>
          <span className="num mt-2 block">
            {team.code} {num(l.value, lang)}
            {unit} · league {num(l.league, lang)}
            {unit}
            {l.interval && (
              <>
                {" "}
                · 95% interval {num(l.interval[0], lang)}–{num(l.interval[1], lang)}
              </>
            )}{" "}
            · n {num(l.n, lang)} · confidence {l.confidence}
          </span>
        </span>
      }
    >
      <button
        type="button"
        data-label={l.id}
        data-direction={l.direction}
        className={cx(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-semibold hover:border-line-strong",
          typical ? "border-line bg-surface-1 text-ink-3" : "border-muted/40 bg-muted-soft text-ink",
        )}
      >
        <span className="font-medium text-ink-3">{LABEL_NAME[l.id] ?? l.id}</span>
        {typical ? "typical" : l.label}
        <Icon name="info" className="h-3.5 w-3.5 text-ink-3" />
      </button>
    </Tip>
  );
}

/** One row per lane: a diverging bar of the lift over the league (pp), the team's value, the lane. */
function LaneLift({
  rows,
  label,
  id,
  highlight,
  color,
}: {
  rows: { lane: string; value: number | null; league: number | null; effect: number | null; n: number }[];
  label: string;
  id: string;
  highlight?: string | null;
  color: string;
}) {
  const { lang } = useT();
  const max = Math.max(5, ...rows.map((r) => Math.abs(r.effect ?? 0)));
  return (
    <table className="w-full border-collapse text-[12.5px]" data-chart={id}>
      <caption className="sr-only">{label}</caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Lane</th>
          <th scope="col">Lift over the league, percentage points</th>
          <th scope="col">Share</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const e = r.effect ?? 0;
          const w = (Math.abs(e) / max) * 50;
          const hi = r.lane === highlight;
          return (
            <tr key={r.lane} data-lane={r.lane} className={cx(hi && "text-ink")}>
              <th scope="row" className={cx("w-[38%] py-1 pr-2 text-left font-medium", hi ? "text-ink" : "text-ink-2")}>
                {LANE_NAMES[r.lane]}
              </th>
              <td className="py-1">
                <svg viewBox="0 0 100 10" preserveAspectRatio="none" className="block h-2.5 w-full" aria-hidden="true">
                  <rect x="0" y="0" width="100" height="10" rx="2" fill="var(--surface-3)" />
                  <rect
                    data-lane={r.lane}
                    data-value={r.effect ?? undefined}
                    x={e >= 0 ? 50 : 50 - w}
                    y="1"
                    width={w}
                    height="8"
                    rx="1.5"
                    fill={e >= 0 ? color : "var(--ink-3)"}
                    opacity={hi || e >= 0 ? 0.95 : 0.55}
                  />
                  <line
                    x1="50"
                    x2="50"
                    y1="0"
                    y2="10"
                    stroke="var(--ink-2)"
                    strokeWidth="1"
                    vectorEffect="non-scaling-stroke"
                  />
                </svg>
              </td>
              <td className="num w-[5.4rem] py-1 pl-2 text-right">
                <span className={cx("font-semibold", hi ? "text-ink" : "text-ink-2")}>{pct(r.value, lang)}</span>{" "}
                <span className={cx("text-[11.5px]", e > 0 ? "text-ink-2" : "text-ink-3")}>
                  {signed(r.effect, lang)}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function TeamCard({ team, lanes }: { team: TeamProfile; lanes: string[] }) {
  const { lang } = useT();
  const top = lanes.reduce(
    (a, l) => ((team.entry_lanes[l]?.effect ?? -99) > (team.entry_lanes[a]?.effect ?? -99) ? l : a),
    lanes[0]!,
  );
  const e = team.entry_lanes[top]!;
  const soft = team.soft_lane;
  return (
    <article
      data-team={team.code}
      className="flex min-w-0 flex-col rounded-2xl border border-line bg-surface-1 pad elev-1"
    >
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="display text-[30px] font-bold leading-none text-ink">{team.code}</h3>
          <p className="mt-1 truncate text-[13px] text-ink-3">{team.name}</p>
        </div>
        <span className="shrink-0 rounded-full bg-surface-3 px-2 py-0.5 text-[11.5px] text-ink-2">
          <span className="num font-semibold">{num(team.matches, lang)}</span> matches
        </span>
      </header>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {team.labels.map((l) => (
          <LabelChip key={l.id} team={team} l={l} lang={lang} />
        ))}
      </div>
      <div className="mt-4 border-t border-line pt-3">
        <p className="eyebrow">Attacks from</p>
        <p className="mt-1 text-[13px] text-ink-2">
          <b className="text-ink">{LANE_NAMES[top]}</b>: <span className="num">{pct(e.share, lang)}</span> of
          final-third entries (league <span className="num">{pct(e.league, lang)}</span>)
        </p>
        <div className="mt-2">
          <LaneLift
            id={`attack-${team.code}`}
            label={`${team.code}: share of final-third entries by lane, and the lift over the league in percentage points`}
            color="var(--accent)"
            highlight={top}
            rows={lanes.map((l) => ({ lane: l, ...team.entry_lanes[l]!, value: team.entry_lanes[l]!.share }))}
          />
        </div>
      </div>
      <div className="mt-3 border-t border-line pt-3">
        <p className="eyebrow">Concedes</p>
        {soft ? (
          <p className="mt-1 text-[13px] leading-snug text-ink-2" data-soft-lane={soft.lane}>
            Soft lane: <b className="text-revise">{LANE_NAMES[soft.lane]}</b> (attacker's view; {team.code}'s own{" "}
            {LANE_NAMES[MIRROR[soft.lane]!]!.toLowerCase()}). Opponents complete{" "}
            <span className="num">{pct(soft.rate, lang)}</span> of entries there (league{" "}
            <span className="num">{pct(soft.league, lang)}</span>, n{" "}
            <span className="num">{num(soft.attempted, lang)}</span>, {soft.confidence} confidence).
          </p>
        ) : (
          <p className="mt-1 text-[13px] text-ink-3">No lane passes the soft-lane rule.</p>
        )}
        <div className="mt-2">
          <LaneLift
            id={`concede-${team.code}`}
            label={`${team.code}: completion of entries conceded by lane (attacker's view), and the lift over the league in percentage points`}
            color="var(--revise)"
            highlight={soft?.lane}
            rows={lanes.map((l) => ({
              lane: l,
              value: team.completion_conceded[l]!.rate,
              league: team.completion_conceded[l]!.league,
              effect: team.completion_conceded[l]!.effect,
              n: team.completion_conceded[l]!.attempted,
            }))}
          />
        </div>
      </div>
    </article>
  );
}

/** The attacker's frame: attacking left to right, the attacker's left flank on top. Labels are
 * HTML laid over the lanes so they stay readable on a phone. */
function MatchupPitch({ att, dfn, lanes, h }: { att: string; dfn: string; lanes: string[]; h: H2H }) {
  const { lang } = useT();
  const vb = { x: -2, y: -2, w: 109, h: 72 };
  const topPct = (y: number) => `${((y * PY - vb.y) / vb.h) * 100}%`;
  const hPct = (y0: number, y1: number) => `${(((y1 - y0) * PY) / vb.h) * 100}%`;
  return (
    <figure className="m-0">
      <div className="relative">
        <svg
          viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
          className="block h-auto w-full rounded-xl"
          role="img"
          data-chart="h2h-pitch"
          data-team={att}
          aria-label={`${att} attacking ${dfn}, left to right: ${h.top ? `top lane ${LANE_NAMES[h.top]}` : "no lane mismatch"}`}
        >
          <PitchLines thirds />
          {lanes.map((l, i) => {
            const v = h.lanes[l]!;
            const y0 = LANE_EDGES[i]! * PY;
            const y1 = LANE_EDGES[i + 1]! * PY;
            const top = l === h.top;
            const both = (v.attack_pp ?? 0) > 0 && (v.completion_pp ?? 0) > 0;
            return (
              <g key={l} data-lane={l} data-mismatch={v.mismatch_pp ?? undefined} data-top={String(top)}>
                <rect
                  x={FINAL_THIRD_X * PX}
                  y={y0}
                  width={(100 - FINAL_THIRD_X) * PX}
                  height={y1 - y0}
                  fill={top ? "var(--revise)" : both ? "var(--accent)" : "transparent"}
                  opacity={top ? 0.3 : both ? 0.12 : 0}
                />
                {i > 0 && (
                  <line
                    x1="0"
                    x2="105"
                    y1={y0}
                    y2={y0}
                    stroke="var(--pitch-faint)"
                    strokeWidth="0.3"
                    strokeDasharray="0.8 0.8"
                  />
                )}
                {top && (
                  <path
                    d={`M${40 * PX},${(y0 + y1) / 2} L${(FINAL_THIRD_X + 22) * PX},${(y0 + y1) / 2}`}
                    stroke="var(--revise)"
                    strokeWidth="0.8"
                    markerEnd="url(#h2h-arrow)"
                  />
                )}
              </g>
            );
          })}
          <defs>
            <marker id="h2h-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--revise)" />
            </marker>
          </defs>
          <rect
            x={BOX.x * PX}
            y={BOX.y0 * PY}
            width={(100 - BOX.x) * PX}
            height={(BOX.y1 - BOX.y0) * PY}
            fill="none"
            stroke="var(--pitch-line)"
            strokeWidth="0.35"
          />
        </svg>
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          {lanes.map((l, i) => {
            const v = h.lanes[l]!;
            const top = l === h.top;
            return (
              <div
                key={l}
                className="absolute inset-x-[3%] flex items-center justify-between gap-2"
                style={{ top: topPct(LANE_EDGES[i]!), height: hPct(LANE_EDGES[i]!, LANE_EDGES[i + 1]!) }}
              >
                <span className="truncate rounded-md bg-bg/70 px-1.5 py-0.5 text-[11.5px] font-medium text-ink-2 sm:text-[12.5px]">
                  {LANE_NAMES[l]}
                </span>
                <span
                  className={cx(
                    "display shrink-0 rounded-md bg-bg/70 px-1.5 py-0.5 text-[15px] font-bold leading-none sm:text-[18px]",
                    top ? "text-revise" : "text-ink",
                  )}
                >
                  {signed(v.mismatch_pp, lang)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <figcaption className="mt-2 text-[12.5px] leading-relaxed text-ink-3">
        {att} attacking left to right; {att}'s left flank is the top edge. Figure per lane: mismatch in percentage
        points ({att}'s lift in entries + {dfn}'s lift in completion conceded); a lane is shaded only when both lifts
        are positive.
      </figcaption>
    </figure>
  );
}

function HeadToHead() {
  const m = useData();
  const { lang } = useT();
  const T = m.ui.teams;
  const codes = T.teams.map((t) => t.code);
  const showcase = T.head_to_head.find(
    (x) => x.attacker === m.timeline.home.code && x.defender === m.timeline.away.code,
  );
  const first = showcase ?? T.head_to_head.find((x) => x.claim && x.claim.status !== "blocked") ?? T.head_to_head[0]!;
  const [att, setAtt] = useState(first.attacker);
  const [dfn, setDfn] = useState(first.defender);
  const h = T.head_to_head.find((x) => x.attacker === att && x.defender === dfn)!;
  const pick = (which: "att" | "dfn", v: string) => {
    if (which === "att") {
      if (v === dfn) setDfn(att);
      setAtt(v);
    } else {
      if (v === att) setAtt(dfn);
      setDfn(v);
    }
  };
  const sel = "h-10 rounded-xl border border-line bg-surface-2 px-3 text-[14px] font-semibold text-ink";
  const text = h.claim?.text ? { en: h.claim.text.en, [lang]: h.claim.text[lang] } : null;
  return (
    <Panel
      id="h2h"
      title="Head to head: lane mismatch"
      subtitle="Where the attacker's habit meets the defender's soft spot, over the season. Lanes are named from the attacker's point of view: the defender's own right flank is the attacker's left flank, so both sides of a lane describe the same strip of grass."
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12px] font-semibold text-ink-3">
          Attacker
          <select id="h2h-attacker" className={sel} value={att} onChange={(e) => pick("att", e.target.value)}>
            {codes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <Button
          size="icon"
          aria-label="Swap attacker and defender"
          onClick={() => (setAtt(dfn), setDfn(att))}
          className="mb-0.5"
        >
          <Icon name="swap" className="h-[18px] w-[18px]" />
        </Button>
        <label className="flex flex-col gap-1 text-[12px] font-semibold text-ink-3">
          Defender
          <select id="h2h-defender" className={sel} value={dfn} onChange={(e) => pick("dfn", e.target.value)}>
            {codes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {h.claim ? (
            <StatusChip
              status={
                h.claim.status === "blocked"
                  ? "blocked"
                  : h.claim.status === "published_with_context"
                    ? "published_with_context"
                    : "published"
              }
              label={`Verifier: ${h.claim.status === "published" ? "passed" : h.claim.status.replace(/_/g, " ")}`}
            />
          ) : (
            <Chip>No claim: no lane mismatch</Chip>
          )}
          <Chip>
            n <span className="num">{num(h.n_attack, lang)}</span> entries ·{" "}
            <span className="num">{num(h.n_concede, lang)}</span> conceded
          </Chip>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <MatchupPitch att={att} dfn={dfn} lanes={T.lanes} h={h} />
        <div className="min-w-0">
          {text ? (
            <div className="rounded-xl border border-line bg-surface-2 px-4 py-3.5">
              <p className="eyebrow">Verified sentence</p>
              <p
                className="mt-1.5 text-[16px] font-semibold leading-snug text-ink"
                data-role="matchup-sentence"
                lang={lang}
              >
                {textOf(text, lang, "casual")}
              </p>
              <p className="mt-2 text-[13px] leading-relaxed text-ink-2" lang={lang}>
                {textOf(text, lang, "analyst")}
              </p>
              <p className="mt-2 text-[12px] text-ink-3">
                Confidence {h.claim!.confidence} ·{" "}
                <span className="num">{num(h.claim!.evidence_event_ids.length, lang)}</span> evidence events
              </p>
            </div>
          ) : (
            <Empty>
              No lane where {att}'s attacking habit and {dfn}'s soft spot line up, so no claim was made.
            </Empty>
          )}
          <ScrollRegion label={`Lanes: ${att} attacking ${dfn}`} className="mt-4">
            <table className="w-full min-w-[520px] border-collapse text-[12.5px]" data-table="h2h">
              <thead className="bg-surface-2 text-left text-ink-3">
                <tr>
                  <th scope="col" className="px-3 py-2 font-semibold">
                    Lane ({att}'s view)
                  </th>
                  <th scope="col" className="px-3 py-2 font-semibold">
                    {dfn} calls it
                  </th>
                  <th scope="col" className="px-3 py-2 font-semibold">
                    {att} share
                  </th>
                  <th scope="col" className="px-3 py-2 font-semibold">
                    {dfn} completion conceded
                  </th>
                  <th scope="col" className="px-3 py-2 font-semibold">
                    Mismatch
                  </th>
                </tr>
              </thead>
              <tbody>
                {T.lanes.map((l) => {
                  const v = h.lanes[l]!;
                  return (
                    <tr key={l} data-lane={l} className={cx("border-t border-line", l === h.top && "bg-revise-soft")}>
                      <th scope="row" className="px-3 py-1.5 text-left font-semibold">
                        {LANE_NAMES[l]}
                      </th>
                      <td className="px-3 py-1.5 text-ink-3">{LANE_NAMES[MIRROR[l]!]}</td>
                      <td className="num px-3 py-1.5">
                        {pct(v.attack_share, lang)} <span className="text-ink-3">vs {pct(v.league_share, lang)}</span>
                      </td>
                      <td className="num px-3 py-1.5">
                        {pct(v.completion, lang)}{" "}
                        <span className="text-ink-3">vs {pct(v.league_completion, lang)}</span>
                      </td>
                      <td className={cx("num px-3 py-1.5 font-semibold", l === h.top && "text-revise")}>
                        {signed(v.mismatch_pp, lang)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollRegion>
          <p className="mt-2 text-[12px] text-ink-3">"vs" figures are the league rate for that lane.</p>
        </div>
      </div>
    </Panel>
  );
}

export default function TeamsPage() {
  const m = useData();
  const { lang } = useT();
  const T = m.ui.teams;
  return (
    <div className="flex flex-col gap-flow" data-page="teams">
      <header className="max-w-3xl">
        <p className="eyebrow">Season · {T.dataset} data</p>
        <h1 className="mt-1 text-[28px] font-bold tracking-tight text-ink sm:text-[34px]">Team Board</h1>
        <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">
          Style fingerprints from the season's event data (<span className="num">{num(T.matches, lang)}</span> matches,{" "}
          <span className="num">{num(T.teams.length, lang)}</span> fictional teams). Every label is derived from the
          team's metrics by a fixed rule; hover or focus a label to read the rule and the numbers behind it. Bars show
          the lift over the league average in percentage points: right of the centre line is above the league.
        </p>
      </header>
      <HeadToHead />
      <div className="grid grid-cols-1 gap-flow md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
        {T.teams.map((t) => (
          <TeamCard key={t.code} team={t} lanes={T.lanes} />
        ))}
      </div>
    </div>
  );
}
