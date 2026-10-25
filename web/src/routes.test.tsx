import { cleanup, render, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

// the pages themselves are not under test here: each lazy page renders its name
vi.mock("./features/home/HomePage", () => ({ default: () => <p>home</p> }));
vi.mock("./features/fixtures/FixturesPage", () => ({ default: () => <p>fixtures</p> }));
vi.mock("./features/hub/MatchHub", () => ({ default: () => <p>hub</p>, MatchLedger: () => <p>ledger</p> }));
vi.mock("./features/teams/TeamGrid", () => ({ default: () => <p>teams</p> }));
vi.mock("./features/teams/TeamBoard", () => ({ default: () => <p>board</p> }));
vi.mock("./features/players/PlayerDeck", () => ({ default: () => <p>players</p> }));
vi.mock("./features/players/PlayerConsole", () => ({ default: () => <p>player</p> }));
vi.mock("./features/tech/TechPage", () => ({ default: () => <p>tech</p> }));

const { AppRoutes } = await import("./routes");

function Where() {
  const l = useLocation();
  return <output data-where>{l.pathname + l.search}</output>;
}
const where = () => document.querySelector("[data-where]")?.textContent;

const at = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Suspense fallback={null}>
        <AppRoutes />
      </Suspense>
      <Where />
    </MemoryRouter>,
  );

afterEach(cleanup);

describe("old deep links", () => {
  const cases: [string, string, string][] = [
    ["/live", "/match/m_showcase", "hub"],
    ["/live?t=2760", "/match/m_showcase?t=2760", "hub"],
    ["/live?t=2760&select=ins_0009&lang=es&play=1", "/match/m_showcase?t=2760&select=ins_0009&lang=es&play=1", "hub"],
    ["/teams", "/teams", "teams"],
    ["/players", "/players", "players"],
    ["/players/AUR_08", "/players/AUR_08", "player"],
    ["/tech", "/tech", "tech"],
    ["/", "/", "home"],
    ["/match", "/fixtures", "fixtures"],
    ["/nowhere", "/", "home"],
  ];
  for (const [from, to, page] of cases) {
    it(`${from} -> ${to}`, async () => {
      const r = at(from);
      await waitFor(() => expect(r.getByText(page)).toBeTruthy());
      expect(where()).toBe(to);
    });
  }

  it("new routes resolve", async () => {
    for (const [path, page] of [
      ["/fixtures", "fixtures"],
      ["/match/m_001", "hub"],
      ["/match/m_001/ledger", "ledger"],
      ["/teams/AUR", "board"],
    ]) {
      const r = at(path!);
      await waitFor(() => expect(r.getByText(page!)).toBeTruthy());
      cleanup();
    }
  });
});
