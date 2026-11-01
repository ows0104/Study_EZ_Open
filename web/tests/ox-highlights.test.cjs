const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const { webcrypto, createHash } = require('node:crypto');
function load(file) {
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const ctx = vm.createContext({ exports: {}, crypto: webcrypto, TextEncoder, require: name => {
    if (name.startsWith('.')) return load(path.resolve(path.dirname(file), name) + '.ts');
    return require(name);
  }});
  vm.runInContext(compiled, ctx); return ctx.exports;
}
const { findOxHighlights } = load(path.join(__dirname, '../src/bank/useOxHighlights.ts'));
const { oxHighlights } = load(path.join(__dirname, '../src/bank/oxHighlights.ts'));
const digest = text => createHash('sha256').update(text).digest('hex');
const plain = ranges => Array.from(ranges, range => ({...range}));

test('exact hashes select UTF-16 ranges and text edits invalidate annotations', async () => {
  const text = '판단🙂: A가 아닌 B이다.';
  const start = text.indexOf('A가 아닌 B');
  const annotations = { [digest(text)]: [[start, start + 'A가 아닌 B'.length]] };
  const ranges = await findOxHighlights(text, annotations);
  assert.deepEqual(plain(ranges), [{start, end: start + 'A가 아닌 B'.length}]);
  assert.equal(text.slice(ranges[0].start, ranges[0].end), 'A가 아닌 B');
  assert.deepEqual(plain(await findOxHighlights(text + ' 변경', annotations)), []);
  assert.deepEqual(plain(await findOxHighlights(text.replace('아닌', '맞는'), annotations)), []);
});

test('missing and invalid ranges cannot color unrelated or out-of-bounds text', async () => {
  assert.deepEqual(plain(await findOxHighlights('')), []);
  assert.deepEqual(plain(await findOxHighlights('새로운 해설')), []);
  const text = '짧은 해설';
  const invalid = {[digest(text)]: [[-1, 2], [0, 100], [2, 1], [0, 0], [1.5, 3]]};
  assert.deepEqual(plain(await findOxHighlights(text, invalid)), []);
});

test('backfill contains only hashes and ordered positions for 133 segments and 300 spans', () => {
  assert.equal(Object.keys(oxHighlights).length, 133);
  assert.equal(Object.values(oxHighlights).reduce((n, ranges) => n + ranges.length, 0), 300);
  for (const [hash, ranges] of Object.entries(oxHighlights)) {
    assert.match(hash, /^[0-9a-f]{64}$/);
    assert.ok(ranges.length > 0);
    let previous = -1;
    for (const [start, end] of ranges) {
      assert.ok(Number.isInteger(start) && Number.isInteger(end) && start >= 0 && start < end);
      assert.ok(start > previous); previous = end;
    }
  }
});
