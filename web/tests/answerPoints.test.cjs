const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

function load(file) {
  const source = fs.readFileSync(file, 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = vm.createContext({ exports: {}, require: (name) => {
    if (name.endsWith('/SlideImage')) return { SlideImage: () => null };
    if (name.startsWith('.')) return load(path.resolve(path.dirname(file), name + '.tsx'));
    return require(name);
  } });
  vm.runInContext(js, context);
  return context.exports;
}
const { AnswerBody, QuestionBody } = load(path.join(__dirname, '../src/bank/BankQuestion.tsx'));
const question = { format: 'basic', question_id: 'q1', question: '', options: [], matching_left: [], matching_right: [] };
const answer = { answer: '', answerUnits: [], answerPairs: [], correctOrder: [], correctOptionIds: [], medicalReview: null, slides: [] };
const render = (changes, format = 'basic') => renderToStaticMarkup(React.createElement(AnswerBody, {
  question: { ...question, format }, answer: { ...answer, ...changes },
}));

test('points are blue inline, preserve context, and do not repeat below the answer', () => {
  const html = render({ answer: 'AChE를 억제하여 전달을 개선한다.', answerUnits: ['AChE'] });
  assert.equal(html, '<p class="quiz-answer"><strong class="bank-answer-point">AChE</strong>를 억제하여 전달을 개선한다.</p>');
});

test('shorthand points highlight only the keywords in the user-provided answer', () => {
  const sentence = '지용성 약물을 더 극성·수용성인 대사체로 바꾸어 배설하기 쉽게 만드는 것이다.';
  for (const text of [sentence, `**${sentence}**`]) {
    const html = render({ answer: text, answerUnits: ['**지용성→더 극성/수용성**', '**배설 용이**'] });
    const blue = [...html.matchAll(/<strong class="bank-answer-point">([^<]+)<\/strong>/g)].map((match) => match[1]);
    assert.deepEqual(blue, ['지용성', '더 극성·수용성', '배설하기 쉽게']);
    assert.ok(!html.includes('bank-units'));
    assert.equal(html.replace(/<[^>]+>/g, ''), sentence);
  }
});

test('full-answer bold does not color surrounding prose or unrelated words', () => {
  const html = render({ answer: '**표적은 AADC이며 말초에서 작용한다.**', answerUnits: ['AADC'] });
  assert.ok(html.includes('<strong>표적은 </strong><strong class="bank-answer-point">AADC</strong><strong>이며 말초에서 작용한다.</strong>'));
});

test('compound points can highlight separated keywords while preserving absent information', () => {
  const html = render({ answer: 'NMDA 수용체를 차단한다.', answerUnits: ['NMDA 차단', '강의 밖 조건'] });
  assert.ok(html.includes('<strong class="bank-answer-point">NMDA</strong> 수용체를 <strong class="bank-answer-point">차단</strong>한다.'));
  assert.ok(!html.includes('<li>NMDA 차단</li>'));
  assert.ok(html.includes('<li>강의 밖 조건</li>'));
});

test('case, spacing, and bold markup do not prevent an inline match', () => {
  const html = render({ answer: '**Viral DNA** polymerase가 중요하다.', answerUnits: ['viral DNA polymerase'] });
  assert.ok(!html.includes('bank-units'));
  assert.ok(!html.includes('**'));
  assert.ok(!html.includes('polymerase가 중요하다.</strong>'));
  assert.ok(html.includes('class="bank-answer-point"> polymerase</strong>가 중요하다.'));
});

test('overlapping and repeated points retain all answer text without duplicating it', () => {
  const html = render({ answer: 'NMDA receptor; NMDA.', answerUnits: ['NMDA', 'NMDA receptor'] });
  assert.equal(html.replace(/<[^>]+>/g, ''), 'NMDA receptor; NMDA.');
  assert.ok(!html.includes('bank-units'));
});

test('single O/X explanations and paraphrased points remain visible in blue', () => {
  const html = render({ answer: 'X', answerUnits: ['말초에서만 작용한다.'] }, 'ox');
  assert.ok(html.includes('aria-label="해설"><h2>해설</h2>'));
  assert.ok(html.includes('<li class="bank-answer-point">말초에서만 작용한다.</li>'));
});

test('O and X show every explanation once, including a single or multiline unit', () => {
  for (const binary of ['O', 'X']) {
    const units = ['판단의 **기준**이다.\n조건도 확인한다.', '예외를 구분한다.'];
    const html = render({ answer: binary, answerUnits: units }, 'ox');
    assert.ok(html.includes('<strong>기준</strong>이다.\n조건도 확인한다.'));
    assert.equal(html.split('예외를 구분한다.').length - 1, 1);
    assert.ok(!html.includes('bank-units'));
  }
});

test('O/X does not hide explanations that also occur in the answer', () => {
  const html = render({ answer: 'O', answerUnits: ['O'] }, 'ox');
  assert.ok(html.includes('<h2>해설</h2><ul><li class="bank-answer-point">O</li></ul>'));
});

test('missing O/X explanation is explicit, without an empty panel for other formats', () => {
  assert.ok(render({ answer: 'X', answerUnits: ['  '] }, 'ox').includes('등록된 해설이 없습니다.'));
  assert.ok(!render({ answer: '답' }).includes('bank-ox-explanation'));
});

test('short terms do not match inside other English words and text is escaped', () => {
  const html = render({ answer: '<script>scopolamine</script>', answerUnits: ['O'] });
  assert.ok(html.includes('&lt;script&gt;scopolamine&lt;/script&gt;'));
  assert.ok(html.includes('<li>O</li>'));
  assert.ok(!html.includes('<script>'));
});

test('revealed cloze blanks, matching pairs, and sequence answers are highlighted', () => {
  const html = renderToStaticMarkup(React.createElement(QuestionBody, {
    question: { ...question, format: 'cloze', question: '표적은 {{c1}}이다.' },
    answer: { ...answer, answerUnits: ['AADC'] }, picked: new Set(), onPick: () => {},
  }));
  assert.ok(html.includes('<strong class="bank-answer-point">AADC</strong>'));
  assert.ok(render({ answerPairs: [{ left: '약물', right: '표적' }] }, 'matching')
    .includes('<li class="bank-answer-point">'));
  assert.ok(render({ correctOrder: ['흡수', '분포'] }, 'sequence')
    .includes('class="bank-order bank-answer-point"'));
});
