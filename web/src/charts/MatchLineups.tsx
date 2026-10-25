// MatchLineups: both starting XIs of one match facing each other (match file `lineups`, a list from
// lineups.csv laid out by listed position, as on the Team Board). From 640 px: one landscape pitch,
// the home XI on the left attacking right, the away XI on the right attacking left (mirrored, so
// each side's left flank is on its own left). On phones: the two XIs on stacked pitches, both
// attacking left to right, so labels never collide. Card, goal and substitution markers come from
// the match file's turning points (events). Each XI is one tab stop with roving focus; a node opens
// the same mini-profile sheet as the Team Board. Not a tracked shape.
import { useRef, useState } from "react";
import { PitchLines } from "../components/pitch/Pitch";
import { Icon, type IconName } from "../icons";
import { clock } from "../lib/format";
import { useT, type Key } from "../lib/i18n";
import { xiRows, type MatchFile } from "../data/matches";
import type { Period } from "../types/ui";
import { Jersey, LINE_X, surname } from "./LineupPitch";

export type { XiRow } from "../data/matches";
import type { XiRow } from "../data/matches";

/** Column of each line on the facing pitch (home half, attacking right); the away side mirrors it. */
export const FACING_X = [5, 16, 30, 44] as const;
const TOP = 6;
const SPAN = 56;

/** Node centre in pitch metres. facing: one pitch, away mirrored; else its own pitch (LINE_X). */
export function facingPos(r: XiRow, side: "home" | "away", facing: boolean): { x: number; y: number } {
  const [, , , line, slot, of] = r;
  const y = TOP + ((slot + 0.5) * SPAN) / Math.max(1, of);
  if (!facing) return { x: LINE_X[line] ?? 53, y: 8 + ((slot + 0.5) * 52) / Math.max(1, of) };
  const x = FACING_X[line] ?? 30;
  return side === "home" ? { x, y } : { x: 105 - x, y: 68 - y };
}

export interface Marker {
  icon: IconName;
  label: string;
}

/** Per player: goals, cards and being substituted off, in match order (turning points). */
export function lineupMarkers(file: MatchFile, t: (k: Key) => string): Record<string, Marker[]> {
  const out: Record<string, Marker[]> = {};
  const periods = file.periods as Period[];
  for (const tp of file.turning_points) {
    const pid = tp.player_id;
    if (!pid) continue;
    const at = clock(tp.clock_sec, periods);
    const m: Marker | null =
      tp.kind === "goal"
        ? { icon: "goal", label: `${t("tp_goal")} ${at}` }
        : tp.kind === "card"
          ? tp.card === "red" || tp.card === "second_yellow"
            ? { icon: "red-card", label: `${t("tp_red")} ${at}` }
            : { icon: "yellow-card", label: `${t("tp_yellow")} ${at}` }
          : tp.kind === "sub"
            ? { icon: "substitution", label: `${t("lu_off")} ${at}` }
            : null;
    if (m) (out[pid] ??= []).push(m);
  }
  return out;
}

function XiGroup({
  side,
  code,
  rows,
  facing,
  names,
  markers,
  onOpen,
}: {
  side: "home" | "away";
  code: string;
  rows: XiRow[];
  facing: boolean;
  names: Record<string, string>;
  markers: Record<string, Marker[]>;
  onOpen: (id: string, code: string) => void;
}) {
  const { t } = useT();
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (i: number) => {
    const n = (i + rows.length) % rows.length;
    setActive(n);
    refs.current[n]?.focus();
  };
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const step: Record<string, number> = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
    if (e.key in step) move(i + step[e.key]!);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(rows.length - 1);
    else return;
    e.preventDefault();
  };
  return (
    <div role="group" aria-label={`${t("lu_xi")}: ${code}`} className="absolute inset-0" data-xi={side}>
      {rows.map((r, i) => {
        const [id, shirt, pos] = r;
        const p = facingPos(r, side, facing);
        const name = names[id] ?? id;
        const mk = markers[id] ?? [];
        return (
          <button
            key={id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            tabIndex={i === active ? 0 : -1}
            data-node={id}
            data-side={side}
            aria-label={`${shirt} ${surname(name)}, ${name}, ${t(`pos_${pos}` as Key)}${mk.length ? `, ${mk.map((m) => m.label).join(", ")}` : ""}`}
            onKeyDown={(e) => onKey(e, i)}
            onFocus={() => setActive(i)}
            onClick={() => onOpen(id, code)}
            className={`absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center rounded-lg px-0.5 py-0.5 hover:bg-white/5 ${facing ? "w-[10.5%]" : "w-[17%]"}`}
            style={{ left: `${(p.x / 105) * 100}%`, top: `${(p.y / 68) * 100}%` }}
          >
            <span className={`relative ${facing ? "h-7 w-7 lg:h-9 lg:w-9" : "h-7 w-7 sm:h-9 sm:w-9"}`}>
              <Jersey code={code} shirt={shirt} fluid />
              {mk.length > 0 && (
                <span
                  className="absolute -right-2.5 -top-1.5 flex gap-px"
                  data-markers={mk.map((m) => m.icon).join(" ")}
                >
                  {mk.slice(0, 3).map((m, k) => (
                    <Icon key={k} name={m.icon} size={13} className="rounded-sm bg-bg/80" />
                  ))}
                </span>
              )}
            </span>{" "}
            <span className="max-w-full truncate text-[11px] font-semibold leading-tight text-ink">
              {surname(name)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function MatchLineups({ file, onOpen }: { file: MatchFile; onOpen: (id: string, code: string) => void }) {
  const { t } = useT();
  const lu = file.lineups;
  const names = Object.fromEntries(Object.entries(file.players).map(([id, v]) => [id, String(v?.[0] ?? id)]));
  const markers = lineupMarkers(file, t);
  const home = xiRows(file, "home");
  const away = xiRows(file, "away");
  const subs = file.turning_points.filter((tp) => tp.kind === "sub");
  const pitch = (children: React.ReactNode, key: string) => (
    <div key={key} className="relative w-full" style={{ aspectRatio: "105 / 68" }}>
      <svg viewBox="0 0 105 68" className="absolute inset-0 h-full w-full" aria-hidden="true">
        <PitchLines />
      </svg>
      {children}
    </div>
  );
  return (
    <figure className="m-0" data-viz="match-lineups" data-match={file.match_id}>
      <div className="mb-2 flex items-center justify-between text-[12px] font-semibold text-ink-2">
        <span>
          {lu.home.code} · {lu.home.label} →
        </span>
        <span>
          ← {lu.away.code} · {lu.away.label}
        </span>
      </div>
      <div className="hidden sm:block" data-layout="facing">
        {pitch(
          <>
            <XiGroup
              side="home"
              code={lu.home.code}
              rows={home}
              facing
              names={names}
              markers={markers}
              onOpen={onOpen}
            />
            <XiGroup
              side="away"
              code={lu.away.code}
              rows={away}
              facing
              names={names}
              markers={markers}
              onOpen={onOpen}
            />
          </>,
          "facing",
        )}
      </div>
      <div className="flex flex-col gap-3 sm:hidden" data-layout="stacked">
        {(
          [
            ["home", lu.home.code, home],
            ["away", lu.away.code, away],
          ] as const
        ).map(([side, code, rows]) => (
          <div key={side}>
            <p className="mb-1 text-[12px] font-semibold text-ink-2">{code} →</p>
            {pitch(
              <XiGroup
                side={side}
                code={code}
                rows={rows}
                facing={false}
                names={names}
                markers={markers}
                onOpen={onOpen}
              />,
              side,
            )}
          </div>
        ))}
      </div>
      {subs.length > 0 && (
        <ul className="mt-3 grid grid-cols-1 gap-x-4 gap-y-1 text-[12.5px] text-ink-2 sm:grid-cols-2" data-subs>
          {subs.map((s) => (
            <li key={s.event_id} className="flex min-w-0 items-center gap-2">
              <Icon name="substitution" size={16} className="shrink-0 text-ink-3" />
              <span className="num w-[44px] shrink-0 text-ink-3">{clock(s.clock_sec, file.periods as Period[])}</span>
              <span className="w-9 shrink-0 font-semibold text-ink-3">{s.team}</span>
              <span className="min-w-0 truncate">
                <span className="sr-only">{t("lu_off")} </span>
                {surname(names[s.player_id ?? ""] ?? "")} <span aria-hidden="true">→</span>
                <span className="sr-only"> {t("lu_on")}</span> {surname(names[s.on_player_id ?? ""] ?? "")}
              </span>
            </li>
          ))}
        </ul>
      )}
      <figcaption className="mt-2 text-[11.5px] text-ink-3">{t("lu_note")}</figcaption>
    </figure>
  );
}
