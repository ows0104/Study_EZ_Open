const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function fixture() {
  let revision = 1, timetableRequests = 0, meRequests = 0;
  const js = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/firstScreen.ts'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = vm.createContext({ exports: {}, require: () => ({ api: async (url) => {
    if (url === '/api/me') { meRequests++; return { isAdmin: false }; }
    timetableRequests++; return { events: [{ revision }] };
  } }) });
  vm.runInContext(js, context);
  return { ...context.exports, change: () => revision++, requests: () => ({ timetableRequests, meRequests }) };
}
test('direct study entry invalidates the timetable prefetched before new questions', async () => {
  const f = fixture();
  f.startFirstScreen(); await f.getMe();
  f.change(); f.invalidateTimetable();
  assert.equal((await f.takeTimetable()).events[0].revision, 2);
  assert.equal(f.requests().timetableRequests, 2);
});
test('repeated account reads do not repopulate a stale timetable cache', async () => {
  const f = fixture();
  f.startFirstScreen(); await f.getMe(); await f.takeTimetable();
  await f.getMe(); f.change();
  assert.equal((await f.takeTimetable()).events[0].revision, 2);
  assert.equal(f.requests().meRequests, 1);
  assert.equal(f.requests().timetableRequests, 2);
});
test('logout allows fresh parallel startup for the next user', async () => {
  const f = fixture();
  f.startFirstScreen(); await f.getMe(); f.resetFirstScreen(); f.change(); f.startFirstScreen();
  await f.getMe();
  assert.equal((await f.takeTimetable()).events[0].revision, 2);
  assert.equal(f.requests().meRequests, 2);
});
