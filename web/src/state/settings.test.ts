import { describe, expect, it, vi } from "vitest";
import { DEFAULTS, sanitize } from "./settings";

describe("settings", () => {
  it("sanitizes anything read from storage", () => {
    expect(sanitize({ lang: "de", density: "tiny", reducedMotion: "yes" })).toEqual(DEFAULTS);
    expect(sanitize({ lang: "fr", density: "compact", highContrast: true }).lang).toBe("fr");
  });

  it("module loads and writes even when storage throws", async () => {
    const original = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("blocked");
      },
    });
    vi.resetModules();
    const mod = await import("./settings");
    expect(() => mod.setSetting("lang", "es")).not.toThrow();
    expect(mod.useSettings.getState().lang).toBe("es");
    if (original) Object.defineProperty(window, "localStorage", original);
  });
});
