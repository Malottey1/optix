// The route map (docs/dashboard.md). Old deep links keep working: #/live (with its view options)
// goes to the showcase Match Hub; anything unknown goes home. routes.test.tsx checks each one.
import { lazy } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";
import { SHOWCASE_ID } from "./data/matches";

const HomePage = lazy(() => import("./features/home/HomePage"));
const FixturesPage = lazy(() => import("./features/fixtures/FixturesPage"));
const MatchHub = lazy(() => import("./features/hub/MatchHub"));
const MatchLedger = lazy(() => import("./features/hub/MatchHub").then((m) => ({ default: m.MatchLedger })));
const TeamsPage = lazy(() => import("./features/teams/TeamsPage"));
const PlayersPage = lazy(() => import("./features/players/PlayersPage"));
const TechPage = lazy(() => import("./features/tech/TechPage"));

/** Old path -> new path. The query (t, select, lang, play) is kept. */
export const REDIRECTS: Record<string, string> = {
  "/live": `/match/${SHOWCASE_ID}`,
  "/match": "/fixtures",
};

function Redirect({ to }: { to: string }) {
  const { search } = useLocation();
  return <Navigate to={{ pathname: to, search }} replace />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route index element={<HomePage />} />
      <Route path="/fixtures" element={<FixturesPage />} />
      <Route path="/match/:id" element={<MatchHub />} />
      <Route path="/match/:id/ledger" element={<MatchLedger />} />
      <Route path="/teams" element={<TeamsPage />} />
      <Route path="/players" element={<PlayersPage />} />
      <Route path="/tech" element={<TechPage />} />
      {Object.entries(REDIRECTS).map(([from, to]) => (
        <Route key={from} path={from} element={<Redirect to={to} />} />
      ))}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
