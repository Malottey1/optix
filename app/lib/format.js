// Display formatting only. No statistic is computed here: values arrive rounded from the engine
// (out/ui.json, out/insights.jsonl) and are written as they are, with the language's decimal mark.

const DECIMAL_COMMA = new Set(["es", "fr"]);

/** A number as the engine wrote it, with a decimal comma in es/fr. null -> en dash. */
export function num(v, lang = "en") {
  if (v === null || v === undefined || v === "") return "–";
  const s = String(v);
  return DECIMAL_COMMA.has(lang) ? s.replace(".", ",") : s;
}

/** A report cell (docs tables): numbers inside it get the language's decimal mark. */
export function cell(s, lang = "en") {
  if (!DECIMAL_COMMA.has(lang)) return s;
  return String(s).replace(/(\d)\.(\d)/g, "$1,$2");
}

const pad = (n) => String(n).padStart(2, "0");

/**
 * Elapsed clock seconds -> football time: mm:ss inside each half (the second half starts at
 * 45:00), then 45+m / 90+m in stoppage time. `periods` comes from out/timeline.json.
 */
export function clock(sec, periods = []) {
  sec = Math.max(0, Math.floor(sec));
  const half = [...periods].reverse().find((p) => sec >= p.start_sec);
  if (!half) return `${pad(Math.floor(sec / 60))}:${pad(sec % 60)}`;
  const base = (half.period - 1) * 2700;
  const into = sec - half.start_sec;
  if (into <= 2700) return `${pad(Math.floor((base + into) / 60))}:${pad((base + into) % 60)}`;
  return `${(base + 2700) / 60}+${Math.ceil((into - 2700) / 60)}`;
}

/** Minute-only football time for compact chips: 12' or 45+2'. */
export function minute(sec, periods = []) {
  const c = clock(sec, periods);
  return c.includes("+") ? `${c}'` : `${c.split(":")[0].replace(/^0(?=\d)/, "")}'`;
}

export const cx = (...parts) => parts.filter(Boolean).join(" ");
