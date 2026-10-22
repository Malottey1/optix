import { createContext, useContext } from "react";
import type { MatchModel } from "./model";

export const DataContext = createContext<MatchModel | null>(null);

export function useData(): MatchModel {
  const d = useContext(DataContext);
  if (!d) throw new Error("useData outside a loaded DataContext");
  return d;
}
