// Which source feeds the page, for the honest indicator on the scoreboard: "live" while the Optix
// server is pushing the verified stream over SSE, "replay" when the page replays the files (static
// hosting, or after the live stream failed: `fellBack`).
import { create } from "zustand";

export interface SourceState {
  mode: "replay" | "live";
  fellBack: boolean;
}

export const useSource = create<SourceState>(() => ({ mode: "replay", fellBack: false }));
