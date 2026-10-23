// V7 Action Route Circuit Nodes (adapted): the claim's evidence events in clock order, as a chain of
// nodes. Node icon AND colour encode the event type (the event icons of src/icons; types the icon
// sheet has no icon for keep a ring); each node is a button that pins the event on
// the drawer's pitch. The engine has no sequence detection, so this is the evidence chain behind
// the claim, not a detected move. The event table below it stays as the text version.
import { memo } from "react";
import { eventIcon, Icon } from "../../icons";
import { cx } from "../../lib/cx";
import { clock, words } from "../../lib/format";
import type { EvidenceRow, Period } from "../../types/ui";

type Shape = "circle" | "triangle" | "square" | "diamond" | "cross" | "ring";
const TYPE_STYLE: Record<string, { shape: Shape; color: string }> = {
  pass: { shape: "circle", color: "var(--accent)" },
  shot: { shape: "triangle", color: "var(--revise)" },
  possession_change: { shape: "square", color: "var(--muted-accent)" },
  tackle: { shape: "diamond", color: "var(--home)" },
  pressure: { shape: "diamond", color: "var(--away)" },
  interception: { shape: "diamond", color: "var(--home)" },
  foul: { shape: "cross", color: "var(--block)" },
};
const styleOf = (t: string) => TYPE_STYLE[t] ?? { shape: "ring" as Shape, color: "var(--ink-2)" };

export function NodeShape({ type, outcome, size = 16 }: { type: string; outcome?: string | null; size?: number }) {
  const { shape, color } = styleOf(type);
  const icon = eventIcon(type, outcome);
  if (icon) return <Icon name={icon} size={size} className="shrink-0" style={{ color }} />;
  const c = size / 2;
  const r = size / 2 - 2;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true" className="shrink-0">
      {shape === "circle" && <circle cx={c} cy={c} r={r} fill={color} />}
      {shape === "ring" && <circle cx={c} cy={c} r={r - 1} fill="none" stroke={color} strokeWidth="2" />}
      {shape === "square" && <rect x={2} y={2} width={size - 4} height={size - 4} rx="1.5" fill={color} />}
      {shape === "triangle" && <path d={`M${c},2 L${size - 2},${size - 2} L2,${size - 2} Z`} fill={color} />}
      {shape === "diamond" && <path d={`M${c},1 L${size - 1},${c} L${c},${size - 1} L1,${c} Z`} fill={color} />}
      {shape === "cross" && (
        <path
          d={`M3,3 L${size - 3},${size - 3} M${size - 3},3 L3,${size - 3}`}
          stroke={color}
          strokeWidth="2.6"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

export const EvidenceChain = memo(function EvidenceChain({
  rows,
  matchId,
  periods,
  pinned,
  onPin,
}: {
  rows: readonly EvidenceRow[];
  matchId: string;
  periods: readonly Period[];
  pinned: string | null;
  onPin: (id: string | null) => void;
}) {
  const ordered = [...rows].sort((a, b) => a.match_id.localeCompare(b.match_id) || a.clock_sec - b.clock_sec);
  const types = [...new Set(ordered.map((e) => e.event_type))];
  return (
    <figure className="m-0" data-viz="evidence-chain">
      <ul className="mb-3 flex flex-wrap gap-x-3 gap-y-1 text-[11.5px] text-ink-3" aria-label="Node shapes">
        {types.map((t) => (
          <li key={t} className="inline-flex items-center gap-1.5">
            <NodeShape type={t} size={12} />
            {words(t)}
          </li>
        ))}
      </ul>
      <ol className="relative m-0 list-none p-0">
        {ordered.map((e, i) => {
          const prev = ordered[i - 1];
          const newMatch = !prev || prev.match_id !== e.match_id;
          const on = pinned === e.event_id;
          return (
            <li key={e.event_id} data-event-id={e.event_id} data-type={e.event_type} className="relative">
              {newMatch && e.match_id !== matchId && (
                <p className="mb-1 mt-2 text-[11.5px] font-semibold uppercase tracking-wide text-ink-3">{e.match_id}</p>
              )}
              {i < ordered.length - 1 && ordered[i + 1]!.match_id === e.match_id && (
                <span
                  aria-hidden="true"
                  className="absolute left-[15px] top-[26px] h-[calc(100%-14px)] w-0.5 bg-line-strong"
                />
              )}
              <button
                type="button"
                onClick={() => onPin(on ? null : e.event_id)}
                aria-pressed={on}
                className={cx(
                  "relative flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left text-[12.5px] hover:bg-surface-3",
                  on && "bg-accent-soft ring-1 ring-accent-line",
                )}
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface-1">
                  <NodeShape type={e.event_type} outcome={e.outcome} />
                </span>
                <span className="num w-[3.8rem] shrink-0 text-ink-3">
                  {e.match_id === matchId ? clock(e.clock_sec, periods) : clock(e.clock_sec)}
                </span>
                <span className="min-w-0 flex-1 truncate">
                  <b className="font-semibold text-ink">{words(e.event_type)}</b>
                  <span className="text-ink-2"> · {e.player ?? e.team}</span>
                  {e.outcome && <span className="text-ink-3"> · {words(e.outcome)}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </figure>
  );
});
