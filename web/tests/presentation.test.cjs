const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/bank/presentation.ts'), 'utf8');
const context = vm.createContext({ exports: {} });
vm.runInContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
const { matchingLayout, shuffled } = context.exports;
test('ordered matching keeps its left column in order while right choices vary across exposures', () => {
  const q = { question_id: 'ordered', matchingOrdered: true,
    matching_left: ['M1', 'M2', 'M3'], matching_right: ['alpha', 'beta', 'gamma'] };
  const right = new Set();
  for (let i = 0; i < 50; i++) {
    const exposure = { ...q, presentationSeed: `ordered-${i}` };
    const layout = matchingLayout(exposure);
    assert.deepEqual(Array.from(layout.left), q.matching_left);
    assert.deepEqual(Array.from(layout.right).sort(), [...q.matching_right].sort());
    assert.equal(JSON.stringify(layout), JSON.stringify(matchingLayout(exposure)));
    right.add(layout.right.join());
  }
  assert.ok(right.size > 1);
  assert.deepEqual(q.matching_left, ['M1', 'M2', 'M3']);
});
test('matching columns vary independently, retain values, and stay fixed during one exposure', () => {
  const q = { question_id: 'same-question', matching_left: ['L1', 'L2'], matching_right: ['R1', 'R2'] };
  const layouts = new Set();
  for (let i = 0; i < 200; i++) {
    const exposure = { ...q, presentationSeed: `exposure-${i}` };
    const first = matchingLayout(exposure);
    assert.equal(JSON.stringify(first), JSON.stringify(matchingLayout(exposure)));
    assert.deepEqual(Array.from(first.left).sort(), q.matching_left);
    assert.deepEqual(Array.from(first.right).sort(), q.matching_right);
    layouts.add(JSON.stringify(first));
  }
  assert.equal(layouts.size, 4, 'two choices must allow all four independent column arrangements');
});
test('larger matching layouts vary in both columns; sequence items are shuffled without changing values', () => {
  const q = { question_id: 'same', matching_left: ['a', 'b', 'c', 'd'], matching_right: ['w', 'x', 'y', 'z'] };
  const left = new Set(), right = new Set(), sequences = new Set();
  for (let i = 0; i < 100; i++) {
    const seed = `try-${i}`;
    const layout = matchingLayout({ ...q, presentationSeed: seed });
    left.add(layout.left.join()); right.add(layout.right.join());
    const sequence = shuffled(q.matching_left, seed);
    assert.deepEqual(Array.from(sequence).sort(), q.matching_left);
    assert.notDeepEqual(Array.from(sequence), q.matching_left);
    sequences.add(sequence.join());
  }
  assert.ok(left.size > 15 && right.size > 15 && sequences.size > 15);
  assert.deepEqual(q.matching_left, ['a', 'b', 'c', 'd']);
});
