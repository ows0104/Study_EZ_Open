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
const { AnswerBody, QuestionBody, choiceScore } = load(path.join(__dirname, '../src/bank/BankQuestion.tsx'));
const question = { format: 'basic', question_id: 'q1', question: '', options: [], matching_left: [], matching_right: [] };
const answer = { answer: '', answerUnits: [], answerPairs: [], correctOrder: [], correctOptionIds: [], medicalReview: null, slides: [] };
test('comparison stems use four indented rows and keep all eight blank answers in order', () => {
  const text = 'Clindamycin과 vancomycin을 같은 약동학 기준으로 비교하여 빈칸을 채우시오. 경구흡수: clindamycin은 {{c1}}, vancomycin은 {{c1}}. 세포 내 침투: clindamycin은 {{c1}}, vancomycin은 {{c1}}. 주요 처리 경로: clindamycin은 {{c1}}, vancomycin은 {{c1}}. 신기능 저하 시: clindamycin은 대개 {{c1}}, vancomycin은 {{c1}}.';
  const q = { ...question, format: 'cloze', question: text };
  const props = { question: q, answer: null, picked: new Set(), onPick: () => {} };
  const hidden = renderToStaticMarkup(React.createElement(QuestionBody, props));
  assert.equal((hidden.match(/class="bank-stem-line is-item"/g) || []).length, 4);
  assert.deepEqual([...hidden.matchAll(/\[ (\d+) \]/g)].map(m => Number(m[1])), [1,2,3,4,5,6,7,8]);
  const units = Array.from({ length: 8 }, (_, i) => `답${i + 1}`);
  const shown = renderToStaticMarkup(React.createElement(QuestionBody, { ...props, answer: { ...answer, answerUnits: units } }));
  assert.equal((shown.match(/class="bank-stem-line is-item"/g) || []).length, 4);
  assert.deepEqual([...shown.matchAll(/class="bank-answer-point">(.*?)<\/strong>/g)].map(m => m[1]), units);
  assert.equal(shown.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim(),
    text.replace(/\{\{c1\}\}/g, () => units.shift()));
});

test('explicit multiline stems retain emphasis and blank order, including old cloze numbers', () => {
  const html = renderToStaticMarkup(React.createElement(QuestionBody, {
    question: { ...question, format: 'cloze', question: '비교하시오.\r\n  **기준 A**: {{c2}}.\r\n  기준 B: {{c1}}.' },
    answer: null, picked: new Set(), onPick: () => {},
  }));
  assert.equal((html.match(/class="bank-stem-line is-item"/g) || []).length, 2);
  assert.ok(html.includes('<strong>기준 A</strong>'));
  assert.deepEqual([...html.matchAll(/\[ (\d+) \]/g)].map(m => m[1]), ['1', '2']);
});

test('long Korean stems separate sentences without splitting decimals or English abbreviations', () => {
  const { stemLines } = load(path.join(__dirname, '../src/bank/BankStem.tsx'));
  const first = 'C. difficile, S. aureus와 e.g. 표기를 그대로 유지하고 0.5 mg/kg 조건을 확인한다.';
  const second = '제시된 조건을 충분히 검토한 다음 각 항목에 해당하는 관계를 설명하고 서로 다른 결과가 나타나는 이유를 판단하시오.';
  const last = '다음 중 이 모든 조건에 해당하지 **않는 것은**?';
  const lines = stemLines(`${first} ${second} ${last}`);
  assert.deepEqual(Array.from(lines, line => line.text), [first, second, last]);
  assert.ok(lines[1].indented && lines[2].indented);
  assert.equal(stemLines('조건을 확인한다. 옳은 것은?').length, 1);
});

const choiceQuestion = { ...question, format: 'multi_select', options: ['A', 'B', 'C', 'D'].map(id => ({ id, text: `보기 ${id}` })) };
const choiceAnswer = { ...answer, correctOptionIds: ['A', 'C'] };
test('multiple choice needs the entire answer set, with neither omissions nor extras', () => {
  for (const [ids, correct, missed, wrong, allCorrect] of [
    [[], 0, 2, 0, false], [['A'], 1, 1, 0, false], [['C'], 1, 1, 0, false],
    [['C', 'A'], 2, 0, 0, true], [['A', 'B'], 1, 1, 1, false],
    [['A', 'B', 'C'], 2, 0, 1, false], [['B', 'D'], 0, 2, 2, false],
    [['A', 'B', 'C', 'D'], 2, 0, 2, false],
  ]) {
    assert.deepEqual(JSON.parse(JSON.stringify(choiceScore(choiceQuestion, choiceAnswer, new Set(ids)))),
      { correct, missed, wrong, allCorrect }, `selected ${ids}`);
  }
});

test('revealed options distinguish correct picks, missed answers, and incorrect picks', () => {
  const html = renderToStaticMarkup(React.createElement(QuestionBody, {
    question: choiceQuestion, answer: choiceAnswer, picked: new Set(['A', 'B']), onPick: () => {},
  }));
  assert.match(html, /class="bank-option is-picked is-correct"[^>]*aria-pressed="true"[^>]*><b>A<\/b>.*?✓ 맞게 고른 정답/);
  assert.match(html, /class="bank-option is-picked is-wrong"[^>]*><b>B<\/b>.*?✕ 잘못 고른 선지/);
  assert.match(html, /class="bank-option is-missed"[^>]*aria-pressed="false"[^>]*><b>C<\/b>.*?! 빠뜨린 정답 · 미선택/);
  assert.match(html, /<b>D<\/b>.*?정답 아님 · 미선택/);
  assert.ok(html.includes('맞게 고른 정답 1개 · 빠뜨린 정답 1개 · 잘못 고른 선지 1개'));
  assert.ok(!html.includes('모두 맞았어요'));
});

test('choice feedback appears only after reveal and never uses stale personal answer keys', () => {
  for (const revealed of [null, { ...choiceAnswer, personalAnswer: true }]) {
    const html = renderToStaticMarkup(React.createElement(QuestionBody, {
      question: choiceQuestion, answer: revealed, picked: new Set(['A']), onPick: () => {},
    }));
    assert.ok(!html.includes('bank-option-result') && !html.includes('bank-choice-score'));
  }
  for (const key of [[], ['Z']]) {
    assert.equal(choiceScore(choiceQuestion, { ...choiceAnswer, correctOptionIds: key }, new Set(['A'])), null);
  }
  assert.equal(choiceScore(choiceQuestion, choiceAnswer, new Set(['Z'])), null);
});

test('single choice and blank selections cannot be mistaken for a correct answer', () => {
  const q = { ...choiceQuestion, format: 'mcq' }, a = { ...choiceAnswer, correctOptionIds: ['C'] };
  assert.equal(choiceScore(q, a, new Set(['A'])).allCorrect, false);
  assert.equal(choiceScore(q, a, new Set(['C'])).allCorrect, true);
  const html = renderToStaticMarkup(React.createElement(QuestionBody, {
    question: choiceQuestion, answer: choiceAnswer, picked: new Set(), onPick: () => {},
  }));
  assert.ok(html.includes('선택한 답이 없어요.') && !html.includes('모두 맞았어요'));
  assert.equal((html.match(/class="bank-option is-missed"/g) || []).length, 2);
});
const render = (changes, format = 'list', tier = 'Advanced') => renderToStaticMarkup(React.createElement(AnswerBody, {
  question: { ...question, format, tier }, answer: { ...answer, ...changes },
}));

test('short answers show scoring items with prose collapsed in every tier', () => {
  const sentence = '시간에 따른 약물 농도 변화인 약동학과 농도에 따른 반응인 약력학을 함께 알아야 한다.';
  const units = ['시간→농도인 약동학', '농도→반응인 약력학'];
  for (const tier of ['Core', 'Advanced', 'Optional']) {
    const html = render({ answer: sentence, answerUnits: units }, 'basic', tier);
    const mainAnswer = html.split('<details')[0];
    assert.equal(mainAnswer, '<ul class="quiz-answer bank-short-answer"><li><strong class="bank-answer-point">시간→농도인 약동학</strong></li><li><strong class="bank-answer-point">농도→반응인 약력학</strong></li></ul>');
    assert.ok(!mainAnswer.includes(sentence));
    assert.ok(html.includes('<details class="bank-answer-context"><summary>설명 보기</summary>'));
    assert.ok(html.includes(sentence));
    assert.ok(!html.includes('bank-units'));
  }
});

test('Core single-item answers do not repeat identical prose; blank units use the original answer', () => {
  const single = render({ answer: '**AADC**', answerUnits: ['AADC', '  '] }, 'basic', 'Core');
  assert.ok(single.includes('bank-short-answer'));
  assert.ok(!single.includes('<details'));
  const fallback = render({ answer: '원래 정답', answerUnits: ['  '] }, 'basic', 'Core');
  assert.equal(fallback, '<p class="quiz-answer">원래 정답</p>');
});

test('short answers do not replace O/X explanations, cloze sentences, or choice answers', () => {
  for (const format of ['ox', 'cloze', 'matching', 'sequence', 'mcq', 'list']) {
    assert.ok(!render({ answer: 'O', answerUnits: ['판단 기준'] }, format, 'Core').includes('bank-short-answer'));
  }
});

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

test('O/X alone is not displayed as an explanation', () => {
  const html = render({ answer: 'O', answerUnits: ['O'] }, 'ox');
  assert.ok(html.includes('이 문항에 등록된 해설이 없습니다.'));
});

test('retired experiment hints are not shown before or after revealing the answer', () => {
  const q = { ...question, hint: 'apical/luminal membrane의 방향을 떠올려 보세요.' };
  const props = { question: q, answer: null, picked: new Set(), onPick: () => {} };
  const html = renderToStaticMarkup(React.createElement(QuestionBody, props));
  assert.ok(!html.includes('힌트 보기') && !html.includes(q.hint));
  const shown = renderToStaticMarkup(React.createElement(QuestionBody, { ...props, answer }));
  assert.ok(!shown.includes('힌트 보기') && !shown.includes(q.hint));
});

test('general explanations are separate from scoring and work for basic, cloze and O/X', () => {
  for (const format of ['basic', 'cloze', 'ox']) {
    const html = render({ answer: 'X', answerUnits: ['X'], explanation: '구체적인 반례와 올바른 기전' }, format);
    assert.ok(html.includes('<h2>해설</h2><p>구체적인 반례와 올바른 기전</p>'));
    assert.equal((html.match(/<h2>해설<\/h2>/g) || []).length, 1);
    assert.ok(!html.includes('이 문항에 등록된 해설이 없습니다.'));
  }
  assert.ok(!render({ explanation: '오래된 설명', personalAnswer: true }).includes('오래된 설명'));
});

test('missing O/X explanation is explicit, without an empty panel for other formats', () => {
  assert.ok(render({ answer: 'X', answerUnits: ['  '] }, 'ox').includes('등록된 해설이 없습니다.'));
  assert.ok(!render({ answer: '답' }).includes('bank-ox-explanation'));
});

test('choice explanations include every distractor, preserve emphasis, and follow option order', () => {
  for (const format of ['mcq', 'multi_select']) {
    const html = renderToStaticMarkup(React.createElement(AnswerBody, {
      question: { ...question, format, options: [{ id: 'A', text: '표적 A' }, { id: 'B', text: '표적 B' }] },
      answer: { ...answer, answer: 'A: 참 — 수용체를 억제한다.', correctOptionIds: ['A'],
        answerUnits: ['B: 거짓 — **효소**를 억제하며 수용체에는 작용하지 않는다.', 'A: 참 — 수용체를 억제한다.'] },
    }));
    const section = html.slice(html.indexOf('<section'));
    assert.ok(section.includes('aria-label="선지별 해설"><h2>선지별 해설</h2>'));
    assert.ok(section.includes('거짓 — <strong>효소</strong>를 억제하며 수용체에는 작용하지 않는다.'));
    assert.ok(section.indexOf('<b>A</b>') < section.indexOf('<b>B</b>'));
    assert.ok(section.includes('참 — 수용체를 억제한다.'));
    assert.equal(section.split('효소').length - 1, 1);
    assert.ok(!html.includes('bank-units'));
  }
});

test('negative choice stems keep truth explanations separate from the answer key', () => {
  const html = renderToStaticMarkup(React.createElement(AnswerBody, {
    question: { ...question, format: 'mcq', question: '옳지 않은 것은?', options: [{ id: 'A', text: '명제 A' }, { id: 'AA', text: '명제 AA' }] },
    answer: { ...answer, correctOptionIds: ['AA'], answerUnits: ['**A:** 참 — 조건을 충족한다.', 'AA: 거짓 — 조건을 충족하지 않는다.'] },
  }));
  assert.ok(html.includes('<b>A</b> 명제 A<span class="bank-note"> · 정답이 아닌 선지</span>'));
  assert.ok(html.includes('<b>AA</b> 명제 AA<span class="bank-note"> · 정답 선지</span>'));
  assert.ok(html.includes('<p>참 — 조건을 충족한다.</p>'));
  assert.ok(html.includes('<p>거짓 — 조건을 충족하지 않는다.</p>'));
});

test('legacy choices retain unlinked explanation text and explicitly show missing explanations', () => {
  const html = renderToStaticMarkup(React.createElement(AnswerBody, {
    question: { ...question, format: 'mcq', options: [{ id: '1', text: '보기 1' }, { id: '2', text: '보기 2' }] },
    answer: { ...answer, answer: '원래 정답', answerUnits: ['1：참 — 기존 근거', '기존의 추가 설명'] },
  }));
  assert.ok(html.includes('원래 정답'));
  assert.ok(html.includes('참 — 기존 근거'));
  assert.equal(html.split('이 선지에 등록된 해설이 없습니다.').length - 1, 1);
  assert.equal(html.split('기존의 추가 설명').length - 1, 1);
});

test('personal choice answers do not show stale original option explanations', () => {
  const html = render({ answer: '개인 수정한 정답', personalAnswer: true }, 'mcq');
  assert.ok(html.includes('개인 수정한 정답'));
  assert.ok(!html.includes('bank-choice-explanation'));
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

test('four repeated cloze markers reveal four answers in their original order', () => {
  const props = {
    question: { ...question, format: 'cloze', question: '흡수 {{c1}}, F {{c1}}; 흡수 {{c1}}, F {{c1}}.' },
    picked: new Set(), onPick: () => {},
  };
  const hidden = renderToStaticMarkup(React.createElement(QuestionBody, { ...props, answer: null }));
  assert.equal((hidden.match(/class="bank-blank"/g) || []).length, 4);
  const revealed = renderToStaticMarkup(React.createElement(QuestionBody, {
    ...props, answer: { ...answer, answerUnits: ['감소', '감소', '증가', '증가'] },
  }));
  assert.deepEqual([...revealed.matchAll(/class="bank-answer-point">([^<]+)</g)].map(match => match[1]),
    ['감소', '감소', '증가', '증가']);
});
