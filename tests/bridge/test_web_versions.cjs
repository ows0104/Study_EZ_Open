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
const protocol = {
  READY_ATTRIBUTE: 'data-studyez-ai-extension', EXTENSION_SOURCE: 'studyez-ai-extension',
  WEBAPP_SOURCE: 'studyez-webapp', MESSAGES: { openPreview: 'OPEN', openPreviewResult: 'RESULT' },
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
    ['1.2', 'personal', false, true], ['1.2.0', 'shared', false, true], ['1.2.0', 'bank', false, true],
    ['1.2.0', 'shared', true, false], ['1.2.0', 'review', false, false],
    ['1.3.0', 'personal', false, false], ['1.3.2', 'bank', false, false],
    ['1.3.2', 'shared', true, false], ['1.3.3', 'personal', false, true],
    ['1.3.3', 'shared', true, true], ['1.3.3', 'review', false, false],
    ['1.3.5', 'review', false, true], ['1.4', 'shared', false, true],
  ]) {
    let sent = 0;
    let handler;
    const window = {
      location: { origin: 'https://studyez.kr' }, setTimeout: () => 1, clearTimeout() {},
      addEventListener: (_, callback) => { handler = callback; }, removeEventListener() {},
      postMessage: message => {
        sent++;
        handler({ source: window, origin: window.location.origin, data: {
          source: protocol.EXTENSION_SOURCE, type: 'RESULT', requestId: message.payload.requestId, ok: true,
        } });
      },
    };
    const bridge = load('previewBridge.ts', { react, './version': versions, './protocol': protocol }, {
      window, document: { documentElement: { getAttribute: () => installed } },
    });
    const request = bridge.requestPreview({ requestId: 'case', mode, files: [], autoSend });
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

test('automatic and review features still route old installations to bundled ZIP', () => {
  for (const installed of ['', '1.2', '1.2.0', '1.3.2']) {
    const html = setup(installed, '1.2.0', versions.AUTO_SEND_MIN_VERSION);
    assert.match(html, /href="\/studyez-extension.zip"/);
    assert.match(html, /chrome:\/\/extensions/);
    assert.match(html, /구버전 브리지는 끈 뒤/);
    assert.doesNotMatch(html, /href="https:\/\/chromewebstore/);
  }
  assert.match(setup('1.3.3', '1.3.3', '1.3.5'), /studyez-extension.zip/);
});

test('manual preview uses published 1.2 store release and needs no update for 1.2 installations', () => {
  assert.match(setup('', '1.2.0'), /href="https:\/\/chromewebstore/);
  assert.equal(setup('1.2', '1.2.0'), '');
  assert.equal(setup('1.2.0', '1.2.0'), '');
  assert.match(setup('1.3.0', '1.2.0'), /studyez-extension.zip/);
  assert.equal(setup('1.3.5', '1.2.0'), '');
  assert.equal(setup('', '1.2.0', '1.3.3', false), '');
});
