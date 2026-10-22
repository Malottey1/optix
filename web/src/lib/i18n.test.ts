import { describe, expect, it } from "vitest";
import { LANGS } from "../types/ui";
import { STRINGS } from "./i18n";

describe("interface strings", () => {
  it("every language has every key and no string carries a number", () => {
    const keys = Object.keys(STRINGS.en).sort();
    for (const lang of LANGS) {
      expect(Object.keys(STRINGS[lang]).sort()).toEqual(keys);
      for (const [k, v] of Object.entries(STRINGS[lang])) {
        expect(v.trim(), `${lang}.${k}`).not.toBe("");
        // the load hint names a CLI command; every other string is free of digits
        if (k !== "load_hint") expect(/\d/.test(v), `${lang}.${k}: ${v}`).toBe(false);
      }
    }
  });

  it("never uses prediction or betting language", () => {
    const all = LANGS.flatMap((l) => Object.values(STRINGS[l])).join(" ");
    expect(all).not.toMatch(/predict|will win|betting|odds|wager|forecast/i);
  });
});
