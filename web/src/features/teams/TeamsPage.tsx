// DEPRECATED (information architecture rebuild): no route renders this page any more; #/teams is
// TeamGrid and #/teams/:code is TeamBoard. Kept for reference, not deleted.
// #/teams: every team's style fingerprint over the season and a head-to-head lane matchup. All
// numbers come from ui.json (engine/profiles.py, engine/style_labels.py, engine/matchup.py).
// Lanes are always named from the attacker's point of view; the defender's own name for the same
// strip of grass is the mirror (left and right swap), shown beside it.
import { TeamBadge } from "../../components/brand/TeamBadge";
import { useState } from "react";
import { Glyph } from "../../components/icons";
import { attackLaneIcon, Icon, laneIcon, patternIcon, styleLabelIcon } from "../../icons";
import { MismatchCrosshairs } from "../../components/viz/MismatchCrosshairs";
import { StateSwaps } from "../../components/viz/StateSwaps";
import { ZoneShift } from "../../components/viz/ZoneShift";
import { LANE_NAMES, MIRROR } from "../../components/pitch/Pitch";
import { Chip, StatusChip } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Panel } from "../../components/ui/card";
import { ScrollRegion } from "../../components/ui/scroll-region";
import { Empty } from "../../components/ui/skeleton";
import { Tip } from "../../components/ui/tooltip";
import { useData } from "../../data/context";
import { cx } from "../../lib/cx";
import { num, pct, signed } from "../../lib/format";
import { patternLabel, useT } from "../../lib/i18n";
import type { Lang, StyleLabel, TeamProfile } from "../../types/ui";
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
        <Icon name={styleLabelIcon(l.id, l.direction)} size={14} className={typical ? "text-ink-3" : "text-ink-2"} />
        <span className="font-medium text-ink-3">{LABEL_NAME[l.id] ?? l.id}</span>
        {typical ? "typical" : l.label}
        <Icon name="verdict-context" size={14} className="text-ink-3" />
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
                <span className="inline-flex items-center gap-1.5">
                  <Icon name={laneIcon(r.lane)} size={16} className={hi ? "text-ink" : "text-ink-3"} />
                  {LANE_NAMES[r.lane]}
                </span>
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

/** Home and away shirts (illustrative artwork, from the kit sheet), small and lazy-loaded. */
function Kits({ code, name }: { code: string; name: string }) {
  const c = code.toLowerCase();
  return (
    <figure className="mt-3 flex items-end gap-3" data-kits={code}>
      {(["home", "away"] as const).map((k) => (
        <span key={k} className="flex flex-col items-center gap-1">
          <img
            src={`./brand/teams/kit-${c}-${k}.webp`}
            width={64}
            height={72}
            loading="lazy"
            decoding="async"
            alt={`${name} ${k} shirt`}
            className="h-[72px] w-16 object-contain"
          />
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{k}</span>
        </span>
      ))}
      <figcaption className="ml-1 self-center text-[11.5px] leading-snug text-ink-3">
        Kits: illustrative artwork for a fictional club.
      </figcaption>
    </figure>
  );
}

/** The families found in a large share of the team's season matches, well above the other teams
 * (agents/dashboard_data.py, patterns.signature; the rule is in patterns.signature_rule). */
function SignaturePatterns({ code }: { code: string }) {
  const m = useData();
  const { lang } = useT();
  const rows = m.ui.patterns?.signature[code];
  if (!rows) return null;
  return (
    <div className="mt-3 border-t border-line pt-3" data-signature-patterns={code}>
      <p className="eyebrow">Signature patterns</p>
      {rows.length ? (
        <ul className="mt-1.5 space-y-1 text-[13px] text-ink-2">
          {rows.map((r) => (
            <li
              key={r.family}
              data-family={r.family}
              className="grid grid-cols-[16px_minmax(0,1fr)_minmax(0,1fr)] items-start gap-x-1.5"
            >
              <Icon name={patternIcon(r.family)} size={16} className="mt-0.5 shrink-0 text-ink-2" />
              <b className="text-ink">{patternLabel(r.family, lang)}</b>
              <span className="text-ink-3">
                <span className="num">{pct(r.share, lang)}</span> of matches (others{" "}
                <span className="num">{pct(r.others_share, lang)}</span>)
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-[13px] text-ink-3">None passes the signature rule this season.</p>
      )}
    </div>
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
        <div className="flex min-w-0 items-center gap-3">
          <TeamBadge code={team.code} size={56} named />
          <span
            aria-hidden="true"
            className="h-10 w-[3px] shrink-0 rounded-full"
            style={{ background: `var(--team-${team.code.toLowerCase()})` }}
          />
          <div className="min-w-0">
            <h3 className="display text-[30px] font-bold leading-none text-ink">{team.code}</h3>
            <p className="mt-1 truncate text-[13px] text-ink-3">{team.name}</p>
          </div>
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
      <Kits code={team.code} name={team.name} />
      <SignaturePatterns code={team.code} />
      <div className="mt-4 border-t border-line pt-3">
        <p className="eyebrow">Attacks from</p>
        <p className="mt-1 text-[13px] text-ink-2">
          <Icon name={attackLaneIcon(top)} size={16} className="mr-1 inline-block align-[-3px] text-ink-2" />
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
            Soft lane: <Icon name={laneIcon(soft.lane)} size={16} className="inline-block align-[-3px] text-ink-2" />{" "}
            <b className="text-revise">{LANE_NAMES[soft.lane]}</b> (attacker's view; {team.code}'s own{" "}
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

function HeadToHead() {
  const m = useData();
  const { lang, t: tr } = useT();
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
        <TeamBadge code={att} size={44} named className="mb-0.5" />
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
        <Button size="icon" aria-label={tr("swap_sides")} onClick={() => (setAtt(dfn), setDfn(att))} className="mb-0.5">
          <Glyph name="swap" className="h-[18px] w-[18px]" />
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
        <TeamBadge code={dfn} size={44} named className="mb-0.5" />
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
        <MismatchCrosshairs h={h} defender={T.teams.find((t) => t.code === dfn)!} lanes={T.lanes} />
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
          <details className="mt-4 rounded-xl border border-line bg-surface-2" data-role="lane-table">
            <summary className="cursor-pointer px-4 py-2.5 text-[13px] font-semibold text-ink-2 hover:text-ink">
              Lane table: completion conceded and mismatch per lane
            </summary>
            <ScrollRegion label={`Lanes: ${att} attacking ${dfn}`} className="rounded-none border-x-0 border-b-0">
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
            <p className="px-4 py-2 text-[12px] text-ink-3">"vs" figures are the league rate for that lane.</p>
          </details>
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
      <Panel
        id="states"
        icon="metric-field-tilt"
        title="When the score changes"
        subtitle="Territory and pressing when trailing and when leading. A side that goes ahead and sits deep gives up territory, so the trailing opponent's field tilt rises without meaning it is on top: that is why the Verifier adds box entries to a field-tilt claim from a trailing side."
      >
        <StateSwaps visuals={m.ui.visuals} codes={T.teams.map((t) => t.code)} initial={m.timeline.home.code} />
      </Panel>
      <Panel
        id="zone-shift"
        title="Where the ball was, half by half"
        subtitle={`Showcase match, ${m.timeline.home.code} against ${m.timeline.away.code}: how each side's on-ball events moved between the halves. A side that leads and sits deep shows its share rising in its own third.`}
      >
        <ZoneShift
          track={m.ui.track}
          periods={m.timeline.periods}
          thirdX={m.ui.visuals.zones.third_x}
          codes={[m.timeline.home.code, m.timeline.away.code]}
          initial={m.timeline.home.code}
        />
      </Panel>
      <div className="grid grid-cols-1 gap-flow md:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
        {T.teams.map((t) => (
          <TeamCard key={t.code} team={t} lanes={T.lanes} />
        ))}
      </div>
    </div>
  );
}
