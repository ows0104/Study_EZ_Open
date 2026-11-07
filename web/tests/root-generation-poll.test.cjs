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
  const context = vm.createContext({ exports: {}, Promise });
  vm.runInContext(js, context);
  return context.exports;
}
const { pollAfterSettled } = load('bank/pollChain.ts');
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  let waiting = null;
  let scheduled = 0;
  return {
    timers: {
      setTimeout: (fn, ms) => {
        assert.equal(waiting, null, '한 번에 하나만 예약한다');
        scheduled += 1; waiting = { fn, ms }; return scheduled;
      },
      clearTimeout: () => { waiting = null; },
    },
    get delay() { return waiting ? waiting.ms : null; },
    get scheduled() { return scheduled; },
    fire() { const due = waiting; waiting = null; due.fn(); },
  };
}

test('응답이 돌아오기 전에는 다음 폴링을 예약하지 않는다', async () => {
  const h = harness();
  let calls = 0;
  let settle;
  const stop = pollAfterSettled(() => { calls += 1; return new Promise(resolve => { settle = resolve; }); }, 3000, h.timers);
  assert.equal(calls, 0);
  assert.equal(h.delay, 3000);
  h.fire();
  await flush();
  assert.equal(calls, 1);
  // 겹쳐 쌓이게 만들던 자리다. setInterval 이면 여기서 다음 것이 이미 기다린다.
  assert.equal(h.delay, null);
  assert.equal(h.scheduled, 1);
  settle({});
  await flush();
  assert.equal(h.delay, 3000);
  h.fire();
  await flush();
  assert.equal(calls, 2);
  stop();
});

test('한 번 거절되어도 사슬은 이어진다', async () => {
  const h = harness();
  let calls = 0;
  const stop = pollAfterSettled(() => { calls += 1; return Promise.reject(new Error('synthetic')); }, 3000, h.timers);
  h.fire();
  await flush();
  assert.equal(calls, 1);
  assert.equal(h.delay, 3000);
  h.fire();
  await flush();
  assert.equal(calls, 2);
  stop();
});

test('멈추면 기다리던 응답이 돌아와도 더 보내지 않는다', async () => {
  const h = harness();
  let calls = 0;
  let settle;
  const stop = pollAfterSettled(() => { calls += 1; return new Promise(resolve => { settle = resolve; }); }, 3000, h.timers);
  h.fire();
  await flush();
  assert.equal(calls, 1);
  stop();
  settle({});
  await flush();
  assert.equal(h.delay, null);
  assert.equal(calls, 1);
  assert.equal(h.scheduled, 1);
});

test('예약 전에 멈추면 한 번도 보내지 않는다', async () => {
  const h = harness();
  let calls = 0;
  const stop = pollAfterSettled(() => { calls += 1; return Promise.resolve({}); }, 3000, h.timers);
  assert.equal(h.delay, 3000);
  stop();
  await flush();
  assert.equal(calls, 0);
  assert.equal(h.delay, null);
});
