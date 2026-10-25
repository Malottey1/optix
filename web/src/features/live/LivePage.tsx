// #/live: the showcase match replaying on a timeline, with the Focus Pitch, the rhythm pulse,
// momentum, the Perimeter Lock, the territorial-stress gauges, shot quality and the stream of
// verified insight cards.
// Layout: phone = one column (pitch, stream, widgets); 1024px+ = pitch and widgets left, stream
// right; 1536px+ = pitch | widgets | stream; 1600px+ (`wide`, the 1080p demo screen) = the rhythm
// strip across the top under the scrubber (same time axis), then pitch | Perimeter Lock, gauges,
// momentum | shot quality over the stream, with every Live visual above the fold at 1600x900 and
// 1920x1080 (checked by tools/check_web.check_first_screen).
import { useState } from "react";
import { useT } from "../../lib/i18n";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { Feed } from "./Feed";
import { RhythmPulse, StressGauges } from "./Flow";
import { FocusPitch } from "./FocusPitch";
import { LiveShots } from "./LiveShots";
import { Momentum } from "./Momentum";
import { PerimeterLock } from "./PerimeterLock";
import { Scoreboard } from "./Scoreboard";
import { Transport } from "./Transport";

export default function LivePage() {
  const { t } = useT();
  const [drawer, setDrawer] = useState<string | null>(null);
  return (
    <div className="flex flex-col gap-flow" data-page="live">
      <h1 className="sr-only">{t("nav_live_long")}</h1>
      <Scoreboard />
      <Transport />
      <div className="grid grid-cols-1 items-start gap-flow lg:grid-cols-12 wide:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,1.05fr)] wide:grid-rows-[auto_auto_auto_1fr]">
        <div className="flex min-w-0 flex-col gap-flow lg:col-span-8 lg:col-start-1 lg:row-start-1 2xl:col-span-6 wide:contents">
          <div className="min-w-0 wide:col-start-1 wide:row-span-3 wide:row-start-2">
            <FocusPitch />
          </div>
          <div className="min-w-0 wide:col-span-3 wide:col-start-1 wide:row-start-1">
            <RhythmPulse />
          </div>
        </div>
        <div className="min-w-0 lg:sticky lg:top-[100px] lg:col-span-4 lg:col-start-9 lg:row-span-2 lg:row-start-1 2xl:col-span-3 2xl:col-start-10 2xl:row-span-1 wide:static wide:col-span-1 wide:col-start-3 wide:row-span-2 wide:row-start-3">
          <Feed onEvidence={setDrawer} />
        </div>
        <div className="grid min-w-0 grid-cols-1 items-start gap-flow md:grid-cols-2 lg:col-span-8 lg:col-start-1 lg:row-start-2 2xl:col-span-3 2xl:col-start-7 2xl:row-start-1 2xl:grid-cols-1 wide:contents">
          <div className="min-w-0 wide:col-start-2 wide:row-start-2">
            <PerimeterLock />
          </div>
          <div className="min-w-0 wide:col-start-2 wide:row-start-4">
            <Momentum />
          </div>
          <div className="min-w-0 wide:col-start-2 wide:row-start-3">
            <StressGauges />
          </div>
          <div className="min-w-0 wide:col-start-3 wide:row-start-2">
            <LiveShots />
          </div>
        </div>
      </div>
      <EvidenceDrawer id={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
