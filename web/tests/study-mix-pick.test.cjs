const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5197/tests/study-management.html';

// 강의 목록 → Main-Quiz 강의 체크 → 아래 막대 「모아풀기」 → 고른 강의를 실은 모아풀기 주소(2026-11-18).
test('study list: Main-Quiz lectures can be picked and open 모아풀기', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '?lazy&student', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.getByRole('heading', { name: '강의 목록', exact: true }).waitFor();
    // The slow summaries are held in ?lazy; selection does not wait for them.
    const bar = page.getByRole('region', { name: '모아풀기' });
    assert.equal(await bar.count(), 0);
    await page.getByRole('checkbox', { name: '강의 3 선택', exact: true }).click();
    await page.getByRole('checkbox', { name: '강의 0 선택', exact: true }).click();
    assert.match(await bar.innerText(), /2개 강의\s*선택/);
    await bar.getByRole('button', { name: '복습퀴즈 모아풀기', exact: true }).click();
    const probe = page.getByRole('status', { name: '모아풀기 주소' });
    // List order (date, then key), not click order.
    assert.deepEqual(JSON.parse(await probe.innerText()), [{ subject: '약리학', runId: '0' }, { subject: '약리학', runId: '3' }]);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});

// 족보 모아풀기(2026-11-18-jokbo-mix): 족보만 있는 칸도 체크되고, 막대의 「족보 모아풀기」는 고른 강의의 시간표 칸을 싣는다.
test('study list: jokbo-only lectures can be picked; the bar splits into review and jokbo mix', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
  page.setDefaultTimeout(10000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '?lazy&student', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.getByRole('heading', { name: '강의 목록', exact: true }).waitFor();
    // The jokbo-only row gets its box once the summaries arrive.
    const jokboOnly = page.getByRole('checkbox', { name: '족보만 선택', exact: true });
    await jokboOnly.click();
    const bar = page.getByRole('region', { name: '모아풀기' });
    // Only a jokbo lecture chosen: the review button is off.
    assert.equal(await bar.getByRole('button', { name: '복습퀴즈 모아풀기', exact: true }).isDisabled(), true);
    await page.getByRole('checkbox', { name: '강의 2 선택', exact: true }).click();
    await page.getByRole('checkbox', { name: '강의 5 선택', exact: true }).click();
    assert.match(await bar.innerText(), /3개 강의\s*선택/);
    await bar.getByRole('button', { name: '족보 모아풀기', exact: true }).click();
    // Lectures 2 and 5 sit in one timetable cell: one jokbo. List order.
    assert.deepEqual(JSON.parse(await page.getByRole('status', { name: '족보 모아풀기 주소' }).innerText()), ['0', 'j']);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});
