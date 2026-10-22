// The replay clock. A requestAnimationFrame loop advances `t` in a zustand store. Components read
// a coarse slice with useReplay(selector) and re-render only when that slice changes; the parts
// that move every frame (clock text, ball marker, playheads) subscribe with useReplayFrame and
// write to DOM refs, so a frame never re-renders the React tree.
import { useEffect } from "react";
import { create } from "zustand";

/** Match seconds per real second. Shown as words (Slow / Normal / Fast), never as numbers. */
export const SPEEDS = { slow: 10, normal: 30, fast: 90 } as const;
export type Speed = keyof typeof SPEEDS;

export interface ReplayState {
  t: number;
  playing: boolean;
  speed: Speed;
  duration: number;
  selected: string | null;
}

export const useReplay = create<ReplayState>(() => ({
  t: 0,
  playing: false,
  speed: "normal",
  duration: 0,
  selected: null,
}));

let raf = 0;
let last = 0;

function frame(now: number) {
  const s = useReplay.getState();
  if (!s.playing) return;
  const dt = last ? Math.min(0.25, (now - last) / 1000) : 0;
  last = now;
  const t = Math.min(s.duration, s.t + dt * SPEEDS[s.speed]);
  const done = t >= s.duration;
  useReplay.setState({ t, playing: !done });
  if (!done) raf = requestAnimationFrame(frame);
}

export function setPlaying(on: boolean) {
  const s = useReplay.getState();
  cancelAnimationFrame(raf);
  last = 0;
  useReplay.setState({ t: on && s.t >= s.duration ? 0 : s.t, playing: on });
  if (on) raf = requestAnimationFrame(frame);
}

export const seek = (t: number) => useReplay.setState((s) => ({ t: Math.max(0, Math.min(s.duration, t)) }));
export const setSpeed = (speed: Speed) => useReplay.setState({ speed });
export const select = (selected: string | null) => useReplay.setState({ selected });

/** Run `cb` on every clock change without re-rendering (for DOM refs). Also runs once on mount. */
export function useReplayFrame(cb: (s: ReplayState) => void, deps: readonly unknown[]) {
  useEffect(() => {
    cb(useReplay.getState());
    return useReplay.subscribe(cb);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
