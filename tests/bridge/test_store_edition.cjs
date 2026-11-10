const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const bridge = path.join(__dirname, '../../bridge');
const read = name => fs.readFileSync(path.join(bridge, name), 'utf8');

/** 스토어 빌드와 같은 변환: EDITION만 user로 바꾸고, bank 스크립트는 싣지 않는다(importScripts는 빈 함수). */
function background(edition) {
  const protocol = read('protocol.js');
  assert.equal(protocol.split('EDITION: "full",').length, 2);
  const opened = [];
  let receive;
  const context = vm.createContext({ URL, console, importScripts() {}, chrome: {
    runtime: { onMessage: { addListener(fn) { receive = fn; } }, onConnect: { addListener() {} } },
    storage: { session: { async get() { return {}; }, async set() {}, async remove() {} } },
    tabs: { onUpdated: { addListener() {} }, onRemoved: { addListener() {} }, onActivated: { addListener() {} },
      async create(input) { opened.push(input.url); return { id: 50 + opened.length }; },
      async sendMessage() {}, async get(id) { return { id, url: 'https://studyez.kr/calendar' }; } },
  } });
  vm.runInContext(protocol.replace('EDITION: "full",', `EDITION: "${edition}",`), context);
  vm.runInContext(read('background.js'), context);
  assert.equal(context.StudyEZBankFile, undefined);
  const open = payload => new Promise(resolve => {
    const result = receive({ type: 'STUDYEZ_OPEN_PREVIEW', payload: {
      requestId: 'r', lectureId: 'subject/run', provider: 'chatgpt', prompt: 'p',
      files: [{ filename: 'a.pdf', downloadUrl: 'https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com/a.pdf' }],
      ...payload,
    } }, { tab: { id: 7, url: 'https://studyez.kr/calendar' } }, resolve);
    assert.equal(typeof result, 'boolean');
  });
  return { open, opened };
}

test('store user edition opens only manual personal preview and review', async () => {
  const { open, opened } = background('user');
  for (const mode of ['personal', 'review']) {
    assert.deepEqual({ ...(await open({ mode, autoSend: false })) }, { ok: true });
  }
  for (const payload of [{ mode: 'shared', autoSend: false }, { mode: 'bank', autoSend: false },
    { mode: 'personal', autoSend: true }, { mode: 'review', autoSend: true }]) {
    const result = await open(payload);
    assert.equal(result.ok, false, JSON.stringify(payload));
    assert.match(result.error, /관리자용 브리지/);
  }
  assert.equal(opened.length, 2);
});

test('full admin edition keeps auto-send, shared links, and Quiz Bank', async () => {
  const { open, opened } = background('full');
  for (const payload of [{ mode: 'shared', autoSend: true }, { mode: 'bank', autoSend: true }, { mode: 'personal', autoSend: true }]) {
    assert.equal((await open(payload)).ok, true, JSON.stringify(payload));
  }
  assert.equal(opened.length, 3);
});
