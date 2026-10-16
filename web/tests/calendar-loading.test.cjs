const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.CALENDAR_TEST_URL || 'http://127.0.0.1:5198/tests/calendar-loading.html';

test('startup loads only metadata; learning and bundles are opt-in and scoped', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const requests = () => page.evaluate(() => window.calendarTest.requests);
  try {
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /시간표 강의 0/ }).waitFor();
    assert.deepEqual((await requests()).sort(), ['/api/me', '/api/timetable?include_study=false'].sort());
    assert.equal(await page.locator('.chip-learning-pair').count(), 0);
    const modules = await page.evaluate(() => performance.getEntriesByType('resource').map(r => r.name));
    assert(!modules.some(url => /\/(EventPanel|LecturePage)\.tsx/.test(url)));
    await page.evaluate(() => { window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('focus')); });
    assert.equal((await requests()).filter(r => r.includes('/timetable')).length, 1);
    await page.getByRole('button', { name: '학습률 보기', exact: true }).click();
    await page.getByRole('status').filter({ hasText: '표시된 기간의 학습률' }).waitFor();
    let enriched = (await requests()).filter(r => r.includes('include_cards=false'));
    assert.equal(enriched.length, 1);
    assert.match(enriched[0], /start=2026-10-12&end=2026-10-16/);
    assert.equal(await page.getByRole('button', { name: /시간표 강의 0/ }).count(), 1);
    await page.evaluate(() => window.calendarTest.release());
    await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).waitFor();
    await page.getByRole('button', { name: '학습률 접기', exact: true }).click();
    await page.getByRole('button', { name: '다음', exact: true }).click();
    await page.getByRole('button', { name: /시간표 강의 1/ }).waitFor();
    assert.equal((await requests()).filter(r => r.includes('include_cards=false')).length, 1);
    await page.getByRole('button', { name: '덱 모아받기 보기', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.some(r => r.startsWith('/api/bundles/decks')));
    assert((await requests()).filter(r => r.startsWith('/api/bundles/decks')).every(r => r.includes('start=2026-10-19&end=2026-10-23')));
    await page.getByRole('button', { name: '덱 모아받기 접기', exact: true }).click();
    await page.getByRole('button', { name: '이전', exact: true }).click();
    await page.getByRole('button', { name: /시간표 강의 0/ }).click();
    await page.getByRole('heading', { name: '시간표 강의 0', exact: true }).waitFor();
    await page.getByRole('link', { name: '강의 화면 전체 보기 →', exact: true }).waitFor();
    assert((await requests()).some(r => r === '/api/lectures/subject/run-0'));
    assert.equal((await requests()).filter(r => r.startsWith('/api/bundles/decks')).length, 1);
    await page.getByText('subject 블럭 덱 받기', { exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.includes('/api/bundles/decks?subject=subject'));
    await page.getByRole('button', { name: '닫기', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});

test('failed learning leaves timetable usable and retryable; students never load bundle lists', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?student&learningFail', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /시간표 강의 0/ }).waitFor();
    assert.equal(await page.getByRole('button', { name: /덱 모아받기/ }).count(), 0);
    await page.getByRole('button', { name: '학습률 보기', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '학습률 조회 실패' }).waitFor();
    assert.equal(await page.getByRole('button', { name: /시간표 강의 0/ }).count(), 1);
    await page.getByRole('button', { name: '다시 시도', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 2);
    await page.evaluate(() => window.calendarTest.release());
    await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).waitFor();
    assert.equal(await page.getByRole('alert').count(), 0);
    assert.equal(await page.evaluate(() => window.calendarTest.requests.filter(r => r.startsWith('/api/bundles/decks')).length), 0);
  } finally { await browser.close(); }
});

test('changing a visible period cancels stale learning; month uses the displayed six weeks', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?student', { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: '학습률 보기', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 1);
    await page.getByRole('button', { name: '다음', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 2);
    await page.evaluate(() => window.calendarTest.release());
    assert.equal(await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).count(), 0);
    await page.evaluate(() => window.calendarTest.release());
    await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).waitFor();
    await page.getByRole('button', { name: '월', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.some(r => r.includes('start=2026-09-28&end=2026-11-06&include_cards=false')));
    await page.getByRole('button', { name: '학습률 접기', exact: true }).click();
    await page.evaluate(() => window.calendarTest.release());
    assert.equal(await page.locator('.chip-learning-pair').count(), 0);
    assert.equal(await page.getByRole('alert').count(), 0);
  } finally { await browser.close(); }
});
