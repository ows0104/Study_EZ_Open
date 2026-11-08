const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const ts = require('../node_modules/typescript');
const webRequire = createRequire(path.resolve(__dirname, '../package.json'));

function modules(now, mocks = {}) {
  const cache = new Map();
  class Clock extends Date {
    constructor(...args) { super(...(args.length ? args : [now])); }
    static now() { return new Date(now).getTime(); }
  }
  function load(file) {
    file = path.resolve(file);
    if (!path.extname(file)) file += fs.existsSync(file + '.ts') ? '.ts' : '.tsx';
    if (mocks[path.basename(file)]) return mocks[path.basename(file)];
    if (cache.has(file)) return cache.get(file);
    const exports = {};
    cache.set(file, exports);
    const output = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    vm.runInNewContext(output.replace(/import\.meta\.env/g, '({})'), {
      exports, Date: Clock, Intl, console,
      require: id => id.endsWith('.css') ? {} : id.startsWith('.') ? load(path.resolve(path.dirname(file), id)) : webRequire(id),
    }, { filename: file });
    return exports;
  }
  return load;
}
const load = modules('2026-11-01T10:00:00+09:00');
const { currentStudyBlock, studyBlockNames, studyBlockName, selectedStudyCourse } = load(path.join(__dirname, '../src/bank/studyBlocks.ts'));
const { startOfWeek, toDateKey } = load(path.join(__dirname, '../src/calendar/entries.ts'));
const at = value => new Date(value + '+09:00');
let sequence = 0;
function event(course, date, category = 'lecture', endTime = '10:00', extra = {}) {
  return { id: String(++sequence), course, title: course, date, startTime: '09:00', endTime, category,
    details: '', professor: '', slot: null, lectures: [], ...extra };
}
const twoBlocks = () => [
  event('이전 블록', '2026-10-29'), event('이전 블록', '2026-10-30'),
  event('이전 블록 시험', '2026-10-30', 'exam', '11:50'),
  event('감염과 면역', '2026-11-02'), event('감염과 면역 TBL', '2026-11-03'),
];

test('last exam end changes the default immediately, with no quizzes or attached lectures', () => {
  const events = twoBlocks();
  assert.equal(currentStudyBlock(events, at('2026-10-30T11:49:59')), '이전 블록');
  assert.equal(currentStudyBlock(events, at('2026-10-30T11:50:00')), '감염과 면역');
  assert.equal(currentStudyBlock(events, at('2026-11-01T00:00:00')), '감염과 면역');
  const ready = { marks: { quiz: true }, bankTimeline: { builtAt: '2026-10-30T02:00:00Z' } };
  events[0].lectures.push(ready);
  assert.equal(currentStudyBlock(events, at('2026-11-01T00:00:00')), '감염과 면역');
});

test('midterm and written exam do not skip remaining classes or a later practical exam', () => {
  const events = twoBlocks();
  events.push(event('이전 블록 실습시험', '2026-10-30', 'exam', '16:50'));
  assert.equal(currentStudyBlock(events, at('2026-10-30T12:00:00')), '이전 블록');
  assert.equal(currentStudyBlock(events, at('2026-10-30T16:50:00')), '감염과 면역');
  events.push(event('이전 블록', '2026-10-31'));
  assert.equal(currentStudyBlock(events, at('2026-10-30T17:00:00')), '이전 블록');
});

test('Saturday belongs to Friday and Sunday to the following Monday, also across year boundaries', () => {
  for (const [date, monday] of [
    ['2026-10-31', '2026-10-26'], ['2026-11-01', '2026-11-02'],
    ['2026-12-26', '2026-12-21'], ['2026-12-27', '2026-12-28'], ['2027-01-03', '2027-01-04'],
  ]) assert.equal(toDateKey(startOfWeek(new Date(date + 'T12:00:00'))), monday);
  // No previous exam is needed for Sunday's next-week preview.
  const events = [event('이번 주', '2026-10-30'), event('다음 주', '2026-11-02')];
  assert.equal(currentStudyBlock(events, at('2026-10-31T12:00:00')), '다음 주');
  assert.equal(currentStudyBlock(events, at('2026-11-01T00:00:00')), '다음 주');
});

test('Sunday waits for an unfinished final exam before advancing to Monday', () => {
  const events = twoBlocks().filter(e => e.category !== 'exam');
  events.push(event('이전 블록 시험', '2026-11-01', 'exam', '16:00'));
  assert.equal(currentStudyBlock(events, at('2026-11-01T15:59:59')), '이전 블록');
  assert.equal(currentStudyBlock(events, at('2026-11-01T16:00:00')), '감염과 면역');
});

test('unknown exam end stays until the day ends; unrelated exams cannot end a block', () => {
  const events = twoBlocks();
  events[2].endTime = '';
  assert.equal(currentStudyBlock(events, at('2026-10-30T20:00:00')), '이전 블록');
  assert.equal(currentStudyBlock(events, at('2026-10-31T00:00:00')), '감염과 면역');
  events.splice(2, 1, event('종합시험 1', '2026-10-29', 'exam', '12:00'));
  assert.equal(currentStudyBlock(events, at('2026-10-30T12:00:00')), '이전 블록');
});

test('overlapping sparse courses and unnamed midterms do not displace the main block', () => {
  const events = [];
  for (const day of ['2026-11-02', '2026-11-09', '2026-11-16', '2026-11-23', '2026-11-26']) {
    for (let i = 0; i < 3; i++) events.push(event('감염과 면역', day));
  }
  events.push(event('임상의학입문', '2026-11-03'), event('임상의학입문', '2026-11-10'),
    event('임상의학입문', '2026-11-17'), event('임상의학입문', '2026-11-24'), event('임상의학입문', '2026-12-01'),
    event('시험', '2026-11-20', 'exam', '11:50'), event('시험', '2026-11-27', 'exam', '15:50'),
    event('다음 블록', '2026-11-30'));
  assert.equal(currentStudyBlock(events, at('2026-11-10T10:00:00')), '감염과 면역');
  events.push(event('임상의학입문 실습', '2026-11-10'),
    event('임상의학입문 시험', '2026-11-10', 'exam', '16:00'));
  assert.equal(currentStudyBlock(events, at('2026-11-20T12:00:00')), '감염과 면역');
  assert.equal(currentStudyBlock(events, at('2026-11-27T15:49:59')), '감염과 면역');
  assert.equal(currentStudyBlock(events, at('2026-11-27T15:50:00')), '다음 블록');
});

test('a completed short course cannot skip an overlapping main block', () => {
  const events = [event('주 블록', '2026-10-26'), event('주 블록', '2026-10-27'),
    event('주 블록', '2026-10-28'), event('주 블록 시험', '2026-10-30', 'exam', '16:00'),
    event('짧은 과목', '2026-10-27'), event('짧은 과목 시험', '2026-10-28', 'exam', '11:00'),
    event('다음 블록', '2026-11-02')];
  assert.equal(currentStudyBlock(events, at('2026-10-29T12:00:00')), '주 블록');
});

test('normalizes practical/TBL/exam names and keeps unprepared timetable blocks in the dropdown', () => {
  for (const suffix of [' 실습 3', ' CBL 2', ' TBL 1', ' 필기시험', ' 실습시험', ' CBL/TBL 1']) {
    assert.equal(studyBlockName('감염과 면역' + suffix), '감염과 면역');
  }
  const names = studyBlockNames(twoBlocks());
  assert.equal(names.get('감염과면역'), '감염과 면역');
  assert.equal(names.size, 2);
});

test('empty, not-yet-started and finished timetables have stable defaults without mutating input', () => {
  assert.equal(currentStudyBlock([], at('2026-11-01T00:00:00')), '');
  const events = twoBlocks().map(Object.freeze);
  Object.freeze(events);
  assert.equal(currentStudyBlock(events, at('2026-10-01T00:00:00')), '이전 블록');
  assert.equal(currentStudyBlock(events, at('2026-12-31T00:00:00')), '감염과 면역');
});

test('manual selection and all-block view survive refreshes until the automatic block changes', () => {
  assert.equal(selectedStudyCourse('감염과 면역', null), '감염과 면역');
  assert.equal(selectedStudyCourse('감염과 면역', { block: '감염과 면역', course: '이전 블록' }), '이전 블록');
  assert.equal(selectedStudyCourse('감염과 면역', { block: '감염과 면역', course: '' }), '');
  assert.equal(selectedStudyCourse('감염과 면역', { block: '이전 블록', course: '' }), '감염과 면역');
});

function officialTimetable() {
  const dir = path.join(__dirname, '../../data/timetable');
  const rows = JSON.parse(fs.readFileSync(path.join(dir, fs.readdirSync(dir).find(f => f.endsWith('.json'))), 'utf8'));
  return rows.map(row => ({ ...row, course: row.title.replace(/[\s\-–—]*\d{1,3}\s*$/, '').trim(), lectures: [] }));
}

test('actual semester timetable selects infection/immunity on November 1 and preserves both exam stages', () => {
  const events = officialTimetable();
  // 감염과 면역은 1차 시험에서 블럭을 나눈다(2026-11-06 사용자 결정 4).
  for (const date of ['2026-11-01T00:00:00', '2026-11-01T23:59:59', '2026-11-02T09:00:00',
    '2026-11-10T14:00:00', '2026-11-20T11:49:59']) {
    assert.equal(currentStudyBlock(events, at(date)), '감염과 면역 1차', date);
  }
  for (const date of ['2026-11-20T11:50:00', '2026-11-20T12:00:00', '2026-11-27T15:49:59']) {
    assert.equal(currentStudyBlock(events, at(date)), '감염과 면역 2차', date);
  }
  assert.doesNotMatch(currentStudyBlock(events, at('2026-11-27T15:50:00')), /^감염과 면역/);
});

test('Korean midnight and Sunday work in an overseas browser timezone', () => {
  const old = process.env.TZ;
  try {
    process.env.TZ = 'America/Los_Angeles';
    assert.equal(currentStudyBlock(officialTimetable(), new Date('2026-10-31T15:00:00Z')), '감염과 면역 1차');
    assert.equal(toDateKey(startOfWeek(new Date('2026-10-31T12:00:00'))), '2026-10-26');
  } finally { if (old === undefined) delete process.env.TZ; else process.env.TZ = old; }
});

test('actual overview first render selects the new block and displays classes with no attached quiz', () => {
  const render = modules('2026-11-01T10:00:00+09:00', {
    'useMe.ts': { useMe: () => null },
    'api.ts': { api: () => { throw Error('Unexpected API in initial render'); } },
    'useQuizPublication.ts': { useQuizPublication: () => ({ values: [] }) },
    'QuizPublicationCell.tsx': { QuizPublicationCell: () => null },
    'StudyPlanBoard.tsx': { StudyPlanBoard: () => null },
    // Its `?raw` prompt imports need Vite; the static first render only needs the overview itself.
    'RootLearning.tsx': { useRootCatalog: () => new Map() },
  });
  const { StudyOverview } = render(path.join(__dirname, '../src/bank/StudyOverview.tsx'));
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  const { MemoryRouter } = webRequire('react-router-dom');
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, {},
    React.createElement(StudyOverview, { events: twoBlocks(), onStart() {} })));
  assert.match(html, /data-block="감염과 면역"/);
  assert.match(html, /이번 블럭/);
  assert.match(html, /감염과 면역 · 11\.02 – 11\.03/);
  assert.match(html, /퀴즈 없음/);
  assert.doesNotMatch(html, /이전 블록/);
  // Real timetable: infection/immunity is split at its first exam and grouped by display kind.
  const actual = renderToStaticMarkup(React.createElement(MemoryRouter, {},
    React.createElement(StudyOverview, { events: officialTimetable(), onStart() {} })));
  assert.match(actual, /data-block="감염과 면역 1차"/);
  for (const section of ['강의', '실습', 'TBL·CBL']) assert.match(actual, new RegExp(`aria-label="${section}"`));
  assert.match(actual, /감염질환에 대한 접근/);
  assert.match(actual, /김남중[^·]*· 감염학/);
  assert.match(actual, /감염과 면역 1차 · 11.02 – 11.19/);
});

test('a Main-Quiz-only lecture opens from the list but is not offered to the bank batch', () => {
  const render = modules('2026-11-01T10:00:00+09:00', {
    'useMe.ts': { useMe: () => null },
    'api.ts': { api: () => { throw Error('Unexpected API in initial render'); } },
    'useQuizPublication.ts': { useQuizPublication: () => ({ values: [] }) },
    'QuizPublicationCell.tsx': { QuizPublicationCell: () => null },
    'StudyPlanBoard.tsx': { StudyPlanBoard: () => null },
    'RootLearning.tsx': { useRootCatalog: () => new Map([['감염과 면역/261104_02', { total: 98, learned: 11, recalled: 0 }]]) },
  });
  const { StudyOverview } = render(path.join(__dirname, '../src/bank/StudyOverview.tsx'));
  const React = webRequire('react');
  const { renderToStaticMarkup } = webRequire('react-dom/server');
  const { MemoryRouter } = webRequire('react-router-dom');
  const events = twoBlocks();
  const marks = { notesPrev: false, preview: false, prequiz: false, notesCurrent: false, quiz: false, mainQuiz: true };
  events[3].lectures = [{ subject: '감염과 면역', runId: '261104_02', title: '감염성 질환의 병리 1', professors: [], marks,
    prequizProgress: null, grabbed: { pre: false, main: false }, studyLoaded: true, cardProgress: null, mastery: null }];
  const html = renderToStaticMarkup(React.createElement(MemoryRouter, {},
    React.createElement(StudyOverview, { events, onStart() {} })));
  assert.match(html, /Main-Quiz/);
  assert.match(html, /첫 학습 11\/98 · 회상 가능 0/);
  assert.match(html, /href="\/mainquiz\/%EA%B0%90%EC%97%BC%EA%B3%BC%20%EB%A9%B4%EC%97%AD\/261104_02"/);
  assert.doesNotMatch(html, /감염성 질환의 병리 1 선택/, 'no batch checkbox for a Main-Quiz-only lecture');
});
