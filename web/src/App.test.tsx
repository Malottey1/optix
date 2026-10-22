import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";
import { ReplaySource } from "./data/ReplaySource";
import { seek } from "./state/replay";
import { setSetting } from "./state/settings";

const DATA = join(__dirname, "..", "public", "data");
const source = () =>
  new ReplaySource(
    "./data/",
    async (url: string) => new Response(readFileSync(join(DATA, url.split("/").pop()!), "utf8")),
  );
const ui = JSON.parse(readFileSync(join(DATA, "ui.json"), "utf8"));
const insights = readFileSync(join(DATA, "insights.jsonl"), "utf8")
  .split("\n")
  .filter(Boolean)
  .map((l) => JSON.parse(l));

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("Live Center", () => {
  it("renders the stream with a rewritten card, its reason and Before / After", async () => {
    window.location.hash = "#/live?t=2760";
    render(<App source={source()} />);
    const page = await screen.findByText((_, el) => el?.getAttribute("data-page") === "live", undefined, {
      timeout: 5000,
    });
    const iid = Object.keys(ui.rewrites).find(
      (id) => insights.find((i) => i.insight_id === id).clock.start_sec <= 2760,
    )!;
    const card = await waitFor(() => page.querySelector(`article[data-insight-id='${iid}']`) as HTMLElement);
    expect(card.dataset.status).toBe("revised");
    const ins = insights.find((i) => i.insight_id === iid);
    expect(within(card).getByText(ins.text.rendered.en.casual)).toBeTruthy();
    expect(within(card).getByText(ui.reasons.en[ui.rewrites[iid].rule_ids[0]])).toBeTruthy();
    fireEvent.click(within(card).getByRole("radio", { name: "Before" }));
    await waitFor(() => expect(within(card).getByText(ui.rewrites[iid].original.en.casual)).toBeTruthy());
  });

  it("switches language to the stream's translated sentence", async () => {
    window.location.hash = "#/live";
    render(<App source={source()} />);
    await screen.findByText((_, el) => el?.getAttribute("data-page") === "live", undefined, { timeout: 5000 });
    act(() => {
      seek(1e9);
      setSetting("lang", "fr");
    });
    const last = insights.at(-1);
    await waitFor(() => expect(screen.getAllByText(last.text.rendered.fr.casual).length).toBeGreaterThan(0));
    act(() => setSetting("lang", "en"));
  });
});
