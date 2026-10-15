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

test('missing semantic evidence never promotes the first cited slide to core evidence', () => {
  const { primary, extra } = splitSlides([slide(9), slide(10), slide(11)]);
  assert.deepEqual(Array.from(primary, s => s.page), []);
  assert.deepEqual(Array.from(extra, s => s.page), [9, 10, 11]);
  const html = renderToStaticMarkup(React.createElement(BankSlides, { slides: [slide(9, false)] }));
  assert.match(html, /확인된 핵심 근거 슬라이드가 없습니다/);
  assert.doesNotMatch(html, /alt="필기/);
});

test('a selected single page is shown even when it is the last cited page', () => {
  const { primary, extra } = splitSlides([slide(1, false), slide(2, false), slide(9, true)]);
  assert.deepEqual(Array.from(primary, s => s.page), [9]);
  assert.deepEqual(Array.from(extra, s => s.page), [1, 2]);
});

test('empty references render nothing and a single reference needs no expander', () => {
  assert.equal(renderToStaticMarkup(React.createElement(BankSlides, { slides: [] })), '');
  const html = renderToStaticMarkup(React.createElement(BankSlides, { slides: [slide(2, true)] }));
  assert.match(html, /alt="필기 2쪽"/);
  assert.doesNotMatch(html, /<details/);
});

test('equal page numbers in different lectures stay distinct and show their original source', () => {
  const own = { ...slide(8, false), sourceId: 'self', sourceFilename: '내 강의.pdf' };
  const other = { ...slide(8, true), sourceId: '261008_02', sourceFilename: '순환기 기초2.pdf', url: 'https://example.test/other-8.png' };
  const { primary, extra } = splitSlides([own, other]);
  assert.deepEqual(Array.from(primary, s => s.sourceId), ['261008_02']);
  assert.deepEqual(Array.from(extra, s => s.sourceId), ['self']);
  const html = renderToStaticMarkup(React.createElement(BankSlides, { slides: [own, other] }));
  assert.match(html, /다른 강의/);
  assert.match(html, /순환기 기초2.pdf/);
  assert.match(html, /PDF 8쪽/);
  assert.doesNotMatch(html, /alt="필기 8쪽"/);
  assert.match(html, /추가 참고 슬라이드 1장/);
});
