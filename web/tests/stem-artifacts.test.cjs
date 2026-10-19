const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
function load(file) {
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const context = vm.createContext({ exports: {}, require: name => {
    if (!name.startsWith('.')) return require(name);
    const target = path.resolve(path.dirname(file), name);
    return load(fs.existsSync(target + '.tsx') ? target + '.tsx' : target + '.ts');
  }});
  vm.runInContext(js, context);
  return context.exports;
}
const { BankStem } = load(path.join(__dirname, '../src/bank/BankStem.tsx'));
const { stemText } = load(path.join(__dirname, '../src/bank/stemText.ts'));
test('transport tags and blank code wrappers disappear before cloze splitting', () => {
  const text = '<escape>경로 **비교**: `{{c1}}` → <escape>{{c1}}</escape>.</escape>';
  for (const answerUnits of [undefined, ['첫째', '둘째']]) {
    const html = renderToStaticMarkup(React.createElement(BankStem, { text, cloze: true, answerUnits }));
    assert.doesNotMatch(html, /escape|`|\{\{c/);
    assert.match(html, /<strong>비교<\/strong>/);
    assert.ok(html.indexOf(answerUnits ? '첫째' : '[ 1 ]') < html.indexOf(answerUnits ? '둘째' : '[ 2 ]'));
  }
});
test('scientific comparisons, apostrophes and intentional quotations are preserved', () => {
  const text = "Ccr <50, Ccr >50; Cushing’s, '부교감 → 교감', 3′, `NET`";
  assert.equal(stemText(text), text);
  assert.equal(stemText('<escape>{{c2}}</escape>와 ``{{c1}}``'), '{{c2}}와 {{c1}}');
});
