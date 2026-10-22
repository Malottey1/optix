// Optix dashboard entry: loads the verified stream and engine outputs, then routes by hash.
// React with htm tagged templates, native ES modules from ./vendor/, no build step.
import { createRoot } from "react-dom/client";
import { html, React } from "./lib/html.js";
import { loadAll } from "./lib/data.js";
import { t } from "./lib/i18n.js";
import { replay, seek, select, setPlaying } from "./lib/replay.js";
import { parseHash, useRoute } from "./lib/router.js";
import { motionReduced, setSetting, LANGS } from "./lib/settings.js";
import { Shell } from "./components/Shell.js";
import { Skeleton } from "./components/ui.js";
import { LivePage } from "./pages/Live.js";
import { TeamsPage } from "./pages/Teams.js";
import { PlayersPage } from "./pages/Players.js";
import { TechPage } from "./pages/Tech.js";

const PAGES = { live: LivePage, teams: TeamsPage, players: PlayersPage, tech: TechPage };

function Loading() {
  return html`<div class="stack-gap grid grid-cols-1 lg:grid-cols-12" aria-busy="true" data-state="loading">
    <p class="sr-only" role="status">${t("loading")}</p>
    <div class="stack-gap flex flex-col lg:col-span-8">
      <${Skeleton} className="h-[110px]" /><${Skeleton} className="h-[56px]" /><${Skeleton} className="aspect-[109/72] w-full" />
    </div>
    <div class="stack-gap flex flex-col lg:col-span-4">
      <${Skeleton} className="h-[160px]" /><${Skeleton} className="h-[160px]" /><${Skeleton} className="h-[160px]" />
    </div>
  </div>`;
}

function Failed({ error }) {
  return html`<div role="alert" class="mx-auto max-w-xl rounded-2xl border border-block/40 bg-block-soft p-6">
    <h1 class="text-[17px] font-semibold">${t("load_error")}</h1>
    <p class="mt-2 text-[13.5px] text-ink-2">${t("load_hint")}</p>
    <p class="mt-2 font-mono text-[12px] text-ink-3">${String(error && error.message)}</p>
  </div>`;
}

function App() {
  const { route } = useRoute();
  const [state, setState] = React.useState({ data: null, error: null });
  React.useEffect(() => {
    loadAll().then((data) => {
      replay.set({ ...replay.get(), duration: data.timeline.duration_sec });
      // view options (screenshots, tests): #/live?t=2760&select=ins_0011&lang=es&play=1
      const q = parseHash().params;
      if (q.has("t")) seek(+q.get("t"));
      if (q.get("select")) select(q.get("select"));
      if (LANGS.includes(q.get("lang"))) setSetting("lang", q.get("lang"));
      setState({ data, error: null });
      if (q.get("play") === "1" && !motionReduced()) setPlaying(true);
    }).catch((error) => setState({ data: null, error }));
  }, []);
  React.useEffect(() => {
    const main = document.getElementById("main");
    if (main && state.data) main.scrollIntoView({ block: "start" });
    window.scrollTo(0, 0);
  }, [route]);
  React.useEffect(() => {
    if (state.data || state.error) document.body.dataset.ready = "1";
  }, [state, route]);
  const Page = PAGES[route];
  return html`<${Shell} route=${route}>
    ${state.error ? html`<${Failed} error=${state.error} />` : state.data ? html`<${Page} data=${state.data} />` : html`<${Loading} />`}
  <//>`;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
