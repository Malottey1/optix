// #/live: the showcase match replaying on a timeline, with the Focus Pitch, momentum, the
// Perimeter Lock and the stream of verified insight cards.
import { html, React } from "../lib/html.js";
import { EvidenceDrawer, Feed } from "../components/Insights.js";
import { FocusPitch, Momentum, PerimeterLock, Scoreboard, Transport } from "../components/LiveWidgets.js";

export function LivePage({ data }) {
  const [drawer, setDrawer] = React.useState(null);
  return html`<div class="stack-gap grid grid-cols-1 lg:grid-cols-12" data-page="live">
    <h1 class="sr-only">Live Center</h1>
    <div class="stack-gap flex min-w-0 flex-col lg:col-span-8">
      <${Scoreboard} data=${data} />
      <${Transport} data=${data} />
      <${FocusPitch} data=${data} />
      <div class="stack-gap grid grid-cols-1 items-start md:grid-cols-2">
        <${Momentum} data=${data} />
        <${PerimeterLock} data=${data} />
      </div>
    </div>
    <div class="min-w-0 lg:col-span-4">
      <div class="lg:sticky lg:top-[84px] lg:max-h-[calc(100vh-100px)] lg:overflow-y-auto lg:rounded-2xl">
        <${Feed} data=${data} onEvidence=${setDrawer} />
      </div>
    </div>
    <${EvidenceDrawer} data=${data} id=${drawer} onClose=${() => setDrawer(null)} />
  </div>`;
}
