const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const ts = require('typescript');

function load(file, globals = {}) {
  const source = fs.readFileSync(path.join(__dirname, '../src', file), 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const context = vm.createContext({ exports: {}, URL, ...globals });
  vm.runInContext(js, context);
  return context.exports;
}

function setup() {
  let now = 0;
  const images = [];
  class Image {
    constructor() { images.push(this); }
    decode() { this.decoded = true; return Promise.resolve(); }
  }
  const { SlidePreloader } = load('slidePreload.ts', {
    Image, Date: { now: () => now }, window: { location: { href: 'https://study.test/' } },
  });
  return { cache: new SlidePreloader(), images, advance: (ms) => { now += ms; } };
}

const url = (page, signature) => `https://slides.test/${page}.png?X-Amz-Signature=${signature}`;

test('reveal reuses the exact preloaded URL, including an in-flight image', () => {
  const { cache, images } = setup();
  cache.warm([url(1, 'old'), url(1, 'new')]);
  assert.equal(images.length, 1);
  assert.equal(images[0].decoded, true);
  assert.equal(cache.resolve(url(1, 'fresh')), url(1, 'old'));
  assert.equal(cache.resolve(url(2, 'fresh')), url(2, 'fresh'));
});

test('failed and expired preloads fall back to fresh reveal URLs', () => {
  const { cache, images, advance } = setup();
  cache.warm([url(1, 'old')]);
  images[0].onerror();
  assert.equal(cache.resolve(url(1, 'fresh')), url(1, 'fresh'));
  cache.warm([url(1, 'retry')]);
  advance(45_001);
  assert.equal(cache.resolve(url(1, 'fresh')), url(1, 'fresh'));
});

test('retained images are bounded and different resources never share a preload', () => {
  const { cache } = setup();
  cache.warm(Array.from({ length: 13 }, (_, i) => url(i, 'old')));
  assert.equal(cache.resolve(url(0, 'fresh')), url(0, 'fresh'));
  assert.equal(cache.resolve(url(12, 'fresh')), url(12, 'old'));
  assert.equal(cache.resolve(url(12, 'fresh') + '&version=2'), url(12, 'fresh') + '&version=2');
});

test('a loaded image survives long thinking time and reuses the same DOM node', () => {
  const { cache, images, advance } = setup();
  cache.warm([url(1, 'old')]);
  images[0].complete = true;
  images[0].naturalWidth = 800;
  advance(600_000);
  cache.warm([url(1, 'fresh')]);
  assert.equal(images.length, 1);
  assert.equal(cache.get(url(1, 'fresh')), images[0]);
  images[0].isConnected = true;
  assert.equal(cache.get(url(1, 'fresh')), undefined, 'do not steal an image from another mounted view');
});

test('lookahead follows review order, forced undo cards, and cram exclusions', () => {
  const { upcoming } = load('lecture/queue.ts');
  const item = (itemId, state, dueAt) => ({ itemId, attempt: state ? { state, dueAt } : null });
  const items = [item('new'), item('future', 'review', '2030-01-01'),
    item('review', 'review', '2020-01-01'), item('learning', 'learning', '2020-01-02')];
  const ids = (options) => Array.from(upcoming(items, Date.parse('2026-01-01'), options), (q) => q.itemId);
  assert.deepEqual(ids({}), ['learning', 'review', 'new']);
  assert.deepEqual(ids({ forcedId: 'future' }), ['future', 'learning', 'review']);
  assert.deepEqual(ids({ cram: true, seen: new Set(['learning', 'review']) }), ['future', 'new']);
});
