// #/tech: how a sentence earns its place on screen (with one real claim followed from its blocked
// first attempt to the translated, number-guarded sentence), the verification ledger of every claim
// in the showcase stream, the measured numbers parsed from the generated reports in docs/ (never
// retyped), and what is planned but not built.
import { Fragment, useState } from "react";
import { Icon, type IconName } from "../../components/icons";
import { Chip, StatusChip, type Status } from "../../components/ui/badge";
import { Panel, Stat } from "../../components/ui/card";
import { ScrollRegion } from "../../components/ui/scroll-region";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { useData } from "../../data/context";
import { cx } from "../../lib/cx";
import { cell, clock, num, words } from "../../lib/format";
import { LANG_NAMES, useT } from "../../lib/i18n";
import { LANGS, type LedgerOutcome } from "../../types/ui";
import { reasonFor, textOf } from "../live/shared";

const OUTCOME: Record<LedgerOutcome, { status: Status; label: string }> = {
  passed: { status: "published", label: "Passed" },
  passed_with_context: { status: "published_with_context", label: "Passed with context" },
  revised: { status: "revised", label: "Revised" },
  blocked: { status: "blocked", label: "Blocked" },
};

const STEPS: { icon: IconName; title: string; body: string; tone?: "accent" }[] = [
  {
    icon: "live",
    title: "Event stream",
    body: "Synthetic events, replayed one at a time. Ingest drops duplicates and rows with missing fields.",
  },
  {
    icon: "chart",
    title: "Analyst",
    body: "Computes every number in engine/ and proposes a claim object: metric, value, scope, evidence event ids. No prose.",
  },
  {
    icon: "shield",
    title: "Verifier",
    body: "Fact check: recompute the value from the event log and check every evidence id. Context check: true but misleading given game state, sample size or metric limits?",
    tone: "accent",
  },
  {
    icon: "layers",
    title: "Narrative",
    body: "Fixed templates write the verified claim in English, Spanish and French, in an analyst and a casual tone.",
  },
  {
    icon: "check",
    title: "Number guard",
    body: "Every number in every sentence must equal a number in the claim, in that language's own form.",
    tone: "accent",
  },
  {
    icon: "flag",
    title: "Insight stream",
    body: "A timed item with a semantic type, its evidence ids and the sentences. The dashboard picks the widget.",
  },
];

function Pipeline() {
  const m = useData();
  const { lang } = useT();
  const L = m.ui.ledger;
  return (
    <Panel
      id="pipeline"
      title="Pipeline: math first, language second"
      subtitle="The engine computes every number; the Verifier checks the language-free claim object; only then is it written in each language, and a guard re-checks every number in every sentence. A blocked claim goes back to the Analyst, which revises it by rule and submits it again."
    >
      <ol className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6" data-chart="pipeline">
        {STEPS.map((s, i) => (
          <li
            key={s.title}
            className={cx(
              "relative flex min-w-0 flex-col rounded-xl border bg-surface-2 px-4 py-3.5",
              s.tone === "accent" ? "border-accent-line" : "border-line",
            )}
          >
            <div className="flex items-center gap-2">
              <span
                className={cx(
                  "inline-flex h-7 w-7 items-center justify-center rounded-lg",
                  s.tone === "accent" ? "bg-accent-soft text-accent" : "bg-surface-3 text-ink-2",
                )}
              >
                <Icon name={s.icon} className="h-4 w-4" />
              </span>
              <h3 className="text-[14.5px] font-semibold text-ink">{s.title}</h3>
            </div>
            <p className="mt-2 text-[12.5px] leading-relaxed text-ink-3">{s.body}</p>
            {i < STEPS.length - 1 && (
              <Icon
                name="arrow"
                className="absolute -right-[13px] top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-ink-3 xl:block"
              />
            )}
          </li>
        ))}
      </ol>
      <p className="mt-3 flex items-center gap-2 text-[12.5px] text-revise">
        <Icon name="rewrite" className="h-4 w-4" />
        Blocked → the Analyst revises the claim by the rule's hint → verified again with the next attempt number.
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat value={num(L.attempts, lang)} label="Claim attempts in the showcase stream" />
        <Stat value={num(L.blocked_attempts, lang)} label="Attempts blocked, then revised" tone="revise" />
        <Stat value={num(L.total - L.counts.blocked, lang)} label="Insights published" tone="accent" />
        <Stat value={num(Object.keys(m.ui.reasons).length, lang)} label="Languages, number-guarded" />
      </dl>
    </Panel>
  );
}

/** One real rewritten claim followed through the pipeline, from the files the engine wrote. */
function Walkthrough() {
  const m = useData();
  const { lang } = useT();
  const id = Object.keys(m.ui.rewrites).sort(
    (a, b) => (m.byId[a]?.clock.start_sec ?? 0) - (m.byId[b]?.clock.start_sec ?? 0),
  )[0];
  const ins = id ? m.byId[id] : undefined;
  if (!ins) return null;
  const rw = m.ui.rewrites[ins.insight_id]!;
  const hist = m.chain(ins.claim_id);
  const first = hist[0]!.claim;
  const final = hist.at(-1)!.claim;
  const reason = reasonFor(m, rw.rule_ids, "en");
  const v1 = first.value as { amount?: number; unit?: string };
  return (
    <Panel
      id="walkthrough"
      title="One claim, end to end"
      subtitle={`The ${clock(ins.clock.start_sec, m.timeline.periods)} ${words(ins.insight_type)} card in the showcase stream, read from claims.jsonl and insights.jsonl.`}
    >
      <ol className="grid grid-cols-1 gap-3 lg:grid-cols-4">
        <li className="rounded-xl border border-line bg-surface-2 px-4 py-3.5" data-claim-id={first.claim_id}>
          <p className="eyebrow">Attempt 1 · claim object</p>
          <dl className="mt-2 space-y-1 text-[12.5px]">
            <div className="flex justify-between gap-2">
              <dt className="text-ink-3">metric</dt>
              <dd className="m-0 font-mono text-ink">{first.metric}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-ink-3">value</dt>
              <dd className="num m-0 text-ink">
                {num(v1.amount, lang)} {v1.unit}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-ink-3">template</dt>
              <dd className="m-0 truncate font-mono text-ink">{first.template_key}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-ink-3">evidence</dt>
              <dd className="num m-0 text-ink">{num(first.evidence_event_ids.length, lang)} events</dd>
            </div>
          </dl>
          <p className="mt-3 text-[13px] italic leading-snug text-ink-2 line-through decoration-block/60">
            “{textOf(rw.original, "en", "casual")}”
          </p>
        </li>
        <li className="rounded-xl border border-block/40 bg-block-soft px-4 py-3.5">
          <p className="eyebrow">Verifier · context check</p>
          <StatusChip status="blocked" label="Blocked" className="mt-2" />
          <p className="mt-2 font-mono text-[12px] text-block">{rw.rule_ids.join(", ")}</p>
          {reason && <p className="mt-2 text-[12.5px] leading-snug text-ink-2">{reason}</p>}
          {Object.keys(rw.revision_hint).length > 0 && (
            <p className="mt-2 text-[12px] text-ink-3">
              Asks for:{" "}
              {Object.values(rw.revision_hint)
                .flat()
                .map((x) => (
                  <code key={x} className="mr-1">
                    {x}
                  </code>
                ))}
            </p>
          )}
        </li>
        <li className="rounded-xl border border-line bg-surface-2 px-4 py-3.5" data-claim-id={final.claim_id}>
          <p className="eyebrow">Attempt {final.verification.attempt} · revised</p>
          <StatusChip
            status={final.verification.status === "published_with_context" ? "published_with_context" : "published"}
            label={words(final.verification.status)}
            className="mt-2"
          />
          <p className="mt-2 font-mono text-[12px] text-ink-2">{final.template_key}</p>
          <p className="mt-2 text-[12px] text-ink-3">strategy: {words(rw.strategy)}</p>
        </li>
        <li className="rounded-xl border border-accent-line bg-accent-soft px-4 py-3.5">
          <p className="eyebrow">Narrative + number guard</p>
          <ul className="mt-2 space-y-2 text-[12.5px] leading-snug">
            {LANGS.map((l) => (
              <li key={l} lang={l}>
                <span className="mr-1.5 font-semibold text-ink-3">{LANG_NAMES[l]}</span>
                <span className="text-ink">{textOf(ins.text.rendered, l, "casual")}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 flex items-center gap-1.5 text-[12px] font-semibold text-accent">
            <Icon name="check" className="h-4 w-4" />
            Number guard {ins.text.number_guard_passed ? "passed" : "not recorded"}
          </p>
        </li>
      </ol>
    </Panel>
  );
}

function Ledger() {
  const m = useData();
  const { lang, typeLabel } = useT();
  const L = m.ui.ledger;
  const [tab, setTab] = useState<"all" | LedgerOutcome>("all");
  const rows = L.rows.filter((r) => tab === "all" || r.outcome === tab);
  return (
    <Panel
      id="ledger"
      title="Verification ledger"
      subtitle="Every claim in the showcase stream and what the Verifier decided. A revised claim was blocked on its first attempt by the rule shown, rewritten with the context it asked for, and passed on the next attempt."
    >
      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList label="Filter the ledger by outcome">
          <TabsTrigger value="all">
            All <span className="num opacity-70">{num(L.total, lang)}</span>
          </TabsTrigger>
          {(Object.keys(OUTCOME) as LedgerOutcome[]).map((k) => (
            <TabsTrigger key={k} value={k}>
              <span data-outcome-count={k}>
                {OUTCOME[k].label} <span className="num opacity-70">{num(L.counts[k], lang)}</span>
              </span>
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={tab} className="mt-4 outline-none">
          {rows.length ? (
            <ScrollRegion label="Ledger table, scrolls" className="max-h-[480px]">
              <table className="w-full min-w-[820px] border-collapse text-[12.5px]" data-table="ledger">
                <thead className="sticky top-0 z-10 bg-surface-2 text-left text-ink-3">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Time
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Insight
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Team
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Metric
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Outcome
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Deciding rule
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Attempts
                    </th>
                    <th scope="col" className="px-3 py-2 font-semibold">
                      Templates
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.claim_id}
                      data-claim-id={r.claim_id}
                      data-outcome={r.outcome}
                      className="border-t border-line"
                    >
                      <td className="num whitespace-nowrap px-3 py-1.5">{clock(r.clock_sec, m.timeline.periods)}</td>
                      <td className="px-3 py-1.5">{r.insight_type ? typeLabel(r.insight_type) : "—"}</td>
                      <td className="px-3 py-1.5">{r.team ?? "—"}</td>
                      <td className="px-3 py-1.5">
                        <code className="text-[11.5px]">{r.metric}</code>
                      </td>
                      <td className="px-3 py-1.5">
                        <StatusChip status={OUTCOME[r.outcome].status} label={OUTCOME[r.outcome].label} />
                      </td>
                      <td className="px-3 py-1.5">
                        {r.rule_ids.length ? (
                          r.rule_ids.map((x) => (
                            <code key={x} className="mr-1 text-[11.5px] text-revise">
                              {x}
                            </code>
                          ))
                        ) : (
                          <span className="text-ink-3">none fired</span>
                        )}
                      </td>
                      <td className="num px-3 py-1.5">{num(r.attempts, lang)}</td>
                      <td className="px-3 py-1.5 text-ink-3">
                        <code className="text-[11px]">{r.template_keys.join(" → ")}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ScrollRegion>
          ) : (
            <p className="rounded-xl border border-dashed border-line-strong/70 px-4 py-6 text-center text-[13px] text-ink-3">
              No claim in the showcase stream had this outcome.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </Panel>
  );
}

function Measured() {
  const m = useData();
  const { lang } = useT();
  const reports = m.ui.measured;
  const [tab, setTab] = useState(reports[0]?.file ?? "");
  if (!reports.length) return null;
  return (
    <Panel
      id="measured"
      title="Measured numbers"
      subtitle="Read from the generated reports in docs/ at the time the data was built: realism targets, multi-seed robustness, and Verifier recall with the hold-out seeds and Wilson 95% intervals. Nothing here is retyped."
    >
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList label="Report">
          {reports.map((r) => (
            <TabsTrigger key={r.file} value={r.file}>
              {r.title}
            </TabsTrigger>
          ))}
        </TabsList>
        {reports.map((r) => (
          <TabsContent key={r.file} value={r.file} className="mt-4 outline-none" data-report={r.file}>
            <p className="text-[13px] leading-relaxed text-ink-2">
              <code className="mr-2 text-[11.5px] text-ink-3">{r.file}</code>
              <Prose text={cell(r.intro, lang)} />
            </p>
            {r.notes.some((n) => /Reading/.test(n.heading)) && (
              <ul className="mt-3 space-y-2">
                {r.notes
                  .filter((n) => /Reading/.test(n.heading))
                  .map((n, i) => (
                    <li
                      key={i}
                      className="rounded-xl border border-accent-line bg-accent-soft px-3.5 py-2.5 text-[13px] leading-relaxed text-ink"
                    >
                      {cell(n.text, lang)}
                    </li>
                  ))}
              </ul>
            )}
            <div className="mt-3 space-y-2">
              {r.tables.map((t, i) => (
                <details key={i} open={i === 0} className="rounded-xl border border-line bg-surface-2">
                  <summary className="cursor-pointer px-4 py-2.5 text-[13px] font-semibold text-ink-2 hover:text-ink">
                    {cell(t.heading, lang)}{" "}
                    <span className="num ml-1 font-normal text-ink-3">({num(t.rows.length, lang)} rows)</span>
                  </summary>
                  <ScrollRegion label={t.heading} className="max-h-[440px] rounded-none border-x-0 border-b-0">
                    <table className="w-full border-collapse text-[12px]" data-table="report">
                      <thead className="sticky top-0 bg-surface-3 text-left text-ink-3">
                        <tr>
                          {t.headers.map((h, j) => (
                            <th key={j} scope="col" className="whitespace-nowrap px-3 py-1.5 font-semibold">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {t.rows.map((row, j) => (
                          <tr key={j} className="border-t border-line">
                            {row.map((c, k) => (
                              <Fragment key={k}>
                                {k === 0 ? (
                                  <th scope="row" className="px-3 py-1 text-left align-top font-semibold text-ink">
                                    {cell(c, lang)}
                                  </th>
                                ) : (
                                  <td
                                    className={cx(
                                      "num whitespace-nowrap px-3 py-1 align-top",
                                      /\bok\b/.test(c) ? "text-pass" : "text-ink-2",
                                    )}
                                  >
                                    {cell(c, lang)}
                                  </td>
                                )}
                              </Fragment>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollRegion>
                </details>
              ))}
            </div>
          </TabsContent>
        ))}
      </Tabs>
    </Panel>
  );
}

/** Report prose from markdown: `code` spans become <code>, the rest stays plain text. */
function Prose({ text }: { text: string }) {
  return (
    <>
      {text.split("`").map((part, i) =>
        i % 2 ? (
          <code key={i} className="text-[12px] text-ink">
            {part}
          </code>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

const BUILT = [
  ["Deterministic engine and Verifier", "Python in engine/ and agents/; every number in this dashboard comes from it."],
  [
    "Replay of the verified stream",
    "The dashboard replays the showcase match from the files the engine wrote (web/public/data).",
  ],
  [
    "Three languages behind a number guard",
    "Hand-written English, Spanish and French templates; every number re-checked per language.",
  ],
];
const PLANNED = [
  [
    "Azure hosting",
    "The dashboard and engine run locally today (a static file server and Python). No Azure resource exists for this repo.",
  ],
  [
    "Live stream over server-sent events",
    "The dashboard defines an SSE source and its contract test, marked not wired yet; no server sends events.",
  ],
  ["Event Hubs ingestion", "Events are read from CSV files and replayed in process; there is no live event feed."],
  ["Application Insights telemetry", "Agent logs are written to out/agent_log.jsonl only."],
  ["Microsoft Agent Framework", "The agents are plain Python classes in one process; no agent framework is wired in."],
  [
    "LLM phrasing",
    "Every sentence comes from fixed templates. A language model would only reword verified facts behind the same number guard; it is not built.",
  ],
];

export default function TechPage() {
  return (
    <div className="flex flex-col gap-flow" data-page="tech">
      <header className="max-w-3xl">
        <p className="eyebrow">How it works</p>
        <h1 className="mt-1 text-[28px] font-bold tracking-tight text-ink sm:text-[34px]">Tech Blueprint</h1>
        <p className="mt-2 text-[14.5px] leading-relaxed text-ink-2">
          How a sentence earns its place on screen, what the Verifier decided for every claim in the showcase match, and
          how well the engine and the Verifier measure up.
        </p>
      </header>
      <Pipeline />
      <Walkthrough />
      <Ledger />
      <Measured />
      <Panel
        id="planned"
        title="Planned Azure integration (not built yet)"
        subtitle="Listed so nobody mistakes the plan for the product."
      >
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
          <div>
            <p className="eyebrow">Built today</p>
            <ul className="mt-2 space-y-2">
              {BUILT.map(([k, v]) => (
                <li key={k} className="rounded-xl border border-line bg-surface-2 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Icon name="check" className="h-4 w-4 text-pass" />
                    <b className="text-[14px] text-ink">{k}</b>
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed text-ink-3">{v}</p>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="eyebrow">Planned, not built</p>
            <ul className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              {PLANNED.map(([k, v]) => (
                <li key={k} data-planned className="rounded-xl border border-dashed border-line-strong px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Chip>
                      <Icon name="cloud" className="h-3.5 w-3.5" />
                      Planned
                    </Chip>
                    <b className="text-[14px] text-ink">{k}</b>
                  </div>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink-3">{v}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Panel>
    </div>
  );
}
