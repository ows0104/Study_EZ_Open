// Verify the production browser merger with two real Quiz Bank APKG exports.
// node scripts/test-bank-bundle.mjs <first.apkg> <second.apkg>
import assert from "node:assert/strict";
import { readFile, writeFile, unlink } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import ts from "typescript";
import { unzipSync } from "fflate";
import initSqlJs from "sql.js";

const [first, second] = process.argv.slice(2);
assert(first && second, "Supply two exported APKG fixtures");
const require = createRequire(import.meta.url);
const wasm = require.resolve("sql.js/dist/sql-wasm.wasm");
const source = (await readFile(new URL("../src/bundle/apkg.ts", import.meta.url), "utf8"))
  .replace('import wasmUrl from "sql.js/dist/sql-wasm.wasm?url";', `const wasmUrl = ${JSON.stringify(wasm)};`);
const temporary = join(fileURLToPath(new URL(".", import.meta.url)), `.bank-bundle-${process.pid}.mjs`);
await writeFile(temporary, ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText);
try {
  const { mergeDecks } = await import(new URL(`.bank-bundle-${process.pid}.mjs`, import.meta.url));
  async function* parts() {
    for (const path of [first, second, first]) yield { label: path, bytes: new Uint8Array(await readFile(path)) };
  }
  const { blob, report } = await mergeDecks(parts());
  assert.deepEqual(report, { notes: 16, decks: 2, media: 2, duplicates: 8, mediaClashes: 0 });
  const zip = unzipSync(new Uint8Array(await blob.arrayBuffer()));
  const SQL = await initSqlJs({ locateFile: () => wasm });
  const db = new SQL.Database(zip["collection.anki2"]);
  try {
    assert.equal(db.exec("SELECT COUNT(*) FROM cards")[0].values[0][0], 16);
    assert.equal(db.exec("SELECT COUNT(DISTINCT guid) FROM notes")[0].values[0][0], 16);
    const media = JSON.parse(new TextDecoder().decode(zip.media));
    const names = new Set(Object.values(media));
    assert.equal(names.size, 2);
    for (const [fields] of db.exec("SELECT flds FROM notes")[0].values) {
      for (const match of fields.matchAll(/<img src="([^"]+)"/g)) assert(names.has(match[1]), `Missing image: ${match[1]}`);
    }
  } finally {
    db.close();
  }
  console.log("PASS: real exports merge into 2 decks / 16 cards / 2 images; repeated deck adds no duplicates");
} finally {
  await unlink(temporary);
}
