// A tiny external store, read with useSyncExternalStore and a selector, so a component re-renders
// only when the slice it reads changes (the replay clock ticks every frame; most of the page
// does not care).
import { React } from "./html.js";

export function createStore(initial) {
  let state = initial;
  const subs = new Set();
  return {
    get: () => state,
    set(patch) {
      const next = typeof patch === "function" ? patch(state) : { ...state, ...patch };
      if (next === state) return;
      state = next;
      subs.forEach((f) => f());
    },
    subscribe(f) {
      subs.add(f);
      return () => subs.delete(f);
    },
  };
}

export function useStore(store, selector = (s) => s) {
  return React.useSyncExternalStore(store.subscribe, () => selector(store.get()));
}
