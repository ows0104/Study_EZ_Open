const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const bridge = path.join(__dirname, '../../bridge');
const read = name => fs.readFileSync(path.join(bridge, name), 'utf8');

function webBridge() {
  const attributes = new Map();
  const posted = [];
  const sent = [];
  const listeners = {};
  const runtime = {
    id: 'extension-id',
    onMessage: { addListener: listener => { listeners.extension = listener; } },
    sendMessage(message, callback) { sent.push(message); callback?.({ ok: true }); },
  };
  const window = {
    location: { origin: 'https://studyez.kr' },
    addEventListener: (type, listener) => { listeners[type] = listener; },
    postMessage: message => posted.push(message),
    setInterval() {},
  };
  const context = vm.createContext({
    chrome: { runtime }, window,
    document: { documentElement: {
      setAttribute: (name, value) => attributes.set(name, value),
      removeAttribute: name => attributes.delete(name),
    } },
  });
  vm.runInContext(read('protocol.js'), context);
  vm.runInContext(read('studyez-bridge.js'), context);
  const protocol = context.STUDYEZ_PROTOCOL;
  function request(type = 'openPreview', extra = {}) {
    listeners.message({ source: window, origin: window.location.origin, data: {
      source: protocol.WEBAPP_SOURCE, type: protocol.MESSAGES[type],
      payload: { requestId: 'r1', prompt: 'Explain', files: [] },
      lectureId: 'lecture', kind: 'chatgpt', provider: 'chatgpt',
      shareUrl: 'https://chatgpt.com/share/ours', ...extra,
    } });
  }
  return { context, runtime, attributes, posted, sent, listeners, protocol, request };
}

test('web bridge reports synchronous invalidation and clears installed marker', () => {
  const s = webBridge();
  s.runtime.sendMessage = () => { throw new Error('Extension context invalidated.'); };
  assert.doesNotThrow(() => s.request());
  assert.equal(s.posted[0].requestId, 'r1');
  assert.equal(s.posted[0].ok, false);
  assert.match(s.posted[0].error, /새로고침/);
  assert.equal(s.attributes.has(s.protocol.READY_ATTRIBUTE), false);
  s.runtime.sendMessage = () => assert.fail('dead context called');
  s.request();
  assert.equal(s.posted.length, 2);
});

test('web bridge handles a missing id without calling runtime', () => {
  const s = webBridge();
  delete s.runtime.id;
  s.runtime.sendMessage = () => assert.fail('missing id called');
  s.request();
  assert.equal(s.posted[0].ok, false);
  assert.equal(s.attributes.size, 0);
});

for (const mode of ['callback error', 'lastError getter throws']) {
  test(`web bridge handles ${mode}`, () => {
    const s = webBridge();
    s.runtime.sendMessage = (_message, callback) => {
      if (mode === 'callback error') s.runtime.lastError = { message: 'Extension context invalidated.' };
      else Object.defineProperty(s.runtime, 'lastError', { get() { throw new Error('Extension context invalidated.'); } });
      callback();
    };
    assert.doesNotThrow(() => s.request());
    assert.equal(s.posted[0].ok, false);
    assert.equal(s.attributes.size, 0);
  });
}

for (const type of ['bankSaved', 'linkSaved', 'watchShare']) {
  test(`${type} handles invalidation without an uncaught error`, () => {
    const s = webBridge();
    s.runtime.sendMessage = () => { throw new Error('Extension context invalidated.'); };
    assert.doesNotThrow(() => s.request(type));
    assert.equal(s.attributes.size, 0);
  });
}

test('web bridge retains live marker on unrelated failure and supports success', () => {
  const s = webBridge();
  s.request();
  assert.equal(s.posted[0].ok, true);
  s.runtime.sendMessage = () => { throw new Error('Temporary failure'); };
  s.request();
  assert.equal(s.posted[1].error, 'Temporary failure');
  assert.equal(s.attributes.get(s.protocol.READY_ATTRIBUTE), s.protocol.VERSION);
});

test('web bridge rejects foreign origins and malformed payloads', () => {
  const s = webBridge();
  s.listeners.message({ source: {}, origin: 'https://studyez.kr', data: { source: s.protocol.WEBAPP_SOURCE } });
  s.listeners.message({ source: s.context.window, origin: 'https://evil.example', data: { source: s.protocol.WEBAPP_SOURCE } });
  s.request('openPreview', { payload: { prompt: 123, files: [] } });
  assert.equal(s.sent.length, 1); // startup check only
  assert.equal(s.posted.length, 0);
});

function element(label = '', attributes = {}) {
  return {
    innerText: label, textContent: label, disabled: false,
    getAttribute: name => attributes[name] ?? null,
    getBoundingClientRect: () => ({ width: 100, height: 20 }),
    click() {},
  };
}

function shareFixture({ fields = [], buttons = [], text = 'Share conversation', dialog = true } = {}) {
  const root = element(text);
  root.querySelectorAll = selector => selector.includes('input') ? fields : buttons;
  const sent = [];
  const state = { disconnected: false, cleared: false, poll: null, observer: null, sleeps: 0 };
  const runtime = {
    id: 'extension-id',
    onMessage: { addListener() {} },
    sendMessage(message, callback) { sent.push(message); callback?.({ ok: true }); },
  };
  const document = {
    body: { innerText: 'https://chatgpt.com/share/unrelated-answer' }, hidden: false,
    querySelector: () => null,
    querySelectorAll: selector => selector.includes('dialog') ? (dialog ? [root] : []) : [],
  };
  const context = vm.createContext({
    chrome: { runtime }, document, location: { pathname: '/c/our-conversation' },
    URL, console: { info() {}, warn() {}, error() {} }, Date,
    setTimeout: callback => { state.sleeps++; callback(); },
    window: {
      setInterval: callback => { state.poll = callback; return 1; },
      clearInterval: () => { state.cleared = true; },
    },
    MutationObserver: class {
      constructor(callback) { state.observer = callback; }
      observe() {}
      disconnect() { state.disconnected = true; }
    },
  });
  const source = read('chatgpt-share.js');
  vm.runInContext(source.slice(0, source.lastIndexOf('void initialize()')), context);
  return { context, root, runtime, sent, state, document };
}

test('bank saves shared and private URLs separately without a response or completion marker', async () => {
  const s = shareFixture();
  vm.runInContext('watch = { mode: "bank" };', s.context);
  s.context.accessToken = async () => 'test-token';
  s.context.conversationState = async () => ({ finished: true, currentNode: 'bank-answer', answer: 'Bank without a completion marker' });
  s.context.publishViaApi = async () => 'https://chatgpt.com/share/bank-test';
  s.context.isPubliclyReadable = async () => true;
  assert.equal(await s.context.publish(), 'published');
  const messages = s.sent.filter(m => ['STUDYEZ_SHARE_LINK', 'STUDYEZ_CONVERSATION_LINK'].includes(m.type));
  assert.equal(messages.length, 2);
  assert.equal(messages[0].url, 'https://chatgpt.com/c/our-conversation');
  assert.equal(messages[1].url, 'https://chatgpt.com/share/bank-test');
  assert.equal(s.sent.some(m => m.type === 'STUDYEZ_BANK_ANSWER'), false);
  assert.equal(await s.context.publish(), 'settled');
});

test('bank hands complete answer to runner even when public sharing fails, once per answer', async () => {
  const s = shareFixture();
  vm.runInContext('watch = { mode: "bank" };', s.context);
  s.context.accessToken = async () => 'test-token';
  s.context.conversationState = async () => ({ finished: true, currentNode: 'bank-answer', answer: 'Bank '.repeat(50) + 'STUDYEZ_BANK_COMPLETE' });
  s.context.publishViaApi = async () => 'https://chatgpt.com/share/bank-test';
  s.context.isPubliclyReadable = async () => false;
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(s.sent.filter(m => m.type === 'STUDYEZ_BANK_ANSWER').length, 1);
  assert.equal(s.sent.filter(m => m.type === 'STUDYEZ_CONVERSATION_LINK').length, 1);
  assert.equal(s.sent.some(m => m.type === 'STUDYEZ_SHARE_LINK'), false);
  vm.runInContext('retryAfter = 0;', s.context);
  await s.context.publish();
  assert.equal(s.sent.filter(m => m.type === 'STUDYEZ_BANK_ANSWER').length, 1);
});

test('bank defers state API calls while the answer is generating', async () => {
  const s = shareFixture();
  vm.runInContext('watch = { mode: "bank" };', s.context);
  const stop = element('중지');
  s.document.querySelectorAll = () => [stop];
  s.context.accessToken = async () => assert.fail('generation must not poll the backend');
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(s.sent.length, 0);
});

test('bank retries an answer when extension storage did not acknowledge it', async () => {
  const s = shareFixture();
  vm.runInContext('watch = { mode: "bank" };', s.context);
  s.context.accessToken = async () => 'token';
  s.context.conversationState = async () => ({finished:true, currentNode:'answer',
    answer:'Question '.repeat(50) + 'STUDYEZ_BANK_COMPLETE'});
  s.context.chrome.runtime.sendMessage = (message, callback) => {
    s.sent.push(message); callback?.({ok:false});
  };
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(s.sent.filter(m => m.type === 'STUDYEZ_BANK_ANSWER').length, 2);
});

test('bank state 429 backs off, then resumes and clears the delay after saving', async () => {
  const s = shareFixture();
  vm.runInContext('watch = { mode: "bank" };', s.context);
  let calls = 0;
  s.context.accessToken = async () => 'test-token';
  s.context.conversationState = async () => { calls++; throw new Error('HTTP 429'); };
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(calls, 1);
  assert.ok(vm.runInContext('retryAfter > Date.now()', s.context));
  vm.runInContext('retryAfter = 0;', s.context);
  s.context.conversationState = async () => ({ finished: true, currentNode: 'recovered', answer: 'Bank STUDYEZ_BANK_COMPLETE' });
  s.context.publishViaApi = async () => 'https://chatgpt.com/share/recovered';
  s.context.isPubliclyReadable = async () => true;
  assert.equal(await s.context.publish(), 'published');
  assert.equal(vm.runInContext('failures', s.context), 0);
  assert.equal(vm.runInContext('retryAfter', s.context), 0);
  assert.equal(s.sent.filter(m => m.type === 'STUDYEZ_SHARE_LINK').length, 1);
});

test('reads anchor href inside sharing dialog and ignores answer links', () => {
  const s = shareFixture({ fields: [element('Copy', { href: '/share/our-share?source=copy' })] });
  assert.equal(s.context.shareUrlOnScreen(), 'https://chatgpt.com/share/our-share');
  const absent = shareFixture({ dialog: false });
  assert.equal(absent.context.shareUrlOnScreen(), '');
});

test('reads input, text and enterprise share URLs, rejects foreign/conversation URLs', () => {
  const s = shareFixture();
  const { normalizedShareUrl } = s.context;
  for (const value of ['https://evil.example/share/abc', 'https://chatgpt.com/c/abc',
    'https://chatgpt.com/share/', 'https://chatgpt.com/share/abc/extra',
    'https://user:password@chatgpt.com/share/abc']) assert.equal(normalizedShareUrl(value), '');
  const input = element(); input.value = ' https://chatgpt.com/share/e/our-share/ ';
  s.root.querySelectorAll = () => [input];
  assert.equal(s.context.shareUrlOnScreen(), 'https://chatgpt.com/share/e/our-share');
  s.root.querySelectorAll = () => [];
  s.root.innerText = 'Share: https://chatgpt.com/share/text-share';
  assert.equal(s.context.shareUrlOnScreen(), 'https://chatgpt.com/share/text-share');
});

for (const label of ['Create link', 'Copy link', 'Copy', '링크 만들기', '공유 링크 복사', '복사']) {
  test(`sharing dialog supports ${label} and clicks only once`, async () => {
    let clicks = 0;
    const button = element(label);
    const field = element();
    button.click = () => { clicks++; field.value = 'https://chatgpt.com/share/created'; };
    const s = shareFixture({ fields: [field], buttons: [button] });
    assert.equal(await s.context.publishViaDialog(), 'https://chatgpt.com/share/created');
    assert.equal(clicks, 1);
  });
}

test('share button label can appear in both aria-label and text', () => {
  const s = shareFixture();
  const button = element('Share', { 'aria-label': 'Share' });
  s.document.querySelectorAll = () => [button];
  assert.equal(s.context.buttonByLabel(/^share$/i), button);
});

test('updates existing snapshot before returning its URL', async () => {
  let clicks = 0;
  const button = element('Update link');
  const field = element(); field.value = 'https://chatgpt.com/share/existing';
  button.click = () => { clicks++; };
  const s = shareFixture({ fields: [field], buttons: [button] });
  assert.equal(await s.context.publishViaDialog(), field.value);
  assert.equal(clicks, 1);
  assert.ok(s.state.sleeps >= 5);
});

test('recovers copy-only dialog using exact conversation matching', async () => {
  const s = shareFixture({ buttons: [element('Copy link')] });
  let reads = 0;
  s.context.api = async () => ({ ok: true, json: async () => {
    reads++;
    return { items: [
      { conversation_id: 'other-conversation', id: 'wrong' },
      { conversation_id: 'our-conversation', id: 'correct' },
    ] };
  } });
  assert.equal(await s.context.publishViaDialog('our-conversation', 'test-token'), 'https://chatgpt.com/share/correct');
  assert.equal(reads, 1);
});

test('waits beyond old ten-second limit without repeatedly creating links', async () => {
  const button = element('Create link');
  let clicks = 0;
  button.click = () => { clicks++; };
  const s = shareFixture({ buttons: [button] });
  const field = element(); field.value = 'https://chatgpt.com/share/delayed';
  s.root.querySelectorAll = selector => selector.includes('input') ? (s.state.sleeps > 50 ? [field] : []) : [button];
  assert.equal(await s.context.publishViaDialog(), field.value);
  assert.equal(clicks, 1);
});

test('dialog timeout stays an error and navigation aborts the attempt', async () => {
  const s = shareFixture();
  await assert.rejects(s.context.publishViaDialog(), /共有|공유 대화상자/);
  s.context.location.pathname = '/c/another-conversation';
  await assert.rejects(s.context.publishViaDialog('our-conversation'), /대화가 바뀌었습니다/);
});

test('unverified links are never sent or marked published', async () => {
  const s = shareFixture();
  s.context.isPubliclyReadable = async () => false;
  await assert.rejects(s.context.settleShare('https://chatgpt.com/share/private'), /공개 여부/);
  assert.equal(s.sent.length, 0);
  assert.equal(vm.runInContext('lastShareUrl', s.context), '');
  await assert.rejects(s.context.settleShare(''), /유효한/);
});

test('transient sharing failure remains pending and backs off without DOM mutations', async () => {
  const s = shareFixture();
  let tries = 0;
  vm.runInContext('watch = { mode: "shared" };', s.context);
  s.context.accessToken = async () => 'test-token';
  s.context.conversationState = async () => ({ finished: true, currentNode: 'answer' });
  s.context.publishViaApi = async () => { tries++; throw new Error('Temporary API failure'); };
  s.context.publishViaDialog = async () => { throw new Error('Temporary dialog failure'); };
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(vm.runInContext('lastSharedNode', s.context), '');
  assert.equal(await s.context.publish(), 'pending');
  assert.equal(tries, 1);
  vm.runInContext('retryAfter = 0;', s.context);
  s.context.publishViaApi = async () => 'https://chatgpt.com/share/recovered';
  s.context.isPubliclyReadable = async () => true;
  assert.equal(await s.context.publish(), 'published');
  assert.equal(vm.runInContext('lastSharedNode', s.context), 'answer');
  assert.equal(vm.runInContext('failures', s.context), 0);
});

test('polling retains DOM mutations that arrive during asynchronous publishing', async () => {
  const s = shareFixture();
  let calls = 0;
  s.context.publish = async () => { calls++; if (calls === 1) s.state.observer(); return 'published'; };
  s.context.watchForCompletedTurns();
  await s.state.poll();
  await s.state.poll();
  await s.state.poll();
  assert.equal(calls, 2);
});

test('invalidation stops share observer/timer and initialization handles synchronous throws', async () => {
  const s = shareFixture();
  s.context.watchForCompletedTurns();
  delete s.runtime.id;
  await s.state.poll();
  assert.equal(s.state.disconnected, true);
  assert.equal(s.state.cleared, true);
  const other = shareFixture();
  other.runtime.sendMessage = () => { throw new Error('Extension context invalidated.'); };
  await assert.doesNotReject(other.context.initialize());
  assert.equal(vm.runInContext('contextInvalidated', other.context), true);
});

for (const mode of ['review', 'bank']) test(`${mode} links keep their own pending keys until each save is acknowledged`, async () => {
  const stored = {};
  const delivered = [];
  let receive;
  const context = vm.createContext({ URL, console, importScripts() {}, chrome: {
    runtime: { onMessage: { addListener(fn) { receive = fn; } }, onConnect: { addListener() {} } },
    storage: { session: {
      async get(key) { return key === null ? { ...stored } : { [key]: stored[key] }; },
      async set(values) { Object.assign(stored, values); },
      async remove(key) { delete stored[key]; },
    } },
    tabs: {
      onUpdated: { addListener() {} }, onRemoved: { addListener() {} }, onActivated: { addListener() {} },
      async create() { return { id: 10 }; },
      async sendMessage(tab, message) { delivered.push({ tab, ...message }); },
    },
  } });
  vm.runInContext(read('protocol.js'), context);
  vm.runInContext(read('background.js'), context);
  const protocol = context.STUDYEZ_PROTOCOL;
  const request = { requestId: 'review', lectureId: '약리학/261006_01', provider: 'chatgpt',
    mode, prompt: 'Review today', autoSend: false,
    files: [{ filename: 'today.pdf', downloadUrl: 'http://localhost:8000/api/local-storage/lectures/today.pdf' }] };
  const response = await new Promise(resolve => receive({ type: protocol.MESSAGES.openPreview, payload: request },
    { tab: { id: 1, url: 'http://localhost:5173' } }, resolve));
  assert.equal(response.ok, true);
  assert.equal(stored['studyez-watch:10'].mode, mode);
  const sender = { tab: { id: 10, url: 'https://chatgpt.com/c/review' } };
  receive({ type: 'STUDYEZ_CONVERSATION_LINK', lectureId: 'wrong', url: sender.tab.url }, sender, () => {});
  await new Promise(resolve => setImmediate(resolve));
  const link = delivered.find(message => message.type === protocol.MESSAGES.linkReady);
  const privateKind = mode === 'bank' ? 'chatgpt_bank' : 'chatgpt_review';
  assert.equal(link.kind, privateKind);
  assert.equal(link.lectureId, request.lectureId);
  assert.equal(stored[`studyez-pending:1:${request.lectureId}:chatgpt`], undefined);
  const count = delivered.length;
  receive({ type: 'STUDYEZ_SHARE_LINK', url: 'https://chatgpt.com/share/review' }, sender, () => {});
  await new Promise(resolve => setImmediate(resolve));
  if (mode === 'review') assert.equal(delivered.length, count);
  else {
    assert.ok(delivered.some(message => message.kind === 'chatgpt_bank_share'));
    assert.equal(stored[`studyez-pending:1:${request.lectureId}:chatgpt_bank_share`].url, 'https://chatgpt.com/share/review');
    assert.equal(stored[`studyez-pending:1:${request.lectureId}:chatgpt_share`], undefined);
  }
  receive({ type: protocol.MESSAGES.linkSaved, lectureId: request.lectureId, kind: privateKind },
    { tab: { id: 1, url: 'http://localhost:5173' } }, () => {});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(stored[`studyez-pending:1:${request.lectureId}:${privateKind}`], undefined);
  if (mode === 'bank') {
    assert.ok(stored[`studyez-pending:1:${request.lectureId}:chatgpt_bank_share`]);
    receive({type: protocol.MESSAGES.linkSaved, lectureId: request.lectureId, kind: 'chatgpt_bank_share'},
      {tab: {id: 1, url: 'http://localhost:5173'}}, () => {});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(stored[`studyez-pending:1:${request.lectureId}:chatgpt_bank_share`], undefined);
  }
});
