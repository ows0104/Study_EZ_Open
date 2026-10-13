const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'web/node_modules/typescript'));
const React = require(path.join(root, 'web/node_modules/react'));
const jsx = require(path.join(root, 'web/node_modules/react/jsx-runtime'));
const { renderToStaticMarkup } = require(path.join(root, 'web/node_modules/react-dom/server'));
let admin = true;
const dependencies = {
  react: React, 'react/jsx-runtime': jsx,
  '../api': { api() { throw Error('No request should be made while rendering a saved link'); } },
  '../bridge/previewBridge': { extensionCompatible: () => false, extensionInputMinimum: () => '1.3.11' },
  '../bridge/ExtensionSetup': { ExtensionSetup: () => React.createElement('aside',{className:'extension-setup'},'Update extension') },
  '../calendar/panelShared': {
    PanelGroup: ({children}) => React.createElement('section', null, children),
    ActionCard: ({hit, tools}) => React.createElement('div', {className:'action-card'}, hit, tools),
    PanelTool: ({label, hint}) => React.createElement('button', {title:hint}, label),
  },
  '../jobProgress': { jobMoving: () => false },
  'react-router-dom': { Link: ({to,children,...props}) => React.createElement('a', {...props,href:to}, children) },
  '../links': { bankHref: () => '/mainquiz/test' },
  '../useMe': { useMe: () => ({isAdmin:admin}) },
  './prompt': { BANK_PROMPT_VERSION:'1.32' },
  './BankCoverage': { BankCoverage: () => null },
};
const source = fs.readFileSync(path.join(root,'web/src/bank/BankPanel.tsx'),'utf8');
const compiled = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const exportsValue = {};
vm.runInNewContext(compiled,{exports:exportsValue,require:id => {
  assert.ok(id in dependencies, `Unexpected dependency ${id}`);
  return dependencies[id];
}});
const props = {lecture:{subject:'약리학',runId:'261012_01'},detail:{
  bankSources:[{kind:'notes_current'}],
  bank:{status:'ready',usable:true,shareUrl:'https://chatgpt.com/share/bank-test',conversationUrl:'https://chatgpt.com/c/private-test'},
}};
test('saved bank uses the existing main card to open its share URL without the extension, with edit below', () => {
  admin = true;
  const html = renderToStaticMarkup(React.createElement(exportsValue.BankPanel,props));
  assert.match(html,/<a class="panel-action-hit" href="https:\/\/chatgpt.com\/share\/bank-test"/);
  assert.doesNotMatch(html,/<strong>자동 출제<\/strong>|생성한 ChatGPT 대화 열기·수정/);
  assert.ok(html.indexOf('panel-aside') > html.indexOf('https://chatgpt.com/share/bank-test'));
  assert.match(html,/링크 고치기<\/button>/);
  assert.doesNotMatch(html,/extension-setup/);
});
test('student can open the shared bank but never gets the private conversation or editor', () => {
  admin = false;
  const html = renderToStaticMarkup(React.createElement(exportsValue.BankPanel,props));
  assert.match(html,/https:\/\/chatgpt.com\/share\/bank-test/);
  assert.doesNotMatch(html,/private-test|panel-aside|링크 고치기<\/button>/);
});

test('student can open the bank link before CLI succeeds', () => {
  admin = false;
  const html = renderToStaticMarkup(React.createElement(exportsValue.BankPanel, {...props,
    detail: {...props.detail, bank: {...props.detail.bank, usable: false, status: 'linked'}}}));
  assert.match(html, /https:\/\/chatgpt.com\/share\/bank-test/);
  assert.match(html, /아직 공개된 문제가 없습니다/);
  assert.doesNotMatch(html, /private-test|공부하기/);
});

test('manual input stores only URLs without an extension, source PDF, or existing bank', async () => {
  const state = [];
  let slot = 0;
  const calls = [];
  const mocked = {...dependencies,
    react: {...React, useState: initial => {
      const i = slot++;
      if (!(i in state)) state[i] = initial;
      return [state[i], value => {state[i] = typeof value === 'function' ? value(state[i]) : value;}];
    }, useEffect() {}, useCallback: callback => callback, useRef: value => ({current: value})},
    '../api': {api: async (url, options) => {calls.push({url, body: JSON.parse(options.body)});}},
    '../bridge/previewBridge': {...dependencies['../bridge/previewBridge'], bumpPreviewVersion() {}},
    '../jobProgress': {jobMoving: () => true}, // CLI running cannot block link entry.
  };
  const loaded = {};
  vm.runInNewContext(compiled, {exports: loaded, require: id => mocked[id]});
  admin = true;
  function controls() {
    slot = 0;
    const panel = loaded.BankPanel({lecture: props.lecture, detail: {bankSources: []}});
    const child = panel.props.children;
    const tree = child.type(child.props);
    const found = [];
    function visit(element) {
      if (Array.isArray(element)) return element.forEach(visit);
      if (!React.isValidElement(element)) return;
      found.push(element);
      visit(element.props.children); visit(element.props.hit); visit(element.props.tools);
    }
    visit(tree);
    return found;
  }
  const tool = controls().find(e => e.props.label === '링크 넣기');
  assert.equal(tool.props.disabled, false);
  tool.props.onClick();
  const inputs = controls().filter(e => e.type === 'input');
  assert.equal(inputs.length, 2);
  inputs[0].props.onChange({target: {value: 'https://chatgpt.com/share/manual'}});
  inputs[1].props.onChange({target: {value: 'https://chatgpt.com/c/manual'}});
  assert.ok(!controls().some(e => e.type === 'textarea'));
  controls().find(e => e.type === 'button' && e.props.children === '저장').props.onClick();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.endsWith('/bank/links'));
  assert.deepEqual(calls[0].body, {shareUrl: 'https://chatgpt.com/share/manual', conversationUrl: 'https://chatgpt.com/c/manual'});
});

test('bank creation and recreation wait for a person to send; only the separate tool sends automatically', async () => {
  const requests = [];
  const jobs = [];
  const mocked = {
    ...dependencies,
    react: {
      ...React,
      useState: value => [value, () => {}],
      useEffect: () => {},
      useCallback: callback => callback,
      useRef: value => ({current:value}),
    },
    '../api': { api: async (url, options) => {
      if (options?.method === 'POST') {jobs.push(url); return {job: {state: 'queued'}};}
      return {url:'https://example.com/notes.pdf'};
    } },
    '../bridge/previewBridge': {
      extensionCompatible: () => true,
      extensionInputMinimum: () => '1.3.11',
      absoluteUrl: url => url,
      requestPreview: async request => { requests.push(request); },
      bumpPreviewVersion() {},
    },
    './prompt': { renderBankPrompt: () => 'Bank prompt' },
  };
  const loaded = {};
  vm.runInNewContext(compiled,{exports:loaded,performance:{now:() => 1},require:id => mocked[id]});
  admin = true;
  function controls(detail) {
    const panel = loaded.BankPanel({...props,detail});
    const adminElement = panel.props.children;
    const tree = adminElement.type(adminElement.props);
    const found = [];
    function visit(element) {
      if (Array.isArray(element)) { element.forEach(visit); return; }
      if (!React.isValidElement(element)) return;
      found.push(element);
      visit(element.props.children);
      visit(element.props.hit);
      visit(element.props.tools);
    }
    visit(tree);
    return found;
  }
  async function click(control, autoSend) {
    assert.ok(control);
    assert.equal(control.props.disabled,false);
    const count = requests.length;
    control.props.onClick();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(requests.length,count + 1);
    assert.equal(requests.at(-1).autoSend,autoSend);
    assert.equal(requests.at(-1).mode,'bank');
    assert.equal(requests.at(-1).files.length,1);
  }
  const fresh = controls({...props.detail,bank:undefined});
  const primary = fresh.find(element => element.type === 'button' && element.props.className === 'panel-action-hit');
  assert.equal(primary.props.children[0].props.children,'링크 만들기');
  assert.ok(!fresh.some(element => element.props.label === '직접 전송'));
  await click(primary,false);
  await click(fresh.find(element => element.props.label === '자동전송'),true);
  const saved = controls(props.detail);
  await click(saved.find(element => element.props.label === '새로 만들기'),false);
  await click(saved.find(element => element.props.label === '자동전송'),true);
  assert.equal(jobs.length, 0); // Link creation never queues a CLI session.
  const count = requests.length;
  fresh.find(element => element.type === 'button' && element.props.children === 'Main-Quiz 만들기').props.onClick();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, count);
  assert.equal(jobs.length, 1);
  assert.ok(jobs[0].endsWith('/prequiz-job?kind=bank'));
});
