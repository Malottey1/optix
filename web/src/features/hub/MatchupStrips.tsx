// The Match Hub's Matchup card: for one direction, two lane strips on small pitches (five lane bands,
// the attacker's left flank on top, attacking right). Left: the attacker's share of final-third
// entries per lane minus the league's (pp). Right: the completion rate of entry passes the defender
// conceded per lane minus the league's (pp): the measure the lane claim tests (engine.matchup), not
// the share of entries conceded. Both are season figures, as the claim is (it is computed on the
// season). Only the claim's lane is outlined, and only when its two numbers pass the claim's own
// thresholds (ui teams.matchup_rule); a verified claim is shown only at the display confidence
// (display-only rule, docs/PROGRESS.md). One sentence states the claim's numbers. Diverging heat
// colours, never verdict colours. Table behind "View data".
import { useState } from "react";
import { TeamBadge } from "../../components/brand/TeamBadge";
import { Segmented } from "../../components/ui/segmented";
import { useData } from "../../data/context";
import type { MatchFile } from "../../data/matches";
import { num, signed } from "../../lib/format";
import { useT, type Key } from "../../lib/i18n";
import type { HeadToHead, TeamsSection } from "../../types/ui";
import { fill, Section } from "./parts";

export const LANE_KEY: Record<string, Key> = {
  left_flank: "lane_lf",
  left_half_space: "lane_lhs",
  center: "lane_c",
  right_half_space: "lane_rhs",
  right_flank: "lane_rf",
};

interface Claim {
  attacker: string;
  defender: string;
  claim_id: string;
  confidence?: string | null;
  metrics: {
    lane: string;
    attack_share: number;
    league_share: number;
    concede_completion: number;
    league_completion: number;
  };
}

/** The directions the hub shows: verified claims at the display confidence whose lane's two season
 * lifts pass the claim's thresholds (pure, unit-tested). */
export function shownMatchups(file: MatchFile, teams: TeamsSection): { mu: Claim; h: HeadToHead }[] {
  const rule = teams.matchup_rule;
  return ((file.matchups ?? []) as unknown as Claim[]).flatMap((mu) => {
    const h = teams.head_to_head.find((x) => x.attacker === mu.attacker && x.defender === mu.defender);
    const l = h?.lanes[mu.metrics.lane];
    const ok =
      h &&
      l &&
      rule.display_confidence.includes(String(mu.confidence)) &&
      (l.attack_pp ?? -Infinity) > rule.min_attack_pp &&
      (l.completion_pp ?? -Infinity) > rule.min_completion_pp;
    return ok ? [{ mu, h: h! }] : [];
  });
}

function Strip({
  lanes,
  value,
  claimLane,
  side,
}: {
  lanes: string[];
  value: (lane: string) => number | null;
  claimLane: string;
  side: "attack" | "defence";
}) {
  const { t, lang } = useT();
  const vals = lanes.map(value);
  const top = Math.max(1, ...vals.map((v) => Math.abs(v ?? 0)));
  const band = 68 / lanes.length;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_3.4rem] gap-x-2">
      <svg
        viewBox="0 0 105 68"
        className="block h-auto w-full rounded-md"
        role="img"
        aria-label={t(side === "attack" ? "mu_att_label" : "mu_def_label")}
        data-strip={side}
        data-claim-lane={claimLane}
      >
        <rect x="0" y="0" width="105" height="68" fill="var(--pitch)" />
        {lanes.map((l, i) => {
          const v = vals[i];
          return (
            <rect
              key={l}
              data-lane={l}
              data-value={v ?? ""}
              x="0"
              y={i * band}
              width="105"
              height={band}
              fill={v == null ? "transparent" : v >= 0 ? "var(--heat-rise)" : "var(--heat-fall)"}
              fillOpacity={v == null ? 0 : 0.12 + (0.7 * Math.abs(v)) / top}
            />
          );
        })}
        <g fill="none" stroke="var(--line-strong)" strokeWidth="0.5">
          <rect x="0.25" y="0.25" width="104.5" height="67.5" />
          <line x1="52.5" y1="0" x2="52.5" y2="68" />
          <line x1="70" y1="0" x2="70" y2="68" strokeDasharray="1.5 1.5" />
          <rect x="88.5" y="13.85" width="16.5" height="40.3" />
          <circle cx="52.5" cy="34" r="9.15" />
        </g>
        {lanes.map((l, i) =>
          l === claimLane ? (
            <rect
              key={`o-${l}`}
              data-outline={l}
              x="0.8"
              y={i * band + 0.8}
              width="103.4"
              height={band - 1.6}
              fill="none"
              stroke="var(--ink)"
              strokeWidth="1.4"
              rx="1"
            />
          ) : null,
        )}
      </svg>
      <ol className="flex flex-col" aria-hidden="true">
        {lanes.map((l, i) => (
          <li
            key={l}
            className={`num flex flex-1 items-center justify-end text-[13px] font-semibold ${l === claimLane ? "text-ink" : "text-ink-3"}`}
          >
            {signed(vals[i], lang)}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function Matchup({ file }: { file: MatchFile }) {
  const m = useData();
  const { t, lang } = useT();
  const shown = shownMatchups(file, m.ui.teams);
  const [dir, setDir] = useState(0);
  if (!shown.length) return null;
  const { mu, h } = shown[Math.min(dir, shown.length - 1)]!;
  const lanes = m.ui.teams.lanes;
  const lane = mu.metrics.lane;
  const sentence = fill(t("mu_sentence"), {
    a: mu.attacker,
    d: mu.defender,
    lane: t(LANE_KEY[lane] ?? "lane_c"),
    as: num(mu.metrics.attack_share, lang),
    ls: num(mu.metrics.league_share, lang),
    cc: num(mu.metrics.concede_completion, lang),
    lc: num(mu.metrics.league_completion, lang),
  });
  return (
    <Section id="matchup" title={t("hub_matchup")}>
      <div data-lane-ok="matchup" data-matchup={`${mu.attacker}-${mu.defender}`} data-claim={mu.claim_id}>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="text-[12.5px] text-ink-3">{fill(t("mu_sub"), { a: mu.attacker, d: mu.defender })}</p>
          {shown.length > 1 && (
            <Segmented
              label={t("hub_matchup")}
              name="matchup-dir"
              value={String(dir)}
              onChange={(v) => setDir(Number(v))}
              options={shown.map((s, i) => ({
                value: String(i),
                label: fill(t("mu_attacking"), { team: s.mu.attacker }),
              }))}
            />
          )}
        </div>
        <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-2 md:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)]">
          <ol className="row-start-2 flex flex-col md:row-start-2" aria-hidden="true">
            {lanes.map((l) => (
              <li
                key={l}
                className={`flex flex-1 items-center text-[12px] ${l === lane ? "font-semibold text-ink" : "text-ink-3"}`}
              >
                <span className="inline-block first-letter:uppercase">{t(LANE_KEY[l] ?? "lane_c")}</span>
              </li>
            ))}
          </ol>
          <div className="col-start-2 flex items-center gap-2">
            <TeamBadge code={mu.attacker} size={28} />
            <div className="min-w-0">
              <div className="text-[13.5px] font-semibold text-ink">
                {fill(t("mu_attacking"), { team: mu.attacker })}
              </div>
              <div className="text-[11.5px] text-ink-3">{t("mu_att_label")}</div>
            </div>
          </div>
          <div className="col-start-2 row-start-2">
            <Strip lanes={lanes} value={(l) => h.lanes[l]?.attack_pp ?? null} claimLane={lane} side="attack" />
          </div>
          <div className="col-start-2 flex items-center gap-2 md:col-start-3 md:row-start-1">
            <TeamBadge code={mu.defender} size={28} />
            <div className="min-w-0">
              <div className="text-[13.5px] font-semibold text-ink">
                {fill(t("mu_defending"), { team: mu.defender })}
              </div>
              <div className="text-[11.5px] text-ink-3">{t("mu_def_label")}</div>
            </div>
          </div>
          <div className="col-start-2 md:col-start-3 md:row-start-2">
            <Strip lanes={lanes} value={(l) => h.lanes[l]?.completion_pp ?? null} claimLane={lane} side="defence" />
          </div>
        </div>
        <p className="mt-1 text-right text-[11.5px] text-ink-3">{t("mu_delta")}</p>
        <p className="mt-2 text-[13.5px] leading-snug text-ink-2" data-matchup-sentence>
          {sentence}
        </p>
        <details className="mt-2 text-[12px] text-ink-3">
          <summary className="cursor-pointer select-none py-1 font-semibold text-ink-2">{t("view_data")}</summary>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] border-collapse text-left">
              <thead>
                <tr>
                  <th scope="col" className="py-1 pr-2">
                    {t("tbl_zone")}
                  </th>
                  <th scope="col" className="py-1 pr-2 text-right">
                    {fill(t("mu_tbl_share"), { team: mu.attacker })}
                  </th>
                  <th scope="col" className="py-1 pr-2 text-right">
                    {t("tbl_league")}
                  </th>
                  <th scope="col" className="py-1 pr-2 text-right">
                    {fill(t("mu_tbl_comp"), { team: mu.defender })}
                  </th>
                  <th scope="col" className="py-1 text-right">
                    {t("tbl_league")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {lanes.map((l) => {
                  const r = h.lanes[l];
                  return (
                    <tr key={l} className="border-t border-line">
                      <th scope="row" className="py-1 pr-2 font-normal">
                        {t(LANE_KEY[l] ?? "lane_c")}
                      </th>
                      <td className="num py-1 pr-2 text-right">{num(r?.attack_share, lang)}</td>
                      <td className="num py-1 pr-2 text-right">{num(r?.league_share, lang)}</td>
                      <td className="num py-1 pr-2 text-right">{num(r?.completion, lang)}</td>
                      <td className="num py-1 text-right">{num(r?.league_completion, lang)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-1">{t("mu_rule_note")}</p>
        </details>
      </div>
    </Section>
  );
}
