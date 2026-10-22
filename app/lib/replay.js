// The replay clock. requestAnimationFrame advances `t`; components subscribe to a slice of it
// with useReplay(selector) and re-render only when that slice changes.
import { createStore, useStore } from "./store.js";

export const SPEEDS = { slow: 10, normal: 30, fast: 90 };      // match seconds per real second

export const replay = createStore({ t: 0, playing: false, speed: "normal", duration: 0, selected: null });

let raf = 0;
let last = 0;

function frame(now) {
  const s = replay.get();
  if (!s.playing) return;
  const dt = last ? Math.min(0.25, (now - last) / 1000) : 0;
  last = now;
  const t = Math.min(s.duration, s.t + dt * SPEEDS[s.speed]);
  const done = t >= s.duration;
  replay.set({ ...s, t, playing: !done });
  if (!done) raf = requestAnimationFrame(frame);
}

export function setPlaying(on) {
  const s = replay.get();
  cancelAnimationFrame(raf);
  last = 0;
  const t = on && s.t >= s.duration ? 0 : s.t;
  replay.set({ ...s, t, playing: on });
  if (on) raf = requestAnimationFrame(frame);
}

export const seek = (t) => replay.set({ ...replay.get(), t: Math.max(0, Math.min(replay.get().duration, t)) });
export const setSpeed = (speed) => replay.set({ ...replay.get(), speed });
export const select = (id) => replay.set({ ...replay.get(), selected: id });
export const useReplay = (sel) => useStore(replay, sel);
