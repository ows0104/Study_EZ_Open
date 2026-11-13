// 족보 진입 화면의 범위 고르기와 채점(web/src/jokbo/selection.ts).  node --test web/tests/jokbo-selection.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(file) {
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = vm.createContext({ exports: {}, require });
  vm.runInContext(js, context);
  return context.exports;
}
const sel = load(path.join(__dirname, '../src/jokbo/selection.ts'));
// vm 안에서 만든 배열은 프로토타입이 달라 deepStrictEqual이 같다고 보지 않는다.
const plain = (x) => JSON.parse(JSON.stringify(x));

const item = (id, yearLabel, extra = {}) => ({ id, yearLabel, choices: ['a', 'b', 'c', 'd', 'e'], answers: [2],
  answerMode: 'one_of', answerStatus: 'key', ...extra });
const doc = {
  lecture: { eventId: 'e' },
  sections: [
    { kind: 'same', professors: ['방예지'], years: ['2025'], itemIds: ['s1'] },
    { kind: 'other', professors: ['김현제'], years: ['2023'], itemIds: ['o1'] },
    { kind: 'other', professors: ['석승혁'], years: ['2022', '2020'], itemIds: ['o2', 'o3', 'o4'] },
  ],
  items: [item('s1', '2025'), item('o1', '2023'), item('o2', '2022'), item('o3', '2020'), item('o4', '2020')],
};

test('다른 교수 연도는 「연도 교수」 버튼 하나씩, 최신부터', () => {
  const ys = sel.otherYears(doc);
  assert.deepEqual(plain(ys.map(y => y.label)), ['2023 김현제', '2022 석승혁', '2020 석승혁']);
  assert.deepEqual(plain(ys[2].itemIds), ['o3', 'o4']);
});

test('같은 교수만 / 다른 교수까지 + 고른 연도', () => {
  assert.deepEqual(plain(sel.pickItems(doc, 'same', new Set()).map(i => i.id)), ['s1']);
  const keys = sel.otherYears(doc).map(y => y.key);
  assert.deepEqual(plain(sel.pickItems(doc, 'more', new Set(keys)).map(i => i.id)), ['s1', 'o1', 'o2', 'o3', 'o4']);
  assert.deepEqual(plain(sel.pickItems(doc, 'more', new Set([keys[2]])).map(i => i.id)), ['s1', 'o3', 'o4']);
  // 「다른 교수까지」에서 연도를 다 끄면 같은 교수 문항만 남는다
  assert.deepEqual(plain(sel.pickItems(doc, 'more', new Set()).map(i => i.id)), ['s1']);
});

test('같은 교수 문항이 없으면 처음부터 다른 교수까지, 미상은 「교수 미상」', () => {
  const cbl = { ...doc, sections: [{ kind: 'unknown', professors: [], years: ['2025'], itemIds: ['s1'] }], items: [item('s1', '2025')] };
  assert.equal(sel.defaultScope(cbl), 'more');
  assert.equal(sel.defaultScope(doc), 'same');
  assert.equal(sel.otherYears(cbl)[0].label, '2025 교수 미상');
});

test('채점: one_of·all_of·전원 정답·답 없음', () => {
  assert.equal(sel.grade(item('x', '2025'), [2]), 'correct');
  assert.equal(sel.grade(item('x', '2025'), [3]), 'wrong');
  assert.equal(sel.grade(item('x', '2025', { answers: [3, 5], answerStatus: 'key-multiple' }), [5]), 'correct');
  const allOf = item('x', '2025', { answers: [3, 5], answerMode: 'all_of' });
  assert.equal(sel.needed(allOf), 2);
  assert.equal(sel.grade(allOf, [3]), 'wrong');
  assert.equal(sel.grade(allOf, [5, 3]), 'correct');
  assert.equal(sel.grade(item('x', '2025', { answers: [], answerStatus: 'all-correct' }), [1]), 'correct');
  assert.equal(sel.grade(item('x', '2025', { answers: [], answerStatus: 'missing' }), [1]), 'ungraded');
});
