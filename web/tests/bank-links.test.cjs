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
  '../bridge/ExtensionSetup': { ExtensionSetup: () => null },
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
  assert.match(html,/수정<\/button>/);
});
test('student can open the shared bank but never gets the private conversation or editor', () => {
  admin = false;
  const html = renderToStaticMarkup(React.createElement(exportsValue.BankPanel,props));
  assert.match(html,/https:\/\/chatgpt.com\/share\/bank-test/);
  assert.doesNotMatch(html,/private-test|panel-aside|수정<\/button>/);
});
