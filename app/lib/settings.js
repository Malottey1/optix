// User settings: language, reduced motion, density, evidence open by default, high contrast.
// Persisted in localStorage inside try/catch: the app works the same when storage is unavailable.
import { createStore, useStore } from "./store.js";

const KEY = "optix.settings.v1";
const DEFAULTS = { lang: "en", reducedMotion: false, density: "comfortable", evidenceOpen: false, highContrast: false };
const LANGS = ["en", "es", "fr"];

function read() {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return {};
    const v = JSON.parse(raw);
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

function write(v) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(v));
  } catch {
    /* storage unavailable (private mode, blocked): keep the in-memory settings */
  }
}

const osReduced = () => {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
};

function sanitize(v) {
  return {
    lang: LANGS.includes(v.lang) ? v.lang : DEFAULTS.lang,
    reducedMotion: Boolean(v.reducedMotion),
    density: v.density === "compact" ? "compact" : "comfortable",
    evidenceOpen: Boolean(v.evidenceOpen),
    highContrast: Boolean(v.highContrast),
  };
}

export const settings = createStore(sanitize({ ...DEFAULTS, ...read() }));

export function applyToDocument(s) {
  const root = document.documentElement;
  root.lang = s.lang;
  root.dataset.density = s.density;
  root.dataset.contrast = s.highContrast ? "high" : "normal";
  root.dataset.motion = s.reducedMotion || osReduced() ? "reduce" : "full";
}

settings.subscribe(() => {
  write(settings.get());
  applyToDocument(settings.get());
});
applyToDocument(settings.get());

export const setSetting = (k, v) => settings.set({ ...settings.get(), [k]: v });
export const useSettings = (sel) => useStore(settings, sel);
export const motionReduced = () => settings.get().reducedMotion || osReduced();
export { LANGS };
