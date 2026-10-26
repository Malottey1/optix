// The viewer's personalization: Fan or Analyst view, the followed player (player focus) and the
// focus metric. Mode and focus are kept in this browser's localStorage, every access inside
// try/catch, so with storage blocked they still work for the visit; the metric lives in memory.
// What they select comes from lib/personalize.ts: the same verified insights, never new numbers.
import { create } from "zustand";
import { CONFIG, isMetric, isMode, type MetricId, type Mode } from "../lib/personalize";

export interface View {
  mode: Mode;
  focus: string | null;
  metric: MetricId | null;
}

export const VIEW_KEY = "optix.view.v1";

/** A stored value back to a View; anything unknown falls back to the default (pure, unit-tested). */
export function sanitizeView(v: unknown): Omit<View, "metric"> {
  const o = v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  return {
    mode: isMode(o.mode) ? o.mode : CONFIG.default_mode,
    focus: typeof o.focus === "string" && /^[A-Z]{3}_\d+$/.test(o.focus) ? o.focus : null,
  };
}

function read() {
  try {
    const raw = window.localStorage.getItem(VIEW_KEY);
    return sanitizeView(raw ? JSON.parse(raw) : {});
  } catch {
    return sanitizeView({});
  }
}

function write(v: View) {
  try {
    window.localStorage.setItem(VIEW_KEY, JSON.stringify({ mode: v.mode, focus: v.focus }));
  } catch {
    /* storage unavailable: keep the in-memory view for this visit */
  }
}

export const useView = create<View>(() => ({ ...read(), metric: null }));

useView.subscribe(write);

export const setMode = (mode: Mode) => useView.setState({ mode });
export const setFocus = (focus: string | null) => useView.setState({ focus });
export const setMetric = (metric: MetricId | null) => useView.setState({ metric: isMetric(metric) ? metric : null });
export const useFan = () => useView((s) => s.mode === "fan");
