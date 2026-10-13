const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'web/node_modules/typescript'));
const react = require(path.join(root, 'web/node_modules/react'));
const { renderToStaticMarkup } = require(path.join(root, 'web/node_modules/react-dom/server'));

function load(name, dependencies = {}, globals = {}) {
  const source = fs.readFileSync(path.join(root, 'web/src/bridge', name), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: id => {
    if (!(id in dependencies)) throw new Error(`Unexpected import ${id}`);
    return dependencies[id];
  }, ...globals });
  return exports;
}
const versions = load('version.ts');
const routing = load('linkRouting.ts', { './version': versions });
const protocol = {
  READY_ATTRIBUTE: 'data-studyez-ai-extension', EXTENSION_SOURCE: 'studyez-ai-extension',
  WEBAPP_SOURCE: 'studyez-webapp', MESSAGES: { openPreview: 'OPEN', openPreviewResult: 'RESULT', linkReady: 'LINK', linkSaved: 'SAVED' },
  LINK_KINDS: ['chatgpt', 'gemini', 'claude', 'chatgpt_share', 'gemini_share', 'claude_share', 'chatgpt_review', 'gemini_review', 'claude_review'],
  PREVIEW_TIMEOUT_MS: 5000, EXTENSION_DOWNLOAD_URL: '/studyez-extension.zip',
  EXTENSION_STORE_URL: 'https://chromewebstore.google.com/detail/example', EXTENSION_STORE_VERSION: '1.2.0',
};

test('Chrome versions compare omitted and future components and reject invalid markers', () => {
  for (const [installed, required, expected] of [
    ['1.2', '1.3.3', false], ['1.3.2', '1.3.3', false], ['1.3.3', '1.3.3', true],
    ['1.3.3', '1.3.5', false], ['1.3.5', '1.3.5', true], ['1.4', '1.3.5', true],
    ['2', '1.3.5', true], ['1.3.5.1', '1.3.5', true], ['', '1.3.3', false],
    ['true', '1.3.3', false], ['1.3.x', '1.3.3', false],
  ]) assert.equal(versions.versionAtLeast(installed, required), expected, installed);
});

test('unsupported preview and review requests never dispatch; supported requests complete', async () => {
  for (const [installed, mode, autoSend, allowed] of [
    ['1.1.0', 'personal', false, false], ['', 'personal', false, false],
    ['1.2', 'personal', false, true], ['1.2.0', 'shared', false, true], ['1.2.0', 'bank', false, false],
    ['1.2.0', 'shared', true, false], ['1.2.0', 'review', false, true],
    ['1.3.0', 'personal', false, false], ['1.3.2', 'bank', false, false],
    ['1.3.2', 'shared', true, false], ['1.3.3', 'personal', false, true],
    ['1.3.3', 'shared', true, true], ['1.3.3', 'review', false, true],
    ['1.3.9', 'bank', true, false], ['1.3.10', 'bank', true, false], ['1.3.11', 'bank', true, false],
    ['1.3.10', 'bank', false, false], ['1.3.11', 'bank', false, false],
    ['1.3.12', 'bank', false, false], ['1.3.13', 'bank', false, true], ['1.3.13', 'bank', true, true],
    ['1.3.5', 'review', false, true], ['1.4', 'shared', false, true],
  ]) {
    let sent = 0;
    let handler;
    const window = {
      location: { origin: 'https://studyez.kr' }, setTimeout: () => 1, clearTimeout() {},
      addEventListener: (_, callback) => { handler = callback; }, removeEventListener() {},
      postMessage: message => {
        sent++;
        assert.equal(message.payload.mode, mode === 'review' && !versions.versionAtLeast(installed, versions.NATIVE_REVIEW_MIN_VERSION) ? 'personal' : mode);
        handler({ source: window, origin: window.location.origin, data: {
          source: protocol.EXTENSION_SOURCE, type: 'RESULT', requestId: message.payload.requestId, ok: true,
        } });
      },
    };
    const bridge = load('previewBridge.ts', { react, './version': versions, './protocol': protocol, './linkRouting': routing }, {
      window, document: { documentElement: { getAttribute: () => installed } },
    });
    const request = bridge.requestPreview({ requestId: 'case', lectureId: '약리학/261008_01', provider: 'chatgpt', prompt: 'study', mode, files: [], autoSend });
    if (allowed) await request;
    else await assert.rejects(request, /브리지 설치·업데이트/);
    assert.equal(sent, allowed ? 1 : 0, `${installed} ${mode}`);
  }
});

function setup(installed, storeVersion, minimum, possible = true) {
  const { ExtensionSetup } = load('ExtensionSetup.tsx', {
    'react/jsx-runtime': require(path.join(root, 'web/node_modules/react/jsx-runtime')),
    '../../../bridge/manifest.json': { default: JSON.parse(fs.readFileSync(path.join(root, 'bridge/manifest.json'))) },
    './version': versions, './protocol': { ...protocol, EXTENSION_STORE_VERSION: storeVersion },
    './previewBridge': { extensionPossible: () => possible, extensionVersion: () => installed,
      extensionInputMinimum: () => versions.minimumVersionForInput(installed, 'personal', false),
      extensionCompatible: minimum => versions.versionAtLeast(installed, minimum) },
  });
  return renderToStaticMarkup(react.createElement(ExtensionSetup, { minimum }));
}

test('automatic sending still routes old installations to bundled ZIP', () => {
  for (const installed of ['', '1.2', '1.2.0', '1.3.2']) {
    const html = setup(installed, '1.2.0', versions.AUTO_SEND_MIN_VERSION);
    assert.match(html, /href="\/studyez-extension.zip"/);
    assert.match(html, /chrome:\/\/extensions/);
    assert.match(html, /구버전 브리지는 끈 뒤/);
    assert.doesNotMatch(html, /href="https:\/\/chromewebstore/);
  }
});

test('review on old extensions uses personal requests and restores the review destination after reload', () => {
  for (const provider of ['chatgpt', 'gemini', 'claude']) {
    const input = { lectureId: '약리학/261008_01', mode: 'review', provider, prompt: 'review', files: [] };
    const wire = routing.bridgeRequest(input, '1.2.0');
    assert.equal(wire.mode, 'personal');
    assert.equal(wire.prompt, input.prompt);
    assert.equal(wire.provider, provider);
    const afterReload = load('linkRouting.ts', { './version': versions });
    const target = afterReload.linkDestination(wire.lectureId, provider);
    assert.equal(target.lectureId, input.lectureId);
    assert.equal(target.kind, `${provider}_review`);
    assert.equal(afterReload.linkDestination(input.lectureId, provider).kind, provider);
    assert.equal(afterReload.linkDestination(wire.lectureId, `${provider}_share`), null);
  }
  const native = { lectureId: '약리학/261008_01', mode: 'review' };
  assert.equal(routing.bridgeRequest(native, '1.3.5'), native);
  assert.equal(routing.linkDestination('studyez:review:', 'chatgpt'), null);
});

test('preview and review for one lecture save separately and acknowledge the original extension keys', async () => {
  let handler;
  let finishSave;
  const saved = [];
  const acknowledgements = [];
  const window = { location: { origin: 'https://studyez.kr' },
    addEventListener: (_, callback) => { handler = callback; }, removeEventListener() {},
    postMessage: message => acknowledgements.push(message),
  };
  const bridge = load('previewBridge.ts', { react: { useEffect: callback => callback() },
    './version': versions, './protocol': protocol, './linkRouting': routing }, { window });
  const lectureId = '약리학/261008_01';
  const reviewId = routing.bridgeRequest({ lectureId, mode: 'review' }, '1.2.0').lectureId;
  bridge.usePreviewLink(input => {
    saved.push(input);
    return input.kind === 'chatgpt_review' ? new Promise(resolve => { finishSave = resolve; }) : Promise.resolve();
  });
  const deliver = (id, kind = 'chatgpt') => handler({ source: window, origin: window.location.origin,
    data: { source: protocol.EXTENSION_SOURCE, type: 'LINK', lectureId: id, kind, url: 'https://chatgpt.com/c/example' },
  });
  deliver(lectureId);
  deliver(reviewId);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(saved[0].kind, 'chatgpt');
  assert.equal(saved[1].kind, 'chatgpt_review');
  assert.equal(saved[0].lectureId, saved[1].lectureId);
  assert.equal(acknowledgements.length, 1);
  finishSave();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(acknowledgements[1].lectureId, reviewId);
  assert.equal(acknowledgements[1].kind, 'chatgpt');
  deliver(reviewId, 'chatgpt_share');
  assert.equal(saved.length, 2);
  bridge.usePreviewLink(async () => { throw new Error('save failed'); });
  deliver(reviewId);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(acknowledgements.length, 2);
});

test('manual preview uses published 1.2 store release and needs no update for 1.2 installations', () => {
  assert.match(setup('', '1.2.0'), /href="https:\/\/chromewebstore/);
  assert.equal(setup('1.2', '1.2.0'), '');
  assert.equal(setup('1.2.0', '1.2.0'), '');
  assert.match(setup('1.3.0', '1.2.0'), /studyez-extension.zip/);
  assert.equal(setup('1.3.5', '1.2.0'), '');
  assert.equal(setup('', '1.2.0', '1.3.3', false), '');
});
