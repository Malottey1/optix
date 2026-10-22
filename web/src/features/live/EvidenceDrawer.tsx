// The evidence drawer: the exact events behind a claim, the claim object the Verifier checked,
// and every verification attempt with the rule that decided it. Rows and pitch marks share
// data-event-id; hovering or focusing a row highlights its mark on the mini pitch.
import { useState, type ReactNode } from "react";
import { Arrowheads, InsightLayer, PitchLines } from "../../components/pitch/Pitch";
import { StatusChip, TeamDot } from "../../components/ui/badge";
import { Sheet } from "../../components/ui/sheet";
import { useData } from "../../data/context";
import { cx } from "../../lib/cx";
import { clock, num, words } from "../../lib/format";
import { useT } from "../../lib/i18n";
import type { Insight } from "../../types/ui";
import { STATUS_KEY } from "./Feed";
import { reasonFor, statusOf, textOf } from "./shared";

function Kv({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-line py-2 text-[13px] last:border-b-0">
      <dt className="text-ink-3">{k}</dt>
      <dd className="m-0 min-w-0 text-right font-semibold text-ink">{v}</dd>
    </div>
  );
}

function Body({ ins }: { ins: Insight }) {
  const m = useData();
  const { t, lang } = useT();
  const [hi, setHi] = useState<string | null>(null);
  const tl = m.timeline;
  const hist = m.chain(ins.claim_id);
  const final = hist.at(-1)!.claim;
  const v = final.value as {
    amount?: number;
    unit?: string;
    baseline?: number | null;
    confidence?: string | null;
    baseline_source?: { kind: string; n: number } | null;
  };
  const rows = m.evidenceOf(ins.evidence_event_ids);
  const inMatch = (matchId: string) => matchId === tl.match_id;
  const side = m.sideOf(ins.teams.primary);
  const hasPoints = (ins.payload.points ?? []).length > 0;
  return (
    <div className="space-y-6">
      <p className="text-[14px] leading-relaxed text-ink-2" lang={lang}>
        {textOf(ins.text.rendered, lang, "analyst")}
      </p>

      {hasPoints && (
        <figure className="m-0">
          <svg
            viewBox="-2.5 -2 110 72"
            className="block h-auto w-full rounded-xl"
            role="img"
            aria-label={`${t("evidence")}: ${ins.teams.primary} ${t("attacking")}`}
          >
            <Arrowheads id="drawer" />
            <PitchLines />
            <InsightLayer insight={ins} side={side} markerId="drawer" highlight={hi} />
          </svg>
          <figcaption className="mt-2 flex items-center gap-1.5 text-[12px] text-ink-3">
            <TeamDot side={side} />
            {ins.teams.primary} {t("attacking")} →
          </figcaption>
        </figure>
      )}

      <section aria-labelledby="claim-h">
        <h3 id="claim-h" className="eyebrow">
          {t("claim_object")}
        </h3>
        <dl className="mt-2 rounded-xl border border-line bg-surface-2 px-3.5">
          <Kv k={t("metric")} v={<code className="text-[12px]">{final.metric}</code>} />
          {v.amount != null && (
            <Kv k={t("value")} v={<span className="num">{`${num(v.amount, lang)} ${v.unit ?? ""}`}</span>} />
          )}
          <Kv
            k={t("scope")}
            v={
              final.window && final.scope === "window" ? (
                <span className="num">{`${words(final.scope)} · ${clock(final.window.from_sec, tl.periods)}–${clock(final.window.to_sec, tl.periods)}`}</span>
              ) : (
                words(final.scope)
              )
            }
          />
          {v.baseline != null && (
            <Kv
              k={t("baseline")}
              v={
                <span className="num">{`${num(v.baseline, lang)}${v.baseline_source ? ` (${v.baseline_source.kind}, n=${v.baseline_source.n})` : ""}`}</span>
              }
            />
          )}
          {v.confidence && <Kv k={t("confidence")} v={v.confidence} />}
          {Object.entries((final.supporting_values ?? {}) as Record<string, number | null>).map(([k, x]) => (
            <Kv key={k} k={words(k)} v={<span className="num">{num(x, lang)}</span>} />
          ))}
        </dl>
      </section>

      <section aria-labelledby="attempts-h">
        <h3 id="attempts-h" className="eyebrow">
          {t("attempts_title")}
        </h3>
        <ol className="relative mt-3 space-y-3 border-l border-line-strong pl-5">
          {hist.map((a) => {
            const ver = a.claim.verification;
            const rs = ver.rule_ids ?? [];
            const st =
              ver.status === "blocked"
                ? "blocked"
                : ver.status === "published_with_context"
                  ? "published_with_context"
                  : "published";
            const reason = ver.status === "blocked" ? reasonFor(m, rs, lang) : null;
            return (
              <li key={a.claim.claim_id} data-claim-id={a.claim.claim_id} className="relative">
                <span
                  aria-hidden="true"
                  className={cx(
                    "absolute -left-[26px] top-1 h-3 w-3 rounded-full border-2 border-surface-1",
                    st === "blocked" ? "bg-block" : st === "published_with_context" ? "bg-muted" : "bg-pass",
                  )}
                />
                <div className="flex flex-wrap items-center gap-2 text-[13px]">
                  <b className="font-semibold text-ink">
                    {t("attempt")} {ver.attempt}
                  </b>
                  <StatusChip status={st} label={t(STATUS_KEY[st])} />
                  <code className="text-[11.5px] text-ink-3">{a.claim.template_key}</code>
                </div>
                {rs.length > 0 && (
                  <p className="mt-1 text-[12.5px] text-ink-2">
                    {t("rules")}:{" "}
                    {rs.map((r) => (
                      <code key={r} className="mr-1.5 text-[11.5px] text-revise">
                        {r}
                      </code>
                    ))}
                  </p>
                )}
                {reason && <p className="mt-1 text-[12.5px] leading-snug text-ink-2">{reason}</p>}
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-labelledby="events-h">
        <h3 id="events-h" className="eyebrow">
          {t("evidence_events")} · <span className="num">{num(rows.length, lang)}</span>
        </h3>
        <div className="mt-2 overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[480px] border-collapse text-[12.5px]">
            <thead className="bg-surface-2 text-left text-ink-3">
              <tr>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {t("time")}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {t("player")}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {t("type")}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {t("outcome")}
                </th>
                <th scope="col" className="px-3 py-2 font-semibold">
                  {t("id")}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr
                  key={e.event_id}
                  data-event-id={e.event_id}
                  tabIndex={hasPoints ? 0 : undefined}
                  onMouseEnter={() => setHi(e.event_id)}
                  onMouseLeave={() => setHi(null)}
                  onFocus={() => setHi(e.event_id)}
                  onBlur={() => setHi(null)}
                  className={cx(
                    "border-t border-line outline-none focus-visible:bg-surface-3",
                    hi === e.event_id && "bg-accent-soft",
                  )}
                >
                  <td className="num whitespace-nowrap px-3 py-1.5">
                    {inMatch(e.match_id) ? clock(e.clock_sec, tl.periods) : e.match_id}
                  </td>
                  <td className="px-3 py-1.5">
                    {e.player ?? e.team}
                    {e.related_player && <span className="text-ink-3"> → {e.related_player}</span>}
                  </td>
                  <td className="px-3 py-1.5">{words(e.event_type)}</td>
                  <td className="px-3 py-1.5">{words(e.outcome)}</td>
                  <td className="px-3 py-1.5">
                    <code className="text-[11px] text-ink-3">{e.event_id}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export function EvidenceDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const m = useData();
  const { t, typeLabel, lang } = useT();
  const ins = id ? m.byId[id] : undefined;
  const status = ins ? statusOf(m, ins) : "published";
  return (
    <Sheet
      open={Boolean(ins)}
      onOpenChange={(o) => !o && onClose()}
      id="drawer"
      attrs={ins ? { "data-insight-id": ins.insight_id, "data-claim-id": ins.claim_id } : undefined}
      closeLabel={t("close_drawer")}
      eyebrow={
        ins && (
          <span className="inline-flex flex-wrap items-center gap-2">
            {t("evidence")} · {typeLabel(ins.insight_type)} ·{" "}
            <span className="num">{clock(ins.clock.start_sec, m.timeline.periods)}</span>
            <StatusChip status={status} label={t(STATUS_KEY[status])} className="normal-case tracking-normal" />
          </span>
        )
      }
      title={ins ? <span lang={lang}>{textOf(ins.text.rendered, lang, "casual")}</span> : ""}
    >
      {ins && <Body ins={ins} />}
    </Sheet>
  );
}
