const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const source = fs.readFileSync(path.join(__dirname, '../src/bank/BankSlides.tsx'), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
} }).outputText;
const context = vm.createContext({ exports: {}, require: name => name.endsWith('/SlideImage')
  ? { SlideImage: ({ src, alt }) => React.createElement('img', { src, alt }) } : require(name) });
vm.runInContext(js, context);
const { BankSlides, splitSlides } = context.exports;
const slide = (page, primary) => ({ page, primary, url: `https://example.test/${page}.png` });

test('only marked slides render initially; extra references stay closed and unloaded', () => {
  const slides = [slide(1, false), slide(3, true), slide(4, false), slide(8, true)];
  const html = renderToStaticMarkup(React.createElement(BankSlides, { slides }));
  assert.match(html, /alt="필기 3쪽"/);
  assert.match(html, /alt="필기 8쪽"/);
  assert.doesNotMatch(html, /alt="필기 (1|4)쪽"/);
  assert.match(html, /<summary>추가 참고 슬라이드 2장<\/summary>/);
  assert.doesNotMatch(html, /<details[^>]*\bopen/);
});

test('older API responses show one slide and retain the rest for expansion', () => {
  const { primary, extra } = splitSlides([slide(9), slide(10), slide(11)]);
  assert.deepEqual(Array.from(primary, s => s.page), [9]);
  assert.deepEqual(Array.from(extra, s => s.page), [10, 11]);
});

test('empty references render nothing and a single reference needs no expander', () => {
  assert.equal(renderToStaticMarkup(React.createElement(BankSlides, { slides: [] })), '');
  const html = renderToStaticMarkup(React.createElement(BankSlides, { slides: [slide(2, true)] }));
  assert.match(html, /alt="필기 2쪽"/);
  assert.doesNotMatch(html, /<details/);
});
