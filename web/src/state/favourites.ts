// Local favourites (followed teams, players and fixtures): kept in this browser's localStorage, every
// access inside try/catch, so with storage blocked they still work for the visit and nothing breaks.
import { create } from "zustand";

export type FavKind = "teams" | "players" | "fixtures";
export type Favourites = Record<FavKind, string[]>;

const KEY = "optix.favourites.v1";
export const EMPTY: Favourites = { teams: [], players: [], fixtures: [] };

/** Keeps only string ids per kind, unique, in first-seen order (pure, unit-tested). */
export function sanitizeFavs(v: unknown): Favourites {
  const o = v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  const ids = (x: unknown) =>
    Array.isArray(x) ? [...new Set(x.filter((i): i is string => typeof i === "string"))] : [];
  return { teams: ids(o.teams), players: ids(o.players), fixtures: ids(o.fixtures) };
}

function read(): Favourites {
  try {
    const raw = window.localStorage.getItem(KEY);
    return sanitizeFavs(raw ? JSON.parse(raw) : {});
  } catch {
    return { ...EMPTY };
  }
}

function write(v: Favourites) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(v));
  } catch {
    /* storage unavailable: keep the in-memory favourites for this visit */
  }
}

export const useFavourites = create<Favourites>(() => read());

export function toggleFavourite(kind: FavKind, id: string) {
  const cur = useFavourites.getState();
  const next = { ...cur, [kind]: cur[kind].includes(id) ? cur[kind].filter((x) => x !== id) : [...cur[kind], id] };
  useFavourites.setState(next, true);
  write(next);
}

export function clearFavourites() {
  useFavourites.setState({ ...EMPTY }, true);
  write({ ...EMPTY });
}

export const favCount = (f: Favourites) => f.teams.length + f.players.length + f.fixtures.length;
