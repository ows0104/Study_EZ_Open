// 배경(background.js)과 탭(chatgpt-bridge.js)의 자료 전달을 가짜 포트로 잇는다.
// 2026-11-15: 「받는 중」 뒤 연결이 끊김 → 조각마다 FILE_ACK, 끊기면 한 번 다시 받기.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const bridge = path.join(__dirname, '../../bridge');
const read = (name) => fs.readFileSync(path.join(bridge, name), 'utf8');

function listeners() {
  const fns = [];
  return { fns, addListener(fn) { fns.push(fn); }, fire(...args) { for (const fn of [...fns]) fn(...args); } };
}

/** 양쪽 포트. 메시지는 비동기로, 복제해서 넘긴다. disconnect()는 상대 쪽 onDisconnect만 부른다. */
function portPair(log) {
  const make = (side) => ({ side, onMessage: listeners(), onDisconnect: listeners(), open: true });
  const tab = make('tab');
  const bg = make('bg');
  const wire = (from, to) => {
    from.postMessage = (message) => {
      if (!from.open) throw new Error('Attempting to use a disconnected port object');
      log.push({ from: from.side, type: message.type });
      const copy = JSON.parse(JSON.stringify(message));
      setImmediate(() => { if (to.open) to.onMessage.fire(copy); });
    };
    from.disconnect = () => {
      if (!from.open) return;
      from.open = false;
      to.open = false;
      setImmediate(() => to.onDisconnect.fire());
    };
  };
  wire(tab, bg);
  wire(bg, tab);
  /** 배경 서비스 워커가 죽은 경우: 양쪽 다 끊김을 받는다. */
  const kill = () => {
    tab.open = false;
    bg.open = false;
    setImmediate(() => { tab.onDisconnect.fire(); bg.onDisconnect.fire(); });
  };
  return { tab, bg, kill };
}

function payload(size) {
  const bytes = new Uint8Array(size);
  for (let index = 0; index < size; index += 1) bytes[index] = (index * 31 + 7) % 251;
  return bytes;
}

/** `onChunk(attempt, chunkIndex, pair)`로 특정 시점에 끊김을 일으킨다. */
function setup({ size = 3 * 1024 * 1024 + 123, readSize = 65536, onChunk = () => {} } = {}) {
  const data = payload(size);
  const log = [];
  const pairs = [];
  const cancelled = [];
  let onConnect;
  const bgContext = vm.createContext({
    URL, console, setTimeout, clearTimeout, btoa, importScripts() {},
    fetch: async () => {
      let offset = 0;
      const reader = {
        async read() {
          if (offset >= data.length) return { done: true };
          const value = data.subarray(offset, offset + readSize);
          offset += readSize;
          return { done: false, value };
        },
        async cancel() { cancelled.push(offset); },
      };
      return { ok: true, status: 200, body: { getReader: () => reader } };
    },
    chrome: {
      runtime: { onMessage: { addListener() {} }, onConnect: { addListener(fn) { onConnect = fn; } } },
      storage: { session: { async get() { return {}; }, async set() {}, async remove() {} } },
      tabs: { onUpdated: { addListener() {} }, onRemoved: { addListener() {} }, onActivated: { addListener() {} } },
    },
  });
  vm.runInContext(read('protocol.js'), bgContext);
  vm.runInContext(read('background.js'), bgContext);
  const origin = vm.runInContext('R2_ORIGIN', bgContext);

  const tabContext = vm.createContext({
    setTimeout, clearTimeout, console, atob, File,
    chrome: {
      runtime: {
        connect({ name }) {
          const pair = portPair(log);
          const attempt = pairs.length + 1;
          pairs.push(pair);
          let chunkIndex = 0;
          const original = pair.bg.postMessage;
          pair.bg.postMessage = (message) => {
            original(message);
            if (message.type === 'FILE_CHUNK') onChunk(attempt, (chunkIndex += 1), pair);
          };
          onConnect({ ...pair.bg, name });
          return pair.tab;
        },
      },
    },
  });
  const source = read('chatgpt-bridge.js');
  vm.runInContext(source.slice(0, source.lastIndexOf('void initialize()')), tabContext);
  const fetchFile = vm.runInContext('fetchFile', tabContext);
  const file = { id: 'f1', filename: '251117_05 자료.pdf', downloadUrl: `${origin}/lectures/x.pdf` };
  const status = { textContent: '' };
  const statuses = [];
  const trackedStatus = new Proxy(status, { set(target, key, value) { target[key] = value; statuses.push(value); return true; } });
  const controller = new AbortController();
  const run = () => fetchFile(file, trackedStatus, controller.signal);
  return { data, log, pairs, cancelled, run, statuses, controller };
}

test('chunks are batched to ~1MB and each waits for the tab ACK before the next', async () => {
  const s = setup();
  const result = await s.run();
  const bytes = new Uint8Array(await result.arrayBuffer());
  assert.deepEqual(bytes, s.data);
  assert.equal(s.pairs.length, 1);
  const chunks = s.log.filter((entry) => entry.type === 'FILE_CHUNK');
  assert.equal(chunks.length, 4, 'about 1MB per message');
  // Never two chunks in flight: every chunk after the first follows an ACK.
  let outstanding = 0;
  for (const entry of s.log) {
    if (entry.type === 'FILE_CHUNK') { outstanding += 1; assert.equal(outstanding, 1); }
    if (entry.type === 'FILE_ACK') outstanding -= 1;
  }
  assert.ok(s.statuses.some((text) => /받는 중… \d+\.\dMB$/.test(text)), s.statuses.join(' | '));
});

test('a background disconnect mid-stream retries that file once on a new port', async () => {
  const s = setup({ onChunk: (attempt, index, pair) => { if (attempt === 1 && index === 2) pair.kill(); } });
  const result = await s.run();
  assert.deepEqual(new Uint8Array(await result.arrayBuffer()), s.data);
  assert.equal(s.pairs.length, 2);
  assert.ok(s.statuses.some((text) => text.includes('다시 받는 중')), s.statuses.join(' | '));
});

test('a second disconnect stops with file name, received size and attempt count', async () => {
  const s = setup({ onChunk: (attempt, index, pair) => { if (index === 1) pair.kill(); } });
  await assert.rejects(s.run(), (error) => {
    assert.match(error.message, /연결이 끊겼습니다\(251117_05 자료\.pdf, \d+\.\dMB 받은 뒤, 2번 시도\)/);
    return true;
  });
  assert.equal(s.pairs.length, 2);
});

test('the background stops reading R2 when the tab goes away', async () => {
  let s;
  s = setup({ onChunk: (attempt, index) => { if (index === 1) s.controller.abort(); } });
  await assert.rejects(s.run(), /자동 진행을 중지했습니다/);
  assert.equal(s.pairs.length, 1, 'a user stop is not retried');
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(s.cancelled.length >= 1, 'reader.cancel() was called');
  // After the tab left, the background sent nothing else on that port.
  const afterFirst = s.log.slice(s.log.findIndex((entry) => entry.type === 'FILE_CHUNK') + 1);
  assert.ok(!afterFirst.some((entry) => entry.from === 'bg' && entry.type === 'FILE_END'));
});
