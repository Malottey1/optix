// Display formatting only. No statistic is computed here: values arrive rounded from the engine
// and are written as they are, with the language's decimal mark.
import type { Lang, Period } from "../types/ui";

const DECIMAL_COMMA = new Set<string>(["es", "fr"]);

/** A number as the engine wrote it, with a decimal comma in es/fr. null -> en dash. */
export function num(v: number | string | null | undefined, lang: Lang = "en"): string {
  if (v === null || v === undefined || v === "") return "–";
  const s = String(v);
  return DECIMAL_COMMA.has(lang) ? s.replace(".", ",") : s;
}

export const pct = (v: number | null | undefined, lang: Lang = "en") => (v == null ? "–" : `${num(v, lang)}%`);

export const signed = (v: number | null | undefined, lang: Lang = "en") =>
  v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${num(Math.abs(v), lang)}`;

/** Numbers inside a report cell get the language's decimal mark. */
export const cell = (s: string, lang: Lang = "en") => (DECIMAL_COMMA.has(lang) ? s.replace(/(\d)\.(\d)/g, "$1,$2") : s);

const pad = (n: number) => String(n).padStart(2, "0");

/**
 * Elapsed clock seconds -> football time: mm:ss inside each half (the second half starts at
 * 45:00), then 45+m / 90+m in stoppage time. `periods` comes from timeline.json.
 */
export function clock(sec: number, periods: readonly Period[] = []): string {
  const s = Math.max(0, Math.floor(sec));
  const half = [...periods].reverse().find((p) => s >= p.start_sec);
  if (!half) return `${pad(Math.floor(s / 60))}:${pad(s % 60)}`;
  const base = (half.period - 1) * 2700;
  const into = s - half.start_sec;
  if (into <= 2700) return `${pad(Math.floor((base + into) / 60))}:${pad((base + into) % 60)}`;
  return `${(base + 2700) / 60}+${Math.ceil((into - 2700) / 60)}`;
}

/** Which phase of the match the clock is in. */
export function phase(
  sec: number,
  periods: readonly Period[],
  duration: number,
): "pre" | "first" | "half" | "second" | "full" {
  const [p1, p2] = periods;
  if (sec >= duration) return "full";
  if (!p1 || sec < p1.start_sec) return "pre";
  if (sec <= p1.end_sec) return "first";
  if (p2 && sec < p2.start_sec) return "half";
  return "second";
}

/** snake_case engine words for display: "box_entry" -> "box entry". */
export const words = (s: string | null | undefined) => (s ? s.replace(/_/g, " ") : "–");
