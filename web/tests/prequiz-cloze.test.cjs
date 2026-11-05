const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(file, mocks = {}) {
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = vm.createContext({ exports: {}, require: name => {
    if (name in mocks) return mocks[name];
    if (!name.startsWith('.')) return require(name);
    const target = path.resolve(path.dirname(file), name);
    return load(fs.existsSync(target + '.tsx') ? target + '.tsx' : target + '.ts', mocks);
  }});
  vm.runInContext(code, context);
  return context.exports;
}
const file = name => path.join(__dirname, '../src/lecture', name + '.tsx');
const { PreQuizCloze } = load(file('PreQuizCloze'));
const { PreQuizText } = load(file('PreQuizText'));
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const plain = html => html.replace(/<[^>]+>/g, '');
const front = '**개념**: [____]을 이해하고, [기준]을 비교한다.';
const parts = [{ text: '**개념**: ' }, { text: '첫째 답', blank: true }, { text: '을 이해하고, ' },
  { text: '둘째 답', blank: true }, { text: '을 비교한다.' }];

test('unrevealed fronts and legacy cards preserve exactly the existing markup', () => {
  for (const text of [front, '첫 문장이다. 둘째 문장이다.\n힌트 [용어]', 'C. difficile 0.5 mg/kg']) {
    assert.equal(render(PreQuizCloze, { text }), render(PreQuizText, { text }));
    assert.equal(render(PreQuizCloze, { text, parts: [] }), render(PreQuizText, { text }));
  }
  assert.doesNotMatch(render(PreQuizCloze, { text: front }), /첫째 답|둘째 답|bank-answer-point/);
});
test('revealed answers replace only their own blanks in occurrence order', () => {
  const html = render(PreQuizCloze, { text: front, parts });
  assert.equal(plain(html), '개념: 첫째 답을 이해하고, 둘째 답을 비교한다.');
  assert.match(html, /class="bank-answer-point">첫째 답<\/strong>/);
  assert.match(html, /class="bank-answer-point">둘째 답<\/strong>/);
  assert.doesNotMatch(html, /\[____\]|\[기준\]|\uE000/);
});
test('bold spans across blanks, repeated answers, multiline answers and paragraphs survive', () => {
  const rich = [{ text: '**앞 ' }, { text: '동일', blank: true }, { text: ' 뒤**다. 다음 문장이다.\n\n' },
    { text: '동일\n다음 줄', blank: true }, { text: '\n끝.' }];
  const html = render(PreQuizCloze, { text: '', parts: rich });
  assert.match(html, /<strong>앞 <strong class="bank-answer-point">동일<\/strong> 뒤<\/strong>/);
  assert.equal((html.match(/class="prequiz-text-paragraph"/g) || []).length, 3);
  assert.ok(plain(html).includes('동일\n다음 줄\n끝.'));
});
test('answers escape HTML, preserve scientific notation and cannot collide with internal markers', () => {
  const text = '<script>bad()</script> C. difficile 0.5 mg/kg \uE000a literal';
  const html = render(PreQuizCloze, { text: '', parts: [{ text, blank: true }] });
  assert.match(html, /&lt;script&gt;bad\(\)&lt;\/script&gt;/);
  assert.ok(html.includes('C. difficile 0.5 mg/kg \uE000a literal'));
  assert.doesNotMatch(html, /<script>/);
});

function difficult(answers, saved = {}) {
  let state = 0;
  const { PreQuizDifficult } = load(file('PreQuizDifficult'), {
    react: { ...React, useEffect() {}, useState(initial) { return [state++ === 0 ? saved : initial, () => {}]; } },
    './Quiz': { WhyAsked: () => null },
    '../feedback/FeedbackButton': { FeedbackButton: () => null },
    '../api': { api() { throw new Error('Unexpected API request during render'); } },
  });
  return render(PreQuizDifficult, { base: '/demo/prequiz', items: [{ itemId: 'c1', qtype: 'cloze', stem: front }],
    answers, onReview() {}, reportContext: { subject: 'test', runId: 'demo', title: 'Test' } });
}
test('difficult cards fill blanks from immediate and restored saved answers', () => {
  const answer = { answer: 'Separate answer stays', explanation: '', lectureFocus: '', clozeParts: parts };
  for (const html of [difficult({ c1: answer }), difficult({}, { c1: answer })]) {
    assert.match(html, /<h4>.*class="bank-answer-point">첫째 답<\/strong>/);
    assert.ok(html.includes('Separate answer stays'));
    assert.doesNotMatch(html, /\[____\]/);
  }
  assert.ok(difficult({}, { c1: { answer: 'Legacy' } }).includes('[____]'));
});
