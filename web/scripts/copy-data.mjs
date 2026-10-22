// Copies the engine's output (written by `python -m agents.run_match`) into public/data/ so the
// built site can be served without Python. The files are copied byte for byte: never edit them by
// hand. ui.json holds the board, deck, ledger and reports; the stream itself is insights.jsonl,
// every verification attempt is claims.jsonl, and timeline.json has teams, goals and momentum.
import { copyFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "out");
const dst = join(here, "..", "public", "data");
const FILES = ["ui.json", "insights.jsonl", "claims.jsonl", "timeline.json"];

mkdirSync(dst, { recursive: true });
for (const f of FILES) {
  const from = join(src, f);
  if (!existsSync(from)) {
    console.error(
      `missing ${from}: run .venv/bin/python -m agents.run_match --match m_showcase --out out/insights.jsonl`,
    );
    process.exit(1);
  }
  copyFileSync(from, join(dst, f));
  console.log(`${f}  ${(statSync(from).size / 1024).toFixed(1)} KB`);
}
