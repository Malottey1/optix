// Lazy access to the fixture index and the per-match files from any page (data/matches.ts). The
// provider lets tests inject a MatchFiles that reads from disk.
import { createContext, useContext, useEffect, useState } from "react";
import type { EventFile } from "./events";
import { type FixtureIndex, type MatchFile, MatchFiles, type PlayersHeat, type TeamLists, matchFiles } from "./matches";

export const MatchFilesContext = createContext<MatchFiles>(matchFiles);

type Loaded<T> = { data: T | null; error: Error | null };

function useLoad<T>(load: (() => Promise<T>) | null, key: string): Loaded<T> {
  const [state, setState] = useState<Loaded<T> & { key: string }>({ data: null, error: null, key: "" });
  useEffect(() => {
    if (!load) return;
    let live = true;
    load().then(
      (data) => live && setState({ data, error: null, key }),
      (error: Error) => live && setState({ data: null, error, key }),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload only when the key changes
  }, [key]);
  return state.key === key ? state : { data: null, error: null };
}

export function useFixtures(): Loaded<FixtureIndex> {
  const src = useContext(MatchFilesContext);
  return useLoad(() => src.fixtures(), "index");
}

export function useMatchFile(id: string | null): Loaded<MatchFile> {
  const src = useContext(MatchFilesContext);
  return useLoad(id ? () => src.match(id) : null, id ?? "");
}

export function usePlayersHeat(code: string | null): Loaded<PlayersHeat> {
  const src = useContext(MatchFilesContext);
  return useLoad(code ? () => src.playersHeat(code) : null, code ? `heat:${code}` : "");
}

export function useTeamLists(code: string | null): Loaded<TeamLists> {
  const src = useContext(MatchFilesContext);
  return useLoad(code ? () => src.teamLists(code) : null, code ? `lists:${code}` : "");
}

/** The showcase's event file, loaded only while a player is followed (id null: nothing is fetched). */
export function useEventFile(id: string | null): Loaded<EventFile> {
  const src = useContext(MatchFilesContext);
  return useLoad(id ? () => src.events(id) : null, id ? `events:${id}` : "");
}
