const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function load(file) {
  const source = fs.readFileSync(path.join(__dirname, '../src', file), 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = vm.createContext({ exports: {}, require: () => load('jobProgress.ts') });
  vm.runInContext(js, context);
  return context.exports;
}
const { ADMIN_REFRESH_MS, mergeJobBoard, refreshDue, resultsChanged } = load('admin/jobUpdates.ts');
const job = (id, state, extra = {}) => ({ id, subject: 'local', runId: 'demo', state, ...extra });
const board = (...jobs) => ({ jobs, runner: { lastSeen: 'fresh', busy: true } });

test('automatic and tab-return refreshes wait ten minutes since the last read', () => {
  assert.equal(ADMIN_REFRESH_MS, 600000);
  assert.equal(refreshDue(1000, 11000), false);
  assert.equal(refreshDue(1000, 600999), false);
  assert.equal(refreshDue(1000, 601000), true);
  assert.equal(refreshDue(1000, 1201000), true);
});

test('progress ticks keep results; completion/failure/held/missing active jobs refresh once', () => {
  const running = board(job(1, 'running', { stage: 'validate' }));
  assert.equal(resultsChanged(null, running), false);
  assert.equal(resultsChanged(running, board(job(1, 'running', { stage: 'upload' }))), false);
  for (const state of ['done', 'failed', 'canceled', 'held']) {
    const finished = board(job(1, state));
    assert.equal(resultsChanged(running, finished), true);
    assert.equal(resultsChanged(finished, finished), false);
  }
  assert.equal(resultsChanged(running, board()), true);
  assert.equal(resultsChanged(board(), board(job(2, 'done'))), true);
  assert.equal(resultsChanged(board(job(1, 'queued')), running), false);
});

test('job board refreshes progress and runner while preserving bank results and newest jobs', () => {
  const bank = { usable: true, questionCount: 12 };
  const overview = { lectures: [{ subject: 'local', runId: 'demo', prequizJob: job(2, 'running'), bank }] };
  const next = mergeJobBoard(overview, board(job(2, 'done'), job(1, 'running')));
  assert.equal(next.lectures[0].prequizJob.state, 'done');
  assert.equal(next.lectures[0].bank, bank);
  assert.equal(next.runner.lastSeen, 'fresh');
  assert.equal(overview.lectures[0].prequizJob.state, 'running');
  assert.equal(mergeJobBoard(overview, board(job(1, 'running'))).lectures[0].prequizJob.id, 2);
  assert.equal(mergeJobBoard(overview, board(job(3, 'queued'))).lectures[0].prequizJob.id, 3);
});
