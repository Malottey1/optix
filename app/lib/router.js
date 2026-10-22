// Hash routing: #/live, #/teams, #/players, #/tech. Query after the path (#/live?t=2760) carries
// view options used by the screenshots and tests.
import { React } from "./html.js";

export const ROUTES = ["live", "teams", "players", "tech"];

export function parseHash(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, "");
  const [path, query = ""] = raw.split("?");
  const route = ROUTES.includes(path) ? path : "live";
  return { route, params: new URLSearchParams(query) };
}

export function useRoute() {
  const [r, setR] = React.useState(() => parseHash());
  React.useEffect(() => {
    const on = () => setR(parseHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}
