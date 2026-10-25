// Copies the engine's output (written by `python -m agents.run_match`) into public/data/ so the
// built site can be served without Python. The files are copied byte for byte: never edit them by
// hand. ui.json holds the board, deck, ledger and reports; the stream itself is insights.jsonl,
// every verification attempt is claims.jsonl, and timeline.json has teams, goals and momentum.
// matches/ holds the fixture index and one recap file per played match (python -m agents.match_export).
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
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

const msrc = join(src, "matches");
if (!existsSync(join(msrc, "index.json"))) {
  console.error(`missing ${msrc}/index.json: run .venv/bin/python -m agents.match_export`);
  process.exit(1);
}
const mdst = join(dst, "matches");
mkdirSync(mdst, { recursive: true });
let total = 0;
const files = readdirSync(msrc)
  .filter((f) => f.endsWith(".json"))
  .sort();
for (const f of files) {
  copyFileSync(join(msrc, f), join(mdst, f));
  total += statSync(join(msrc, f)).size;
}
console.log(`matches/  ${files.length} files, ${(total / 1024).toFixed(1)} KB`);
