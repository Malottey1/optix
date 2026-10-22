// User settings: language, reduced motion, density, evidence open by default, high contrast.
// Persisted in localStorage inside try/catch: the app works the same when storage is blocked.
import { create } from "zustand";
import { LANGS, type Lang } from "../types/ui";

export interface Settings {
  lang: Lang;
  reducedMotion: boolean;
  density: "comfortable" | "compact";
  evidenceOpen: boolean;
  highContrast: boolean;
}

const KEY = "optix.settings.v2";
export const DEFAULTS: Settings = {
  lang: "en",
  reducedMotion: false,
  density: "comfortable",
  evidenceOpen: false,
  highContrast: false,
};

export function sanitize(v: Partial<Record<keyof Settings, unknown>>): Settings {
  return {
    lang: LANGS.includes(v.lang as Lang) ? (v.lang as Lang) : DEFAULTS.lang,
    reducedMotion: v.reducedMotion === true,
    density: v.density === "compact" ? "compact" : "comfortable",
    evidenceOpen: v.evidenceOpen === true,
    highContrast: v.highContrast === true,
  };
}

function read(): Partial<Settings> {
  try {
    const raw = window.localStorage.getItem(KEY);
    const v: unknown = raw ? JSON.parse(raw) : {};
    return v && typeof v === "object" ? (v as Partial<Settings>) : {};
  } catch {
    return {};
  }
}

function write(v: Settings) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(v));
  } catch {
    /* storage unavailable (private mode, blocked): keep the in-memory settings */
  }
}

export function osReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

export const useSettings = create<Settings>(() => sanitize({ ...DEFAULTS, ...read() }));

export const motionReduced = (s: Settings = useSettings.getState()) => s.reducedMotion || osReducedMotion();

export function applyToDocument(s: Settings) {
  const root = document.documentElement;
  root.lang = s.lang;
  root.dataset.density = s.density;
  root.dataset.contrast = s.highContrast ? "high" : "normal";
  root.dataset.motion = motionReduced(s) ? "reduce" : "full";
}

useSettings.subscribe((s) => {
  write(s);
  applyToDocument(s);
});

export const setSetting = <K extends keyof Settings>(k: K, v: Settings[K]) =>
  useSettings.setState({ [k]: v } as Pick<Settings, K>);
