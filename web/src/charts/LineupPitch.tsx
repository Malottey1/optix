// LineupPitch: the most-used starting XI on the Focus Pitch drawing (ui.lineups, a list from the
// data: most starts, listed positions, the shirt field). Eleven nodes laid out by listed position
// (one column per line, GK to FW, attacking left to right) and by listed role inside a line, so
// two nodes never share a spot. Each node is a real button with a vector jersey in the club accent
// and the squad number, the surname underneath; the group is one tab stop with roving focus (arrow
// keys move, Enter or Space opens). Not a tracked shape: positions are listed, not measured.
import { useRef, useState } from "react";
import { PitchLines } from "../components/pitch/Pitch";
import { useT, type Key } from "../lib/i18n";
import type { LineupNode } from "../types/ui";

/** Column of each line in pitch metres (105 long), attacking left to right. */
export const LINE_X = [7, 28, 53, 79] as const;
const TOP = 8;
const SPAN = 52;

/** Node centre in pitch metres (105 x 68). */
export function nodePos(n: Pick<LineupNode, "line" | "slot" | "of">): { x: number; y: number } {
  return { x: LINE_X[n.line] ?? 53, y: TOP + ((n.slot + 0.5) * SPAN) / Math.max(1, n.of) };
}

export const surname = (name: string) => name.trim().split(/\s+/).at(-1) ?? name;

export function Jersey({ code, shirt, size = 30, fluid = false }: { code: string; shirt: number; size?: number; fluid?: boolean }) {
  return (
    <svg
      viewBox="0 0 40 40"
      width={fluid ? undefined : size}
      height={fluid ? undefined : size}
      aria-hidden="true"
      className={fluid ? "block h-full w-full" : "block"}
    >
      <path
        d="M13 4 L4 9.5 L7.5 18 L11.5 16 L11.5 36 L28.5 36 L28.5 16 L32.5 18 L36 9.5 L27 4 Q20 9 13 4 Z"
        fill={`var(--team-${code.toLowerCase()})`}
        stroke="#05080f"
        strokeOpacity="0.55"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <text
        x="20"
        y="28"
        textAnchor="middle"
        fontSize="13"
        fontWeight="800"
        fill="#05080f"
        fontFamily="var(--font-display)"
      >
        {shirt}
      </text>
    </svg>
  );
}

export function LineupPitch({
  code,
  xi,
  names,
  onOpen,
}: {
  code: string;
  xi: LineupNode[];
  names: Record<string, string>;
  onOpen: (id: string) => void;
}) {
  const { t } = useT();
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (i: number) => {
    const n = (i + xi.length) % xi.length;
    setActive(n);
    refs.current[n]?.focus();
  };
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const step: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (e.key in step) move(i + step[e.key]!);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(xi.length - 1);
    else return;
    e.preventDefault();
  };
  return (
    <div className="relative w-full" style={{ aspectRatio: "105 / 68" }} data-lineup={code}>
      <svg viewBox="0 0 105 68" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <PitchLines />
      </svg>
      <div role="group" aria-label={`${t("board_lineup")}: ${code}`} className="absolute inset-0">
        {xi.map((n, i) => {
          const p = nodePos(n);
          const name = names[n.id] ?? n.id;
          return (
            <button
              key={n.id}
              ref={(el) => {
                refs.current[i] = el;
              }}
              type="button"
              tabIndex={i === active ? 0 : -1}
              data-node={n.id}
              data-line={n.line}
              data-slot={n.slot}
              aria-label={`${n.shirt}, ${name}, ${t(`pos_${n.position}` as Key)}`}
              onKeyDown={(e) => onKey(e, i)}
              onFocus={() => setActive(i)}
              onClick={() => onOpen(n.id)}
              className="absolute flex w-[17%] -translate-x-1/2 -translate-y-1/2 flex-col items-center rounded-lg px-0.5 py-0.5 hover:bg-white/5"
              style={{ left: `${(p.x / 105) * 100}%`, top: `${(p.y / 68) * 100}%` }}
            >
              <span className="h-7 w-7 sm:h-10 sm:w-10 lg:h-12 lg:w-12">
                <Jersey code={code} shirt={n.shirt} fluid />
              </span>
              <span className="max-w-full truncate text-[clamp(10px,1.2vw,12.5px)] font-semibold leading-tight text-ink">
                {surname(name)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
