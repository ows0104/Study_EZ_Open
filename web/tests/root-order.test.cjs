// 순서 맞추기 화면(2026-11-18 ordering-screen): 앞면은 섞인 단계와 놓은 차례, 답면은 자리별 ✓/✕.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(file) {
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = vm.createContext({ exports: {}, require });
  vm.runInContext(js, context);
  return context.exports;
}
const { RootOrder, orderScore } = load(path.join(__dirname, '../src/bank/RootOrder.tsx'));
const items = [{ id: 'o3', text: 'DNA 복제' }, { id: 'o1', text: '세포 진입' }, { id: 'o4', text: '방출' }, { id: 'o2', text: '초기 전사' }];
const render = props => renderToStaticMarkup(React.createElement(RootOrder, { items, placed: [], disabled: false, onToggle() {}, ...props }));

test('front shows every shuffled step with a fixed number and no answer', () => {
  const html = render({});
  for (const [i, item] of items.entries()) assert.ok(html.includes(`<b>${i + 1}</b> ${item.text}`), item.text);
  assert.match(html, /아직 놓은 단계가 없습니다/);
  assert.doesNotMatch(html, /맞은 자리|✓|✕/);
});

test('placed steps get their position and appear in the placed row in order', () => {
  const html = render({ placed: ['o1', 'o2'] });
  assert.match(html, /aria-pressed="true"[^>]*><b>2<\/b> 세포 진입<span class="mq-order-at">1번째<\/span>/);
  assert.match(html, /aria-pressed="true"[^>]*><b>4<\/b> 초기 전사<span class="mq-order-at">2번째<\/span>/);
  assert.match(html, /<ol><li>세포 진입<\/li><li>초기 전사<\/li><\/ol>/);
  assert.match(html, /Backspace/);
});

test('answer compares each position with the correct order', () => {
  const html = render({ placed: ['o1', 'o3', 'o2'], correct: ['o1', 'o2', 'o3', 'o4'] });
  assert.match(html, /맞은 자리 1 \/ 전체 4/);
  assert.match(html, /class="is-correct"><span class="mq-order-mark"[^>]*>✓<\/span><span class="mq-order-right"><b>1<\/b> 세포 진입/);
  assert.match(html, /class="is-wrong">.*?<b>2<\/b> 초기 전사<\/span><span class="mq-order-mine">내 순서: DNA 복제/);
  assert.match(html, /class="is-empty">.*?<b>4<\/b> 방출<\/span><span class="mq-order-mine">내 순서: 비어 있음/);
  assert.doesNotMatch(html, /<button/);
});

test('score counts only exact positions', () => {
  assert.deepEqual({ ...orderScore(['a', 'b', 'c'], ['a', 'b', 'c']) }, { right: 3, total: 3 });
  assert.deepEqual({ ...orderScore(['b', 'a'], ['a', 'b', 'c']) }, { right: 0, total: 3 });
});
