const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const source = fs.readFileSync(path.join(__dirname, '../src/bank/BankBuildTimes.tsx'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
}}).outputText;
const loaded = {};
vm.runInNewContext(compiled, {exports: loaded, require, Intl, Date, Number});
const render = timeline => renderToStaticMarkup(React.createElement(loaded.BankBuildTimes, {timeline}));

test('shows separate link and upload clocks in Korean time, including seconds', () => {
  const html = render({linkedAt: '2026-10-15T04:05:06Z', builtAt: '2026-10-15T05:06:07Z'});
  assert.match(html, /퀴즈 링크 생성/);
  assert.match(html, /13:05:06/);
  assert.match(html, /최종퀴즈 업로드/);
  assert.match(html, /14:06:07/);
  assert.match(html, /한국 시간/);
  assert.match(html, /dateTime="2026-10-15T04:05:06Z"/);
});

test('never invents dates for old links or pending uploads', () => {
  assert.equal(render(null), '');
  assert.equal(render({linkedAt: null, builtAt: null}), '');
  assert.equal(render({linkedAt: 'invalid', builtAt: null}), '');
  assert.doesNotMatch(render({linkedAt: '2026-10-15T04:05:06Z', builtAt: null}), /최종퀴즈 업로드/);
});
