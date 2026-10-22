// Loads the match once through a StreamSource, then routes by hash (#/live, #/teams, #/players,
// #/tech). View options for screenshots and tests: #/live?t=2760&select=ins_0009&lang=es&play=1
import { LazyMotion, MotionConfig, domAnimation } from "motion/react";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { HashRouter, Navigate, Route, Routes, useLocation } from "react-router";
import { AppShell } from "./components/shell/AppShell";
import { TooltipProvider } from "./components/ui/tooltip";
import { Skeleton } from "./components/ui/skeleton";
import { DataContext } from "./data/context";
import { buildModel, type MatchModel } from "./data/model";
import { ReplaySource } from "./data/ReplaySource";
import type { StreamSource } from "./data/StreamSource";
import { useT } from "./lib/i18n";
import { seek, select, setPlaying, useReplay } from "./state/replay";
import { motionReduced, setSetting, useSettings } from "./state/settings";
import { LANGS, type Lang } from "./types/ui";

const LivePage = lazy(() => import("./features/live/LivePage"));
const TeamsPage = lazy(() => import("./features/teams/TeamsPage"));
const PlayersPage = lazy(() => import("./features/players/PlayersPage"));
const TechPage = lazy(() => import("./features/tech/TechPage"));

function Loading() {
  const { t } = useT();
  return (
    <div className="grid grid-cols-1 gap-flow lg:grid-cols-12" aria-busy="true" data-state="loading">
      <p className="sr-only" role="status">
        {t("loading")}
      </p>
      <div className="flex flex-col gap-flow lg:col-span-8">
        <Skeleton className="h-[132px]" />
        <Skeleton className="h-[60px]" />
        <Skeleton className="aspect-[109/72] w-full" />
      </div>
      <div className="flex flex-col gap-flow lg:col-span-4">
        <Skeleton className="h-[170px]" />
        <Skeleton className="h-[170px]" />
        <Skeleton className="h-[170px]" />
      </div>
    </div>
  );
}

function Failed({ error }: { error: Error }) {
  const { t } = useT();
  return (
    <div role="alert" className="mx-auto max-w-xl rounded-2xl border border-block/40 bg-block-soft p-6">
      <h1 className="text-[17px] font-semibold">{t("load_error")}</h1>
      <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">{t("load_hint")}</p>
      <p className="mt-3 break-words font-mono text-[12px] text-ink-3">{error.message}</p>
    </div>
  );
}

function hashParams(): URLSearchParams {
  const q = window.location.hash.split("?")[1] ?? "";
  return new URLSearchParams(q);
}

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo(0, 0), [pathname]);
  return null;
}

function Pages({ model }: { model: MatchModel }) {
  return (
    <DataContext.Provider value={model}>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/live" element={<LivePage />} />
          <Route path="/teams" element={<TeamsPage />} />
          <Route path="/players" element={<PlayersPage />} />
          <Route path="/tech" element={<TechPage />} />
          <Route path="*" element={<Navigate to="/live" replace />} />
        </Routes>
      </Suspense>
    </DataContext.Provider>
  );
}

const DEFAULT_SOURCE = new ReplaySource();

export default function App({ source = DEFAULT_SOURCE }: { source?: StreamSource }) {
  const [state, setState] = useState<{ model: MatchModel | null; error: Error | null }>({ model: null, error: null });
  const reduced = useSettings((s) => motionReduced(s));
  useEffect(() => {
    const ctl = new AbortController();
    source
      .load(ctl.signal)
      .then((bundle) => {
        const model = buildModel(bundle);
        useReplay.setState({ duration: model.timeline.duration_sec });
        const q = hashParams();
        if (q.has("t")) seek(Number(q.get("t")));
        if (q.get("select")) select(q.get("select"));
        const lang = q.get("lang");
        if (lang && LANGS.includes(lang as Lang)) setSetting("lang", lang as Lang);
        setState({ model, error: null });
        if (q.get("play") === "1" && !motionReduced()) setPlaying(true);
      })
      .catch((error: Error) => {
        if (!ctl.signal.aborted) setState({ model: null, error });
      });
    return () => ctl.abort();
  }, [source]);
  useEffect(() => {
    if (state.model || state.error) document.body.dataset.ready = "1";
  }, [state]);
  const body = useMemo(
    () => (state.error ? <Failed error={state.error} /> : state.model ? <Pages model={state.model} /> : <Loading />),
    [state],
  );
  return (
    <MotionConfig reducedMotion={reduced ? "always" : "never"}>
      <LazyMotion features={domAnimation} strict>
        <TooltipProvider>
          <HashRouter>
            <ScrollTop />
            <AppShell>{body}</AppShell>
          </HashRouter>
        </TooltipProvider>
      </LazyMotion>
    </MotionConfig>
  );
}
