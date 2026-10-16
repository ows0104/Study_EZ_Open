const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(file) {
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = vm.createContext({ exports: {}, require: name => {
    if (name.endsWith('/SlideImage')) return { SlideImage: () => null };
    if (name.endsWith('/BankSlides')) return { BankSlides: () => null };
    if (name.endsWith('/BankSourceNote')) return { BankSourceNote: () => null };
    if (name.endsWith('.css')) return {};
    if (name.startsWith('.')) {
      const target = path.resolve(path.dirname(file), name);
      return load(fs.existsSync(target + '.tsx') ? target + '.tsx' : target + '.ts');
    }
    return require(name);
  }});
  vm.runInContext(code, context);
  return context.exports;
}
const { AnswerPoints } = load(path.join(__dirname, '../src/bank/AnswerPoints.tsx'));
const { AnswerBody } = load(path.join(__dirname, '../src/bank/BankQuestion.tsx'));
const first = 'C. difficile와 e.g. 같은 약어와 0.5 mg/kg 같은 수치는 문장 중간에서 나누지 않고 원래 표기 그대로 보존한다.';
const second = '설명은 각 문장이 전하는 의미와 조건을 유지한 채 다음 줄로 이어지며, 후속 문장의 첫 줄에 들여쓰기를 적용한다.';
const third = '정답을 채점하는 핵심 표현은 문장이 나뉘어도 같은 위치에 강조하여 표시한다.';
const text = `${first} ${second} ${third}`;
const plain = html => html.replace(/<[^>]+>/g, '');
const render = props => renderToStaticMarkup(React.createElement(AnswerPoints, { readable: true, ...props }));
const question = { format: 'list', question_id: 'fixture', question: '', options: [], matching_left: [], matching_right: [] };
const answer = { answer: text, answerUnits: [], answerPairs: [], correctOrder: [], correctOptionIds: [], medicalReview: null, slides: [] };
const body = (q, a) => renderToStaticMarkup(React.createElement(AnswerBody, {
  question: { ...question, ...q }, answer: { ...answer, ...a },
}));

test('list siblings align from the first row and nested bullets keep their indentation', () => {
  const text = '1. **첫 항목**\n   - 하위 항목\n2. 다음 항목\n\t• 다른 하위 항목';
  const html = render({ text, units: ['첫 항목'] });
  assert.equal((html.match(/class="bank-readable-line is-list"/g) || []).length, 4);
  assert.ok(!html.includes('is-indented'));
  assert.ok(html.includes('margin-inline-start:1.5em'));
  assert.ok(html.includes('margin-inline-start:2em'));
  assert.equal(plain(html), text.replace(/\*\*/g, ''));
  assert.ok(html.includes('class="bank-answer-point">첫 항목</strong>'));
});

test('list format aligns unmarked and colon-labeled answer rows including the first row', () => {
  for (const text of ['첫 항목\n둘째 항목\n셋째 항목', '**분류 A**: 첫 항목\n분류 B: 둘째 항목\n  하위 설명']) {
    const html = body({ format: 'list' }, { answer: text });
    assert.ok(!html.includes('is-indented'));
    assert.equal(plain(html).replace(/\s/g, '').includes(text.replace(/\*\*/g, '').replace(/\s/g, '')), true);
  }
});

test('list format aligns unmarked question rows including the first row', () => {
  const { QuestionBody } = load(path.join(__dirname, '../src/bank/BankQuestion.tsx'));
  const html = renderToStaticMarkup(React.createElement(QuestionBody, {
    question: { ...question, question: '분류 A: 첫 조건\n분류 B: 둘째 조건\n  하위 조건' },
    answer: null, picked: new Set(), onPick: () => {},
  }));
  assert.ok(!html.includes('is-sentence') && !html.includes('is-item'));
  assert.ok(html.includes('margin-inline-start:1em'));
});

test('explicit list rows keep long sentences within their own item', () => {
  const html = render({ text: `1. ${first} ${second}\n2. ${third}` });
  assert.equal((html.match(/class="bank-readable-line is-list"/g) || []).length, 2);
});

test('list question stems retain sibling and nested row layout with cloze answers', () => {
  const { BankStem } = load(path.join(__dirname, '../src/bank/BankStem.tsx'));
  const html = renderToStaticMarkup(React.createElement(BankStem, {
    text: '1. {{c1}}\n  - {{c2}}\n2. **항목**', cloze: true, answerUnits: ['답 하나', '답 둘'],
  }));
  assert.equal((html.match(/class="bank-stem-line is-list"/g) || []).length, 3);
  assert.ok(html.includes('margin-inline-start:1em'));
  assert.ok(!html.includes('is-sentence'));
  assert.ok(html.indexOf('답 하나') < html.indexOf('답 둘'));
});

test('long answers use sentence rows without changing the text or splitting abbreviations and decimals', () => {
  const html = render({ text });
  assert.equal((html.match(/class="bank-readable-line/g) || []).length, 3);
  assert.equal((html.match(/class="bank-readable-line is-indented"/g) || []).length, 2);
  assert.equal(plain(html), text);
  assert.ok(html.includes(first));
});

test('cross-sentence scoring and bold retain emphasis on both sides of each line break', () => {
  const bold = render({ text: `**${text}**` });
  assert.equal((bold.match(/<strong>/g) || []).length, 3);
  assert.equal(plain(bold), text);
  const scored = render({ text, units: [text] });
  assert.equal((scored.match(/class="bank-answer-point"/g) || []).length, 3);
  assert.equal(plain(scored), text);
  const keyword = render({ text, units: ['0.5 mg/kg', '핵심 표현'] });
  assert.ok(keyword.includes('class="bank-answer-point">0.5 mg/kg</strong>'));
  assert.ok(keyword.includes('class="bank-answer-point">핵심 표현</strong>'));
});

test('short answers keep their compact markup and explicit multiline text stays readable', () => {
  assert.equal(render({ text: '**짧은 정답**' }), '<strong>짧은 정답</strong>');
  assert.equal(render({ text: '한 문장이다. 짧은 설명이다.' }), '한 문장이다. 짧은 설명이다.');
  const multiline = '첫 줄이다.\r\n  **둘째 줄**이다.\n셋째 줄이다.';
  const html = render({ text: multiline });
  assert.equal((html.match(/class="bank-readable-line/g) || []).length, 3);
  assert.equal(plain(html), multiline.replace(/\*\*/g, ''));
  assert.ok(html.includes('<strong>둘째 줄</strong>'));
  assert.ok(!render({ text, readable: false }).includes('bank-readable'));
});

test('main answers, general explanations, short-answer context, and scoring items use sentence rows', () => {
  const main = body({}, { explanation: text });
  assert.equal((main.match(/class="bank-readable"/g) || []).length, 2);
  const basic = body({ format: 'basic' }, { answerUnits: ['핵심 표현'] });
  assert.ok(basic.includes('<summary>설명 보기</summary><p><span class="bank-readable">'));
  const unit = body({ format: 'basic' }, { answerUnits: [text] });
  assert.ok(unit.includes('<li><span class="bank-readable">'));
  assert.equal((unit.match(/class="bank-answer-point"/g) || []).length, 3);
});

test('legacy O/X and per-option explanations also use sentence rows', () => {
  const ox = body({ format: 'ox' }, { answer: 'X', answerUnits: [text] });
  assert.ok(ox.includes('bank-ox-explanation'));
  assert.equal((ox.match(/class="bank-readable"/g) || []).length, 1);
  const choice = body({ format: 'mcq', options: [{ id: 'A', text: '보기 A' }] }, {
    answer: 'A', answerUnits: [`A: ${text}`], correctOptionIds: ['A'],
  });
  assert.ok(choice.includes('bank-choice-explanation'));
  assert.equal((choice.match(/class="bank-readable"/g) || []).length, 1);
  assert.equal((choice.match(/class="bank-readable-line/g) || []).length, 3);
});


test('OX explanations color only authored key phrases blue, including legacy reasons', () => {
  const a = { answer: 'X', answerUnits: ['X'], explanation: '판단은 **구별 키워드**로 한다.' };
  const html = body({ format: 'ox' }, a);
  assert.ok(html.includes('판단은 <strong class="bank-answer-point">구별 키워드</strong>로 한다.'));
  assert.ok(!html.includes('class="bank-answer-point">X</strong>'));
  const legacy = body({ format: 'ox' }, { answer: 'X', answerUnits: ['X', '근거는 **키워드**다.'] });
  assert.ok(legacy.includes('<li>근거는 <strong class="bank-answer-point">키워드</strong>다.</li>'));
});

const { clozeDraft, clozeAnswer, editorQuestion, saveQuestion } = load(path.join(__dirname, '../src/bank/authoring.ts'));
test('cloze edits derive ordered repeated answers and transport only hidden markers', () => {
  assert.equal(clozeDraft('앞 {{c1}} 뒤 {{c2}} 반복 {{c1}}', ['A', '**B**', 'A']), '앞 {A} 뒤 {**B**} 반복 {A}');
  const saved = clozeAnswer('앞 {A} 뒤 {**B**} 반복 {A}');
  assert.equal(saved.question, '앞 {{c1}} 뒤 {{c1}} 반복 {{c1}}');
  assert.deepEqual(Array.from(saved.answer_units), ['A', '**B**', 'A']);
  assert.equal(saved.answer, '앞 A 뒤 **B** 반복 A');
  assert.equal(clozeAnswer('값 { }').answer_units[0], '');
});
test('one answer edit synchronizes basic, list and OX while preserving legacy explanations', () => {
  for (const format of ['basic', 'list', 'ox']) {
    const answer = format === 'list' ? 'A\nB' : format === 'ox' ? 'O' : '새 답';
    const saved = saveQuestion({ format, answer, answer_units: ['옛 답'] });
    assert.equal(saved.answer_units.join('|'), format === 'list' ? 'A|B' : answer);
  }
  const legacy = editorQuestion({ format: 'ox', question: '발문', answer: 'X', answer_units: ['X', '판단 근거'] });
  assert.equal(legacy.explanation, '판단 근거');
});
