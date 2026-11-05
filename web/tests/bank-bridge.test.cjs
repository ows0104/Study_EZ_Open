const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../node_modules/typescript');
const source = fs.readFileSync(path.join(__dirname, '../src/bank/bankBridge.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const routingExports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/bridge/linkRouting.ts'), 'utf8'),
  {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,
  {exports:routingExports, require:()=>({versionAtLeast:()=>true})});

function fixture(fail = false) {
  let handle, bumps = 0;
  const calls = [], posted = [];
  const window = {location: {origin: 'https://studyez.kr'},
    addEventListener: (_, fn) => { handle = fn; }, removeEventListener() {},
    postMessage: message => posted.push(message)};
  const exports = {};
  const dependencies = {
    react: {useEffect: fn => fn()},
    '../api': {api: async (url, options) => {calls.push({url, body: JSON.parse(options.body)}); if (fail) throw Error('Save failed');}},
    '../bridge/previewBridge': {bumpPreviewVersion: () => {bumps++;}},
    '../bridge/linkRouting': routingExports,
    './rootWeb': {webGenerationId:()=>null},
    './responseFile': {validBankFile:()=>false},
    '../bridge/protocol': {EXTENSION_SOURCE: 'ext', WEBAPP_SOURCE: 'web', MESSAGES: {
      bankReady: 'BANK', bankSaved: 'BANK_SAVED', linkReady: 'LINK', linkSaved: 'LINK_SAVED'}},
  };
  vm.runInNewContext(compiled, {exports, window, require: id => dependencies[id]});
  exports.useBankLink();
  async function send(data) {
    handle({source: window, origin: window.location.origin, data: {source: 'ext', lectureId: 'test/261013_01', ...data}});
    await new Promise(resolve => setImmediate(resolve));
  }
  return {send, calls, posted, get bumps() {return bumps;}};
}

test('bank links save individually and acknowledge only the saved kind', async () => {
  const s = fixture();
  await s.send({type: 'LINK', kind: 'chatgpt_bank', url: 'https://chatgpt.com/c/bank'});
  await s.send({type: 'LINK', kind: 'chatgpt_bank_share', url: 'https://chatgpt.com/share/bank'});
  assert.deepEqual(s.calls.map(c => c.body), [{conversationUrl: 'https://chatgpt.com/c/bank'}, {shareUrl: 'https://chatgpt.com/share/bank'}]);
  assert.ok(s.calls.every(c => c.url.endsWith('/bank/links')));
  assert.deepEqual(s.posted.map(m => m.kind), ['chatgpt_bank', 'chatgpt_bank_share']);
  assert.equal(s.bumps, 2);
});

test('failed saves remain pending and preview messages are ignored', async () => {
  const s = fixture(true);
  await s.send({type: 'LINK', kind: 'chatgpt_bank_share', url: 'https://chatgpt.com/share/bank'});
  await s.send({type: 'LINK', kind: 'chatgpt_share', url: 'https://chatgpt.com/share/preview'});
  assert.equal(s.calls.length, 1);
  assert.equal(s.posted.length, 0);
  assert.equal(s.bumps, 0);
});

test('old extension pending answers recover links without storing a response or queuing CLI', async () => {
  const s = fixture();
  await s.send({type: 'BANK', raw: 'unfinished response', url: 'https://chatgpt.com/c/old', shareUrl: 'https://chatgpt.com/share/old'});
  assert.deepEqual(s.calls[0].body, {conversationUrl: 'https://chatgpt.com/c/old', shareUrl: 'https://chatgpt.com/share/old'});
  assert.ok(s.calls[0].url.endsWith('/bank/links'));
  assert.equal(s.posted[0].type, 'BANK_SAVED');
});

test('complete bank answer starts review and acknowledges only after saving', async () => {
  const s = fixture();
  const raw = '문항 '.repeat(100) + '\nSTUDYEZ_BANK_COMPLETE';
  await s.send({type:'BANK', raw, url:'https://chatgpt.com/c/complete'});
  assert.ok(s.calls[0].url.endsWith('/bank-response'));
  assert.equal(s.calls[0].body.raw, raw);
  assert.equal(s.posted[0].type, 'BANK_SAVED');
  const failed = fixture(true);
  await failed.send({type:'BANK', raw, url:'https://chatgpt.com/c/complete'});
  assert.equal(failed.posted.length, 0);
});

test('legacy extension round trip preserves the launch version in answers, links and acknowledgements', async () => {
  const payload = routingExports.bridgeRequest({mode:'bank', lectureId:'test/261013_01', promptVersion:'1.53'}, '1.3.15');
  const s = fixture();
  await s.send({type:'BANK', lectureId:payload.lectureId, raw:'문항 '.repeat(100)+'\nSTUDYEZ_BANK_COMPLETE',
    promptVersion:'', url:'https://chatgpt.com/c/legacy'});
  assert.equal(s.calls[0].body.promptVersion, '1.53');
  assert.equal(s.calls[0].url, '/api/admin/lectures/test/261013_01/bank-response');
  assert.equal(s.posted[0].lectureId, payload.lectureId);
  await s.send({type:'LINK', lectureId:payload.lectureId, kind:'chatgpt_bank_share', url:'https://chatgpt.com/share/legacy'});
  assert.equal(s.calls[1].url, '/api/admin/lectures/test/261013_01/bank/links');
  assert.equal(s.posted[1].lectureId, payload.lectureId);
  assert.throws(()=>routingExports.bridgeRequest({mode:'bank',lectureId:'test/run'},'1.3.15'), /버전/);
});
