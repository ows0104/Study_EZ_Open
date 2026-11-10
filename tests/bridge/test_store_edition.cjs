const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');

const bridge = path.join(__dirname, '../../bridge');
const read = name => fs.readFileSync(path.join(bridge, name), 'utf8');
const source = () => new Map(fs.readdirSync(bridge).filter(name => name.endsWith('.js') || name === 'manifest.json')
  .map(name => [name, fs.readFileSync(path.join(bridge, name))]));
const userEdition = async () => (await import(pathToFileURL(path.join(bridge, 'user-edition.mjs')).href)).toUserEdition(source());

/** 배경을 띄운다. 사용자판은 bank 스크립트가 없으므로 importScripts는 아무것도 싣지 않는다. */
function background(protocol, backgroundText) {
  const opened = [];
  let receive;
  const context = vm.createContext({ URL, console, importScripts() {}, chrome: {
    runtime: { onMessage: { addListener(fn) { receive = fn; } }, onConnect: { addListener() {} } },
    storage: { session: { async get() { return {}; }, async set() {}, async remove() {} } },
    tabs: { onUpdated: { addListener() {} }, onRemoved: { addListener() {} }, onActivated: { addListener() {} },
      async create(input) { opened.push(input.url); return { id: 50 + opened.length }; },
      async sendMessage() {}, async get(id) { return { id, url: 'https://studyez.kr/calendar' }; } },
  } });
  vm.runInContext(protocol, context);
  vm.runInContext(backgroundText, context);
  assert.equal(context.StudyEZBankFile, undefined);
  const open = payload => new Promise(resolve => {
    receive({ type: 'STUDYEZ_OPEN_PREVIEW', payload: {
      requestId: 'r', lectureId: 'subject/run', provider: 'chatgpt', prompt: 'p',
      files: [{ filename: 'a.pdf', downloadUrl: 'https://d0ec59549fea0c13f1b7fe9f724df93b.r2.cloudflarestorage.com/a.pdf' }],
      ...payload,
    } }, { tab: { id: 7, url: 'https://studyez.kr/calendar' } }, resolve);
  });
  return { open, opened };
}

test('user edition transform drops admin bank scripts and keeps every referenced file', async () => {
  const files = await userEdition();
  assert.equal(files.has('bank-file.js'), false);
  assert.equal(files.has('bank-download.js'), false);
  assert.match(files.get('protocol.js'), /EDITION: "user",/);
  assert.equal(files.get('background.js').split('\n')[0].trim(), 'importScripts("protocol.js");');
  const manifest = JSON.parse(files.get('manifest.json'));
  const scripts = manifest.content_scripts.flatMap(script => script.js);
  assert.equal(scripts.some(name => name.startsWith('bank-')), false);
  for (const name of scripts) assert.ok(files.has(name), name);
  // 관리자판 소스는 그대로다.
  assert.match(read('protocol.js'), /EDITION: "full",/);
});

test('store and site user edition opens only manual personal preview and review', async () => {
  const files = await userEdition();
  const { open, opened } = background(files.get('protocol.js'), files.get('background.js'));
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
  const { open, opened } = background(read('protocol.js'), read('background.js'));
  for (const payload of [{ mode: 'shared', autoSend: true }, { mode: 'bank', autoSend: true }, { mode: 'personal', autoSend: true }]) {
    assert.equal((await open(payload)).ok, true, JSON.stringify(payload));
  }
  assert.equal(opened.length, 3);
});
