const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const ts = require('typescript');

// Remembered screen toggles (2026-11-11): the value a person clicked stays their default in this browser.
function load(localStorage) {
  const source = fs.readFileSync(path.join(__dirname, '../src/preferences.ts'), 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const context = vm.createContext({ exports: {}, localStorage, require: () => ({ useState: () => [], useCallback: f => f }) });
  vm.runInContext(js, context);
  return context.exports;
}
function memory(initial = {}) {
  const items = { ...initial };
  return { items, getItem: k => (k in items ? items[k] : null), setItem: (k, v) => { items[k] = String(v); } };
}

test('saved value is read back; missing or unknown values fall back', () => {
  const store = memory({ 'studyez-list-view': 'order', 'studyez-sidebar': 'yes' });
  const { readPreference, savePreference } = load(store);
  assert.equal(readPreference('studyez-list-view', 'type', ['type', 'order']), 'order');
  assert.equal(readPreference('studyez-sidebar', '0', ['1', '0']), '0');
  assert.equal(readPreference('studyez-map-links', '0', ['1', '0']), '0');
  savePreference('studyez-map-links', '1');
  assert.equal(store.items['studyez-map-links'], '1');
  assert.equal(readPreference('studyez-map-links', '0', ['1', '0']), '1');
});

test('blocked storage keeps the screen working with the fallback', () => {
  const blocked = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  const { readPreference, savePreference } = load(blocked);
  assert.equal(readPreference('studyez-sidebar', '1', ['1', '0']), '1');
  assert.doesNotThrow(() => savePreference('studyez-sidebar', '0'));
});

test('every remembered toggle uses the shared helper with its key', () => {
  const src = f => fs.readFileSync(path.join(__dirname, '../src', f), 'utf8');
  assert.match(src('shell/Sidebar.tsx'), /useFlagPreference\(KEY\)/);
  assert.match(src('shell/Sidebar.tsx'), /const KEY = "studyez-sidebar"/);
  assert.match(src('bank/StudyOverview.tsx'), /usePreference<ListView>\(VIEW_KEY, "type", VIEWS\)/);
  assert.match(src('bank/RootMap.tsx'), /useFlagPreference\('studyez-map-questions'\)/);
  assert.match(src('bank/RootMap.tsx'), /useFlagPreference\('studyez-map-links'\)/);
  assert.match(src('admin/BankReportTab.tsx'), /useFlagPreference\("studyez-admin-report-done"\)/);
  assert.match(src('admin/CardReviewTab.tsx'), /useFlagPreference\("studyez-admin-card-done"\)/);
});
