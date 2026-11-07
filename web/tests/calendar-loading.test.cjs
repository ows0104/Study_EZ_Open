const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.CALENDAR_TEST_URL || 'http://127.0.0.1:5198/tests/calendar-loading.html';

// 2026-11 개편: 회독·학습률은 늘 보인다(토글 없음). 첫 화면 요청은 그대로 두고, 그린 뒤 보이는 범위만 이어 받는다.
const learning = r => r.includes('include_cards=false');

test('startup loads metadata first; learning follows for the visible range; bundles stay opt-in and scoped', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const requests = () => page.evaluate(() => window.calendarTest.requests);
  try {
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /시간표 강의 0/ }).waitFor();
    const first = await requests();
    assert.deepEqual(first.slice(0, 2).sort(), ['/api/me', '/api/timetable?include_study=false'].sort());
    // 그 뒤에 나가는 것은 보이는 범위의 학습률과 오늘 복습 수뿐이다.
    assert(first.slice(2).every(r => learning(r) || r === '/api/timetable/study-progress'), first.join(', '));
    const modules = await page.evaluate(() => performance.getEntriesByType('resource').map(r => r.name));
    assert(!modules.some(url => /\/(EventPanel|LecturePage)\.tsx/.test(url)));
    await page.evaluate(() => { window.dispatchEvent(new Event('focus')); window.dispatchEvent(new Event('focus')); });
    assert.equal((await requests()).filter(r => r.startsWith('/api/timetable?include_study=false')).length, 1);
    await page.waitForFunction(() => window.calendarTest.requests.some(r => r.includes('include_cards=false')));
    let enriched = (await requests()).filter(learning);
    assert.equal(enriched.length, 1);
    assert.match(enriched[0], /start=2026-10-12&end=2026-10-16/);
    assert.equal(await page.getByRole('button', { name: /시간표 강의 0/ }).count(), 1);
    await page.evaluate(() => window.calendarTest.release());
    await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).waitFor({ state: 'attached' });
    await page.getByRole('button', { name: '다음', exact: true }).click();
    await page.getByRole('button', { name: /시간표 강의 1/ }).waitFor();
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 2);
    assert.match((await requests()).filter(learning)[1], /start=2026-10-19&end=2026-10-23/);
    await page.evaluate(() => window.calendarTest.release());
    // 2026-11-07: 캘린더 머리의 「덱 모아받기 보기」는 관리자에게도 없앴다. 블럭 덱은 패널 「관리자」에서만 펼칠 때 부른다.
    assert.equal(await page.getByRole('button', { name: /덱 모아받기/ }).count(), 0);
    await page.getByRole('button', { name: '이전', exact: true }).click();
    await page.getByRole('button', { name: /시간표 강의 0/ }).click();
    await page.getByRole('heading', { name: '시간표 강의 0', exact: true }).waitFor();
    // 관리 도구·강의 화면 링크는 패널 아래 「관리자」 접힘 안에 있다.
    await page.getByText('관리자', { exact: true }).click();
    await page.getByRole('link', { name: '강의 화면 전체 보기 →', exact: true }).waitFor();
    assert((await requests()).some(r => r === '/api/lectures/subject/run-0'));
    assert.equal((await requests()).filter(r => r.startsWith('/api/bundles/decks')).length, 0);
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
    await page.getByRole('alert').filter({ hasText: '학습률 조회 실패' }).waitFor();
    assert.equal(await page.getByRole('button', { name: /시간표 강의 0/ }).count(), 1);
    await page.getByRole('button', { name: '다시 시도', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 2);
    await page.evaluate(() => window.calendarTest.release());
    await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).waitFor({ state: 'attached' });
    assert.equal(await page.getByRole('alert').count(), 0);
    assert.equal(await page.evaluate(() => window.calendarTest.requests.filter(r => r.startsWith('/api/bundles/decks')).length), 0);
  } finally { await browser.close(); }
});

test('changing a visible week cancels stale learning; there is no month view', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?student', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 1);
    await page.getByRole('button', { name: '다음', exact: true }).click();
    await page.waitForFunction(() => window.calendarTest.requests.filter(r => r.includes('include_cards=false')).length === 2);
    await page.evaluate(() => window.calendarTest.release());
    assert.equal(await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).count(), 0);
    await page.evaluate(() => window.calendarTest.release());
    await page.locator('.chip-learning-value').filter({ hasText: '복습 50%' }).waitFor({ state: 'attached' });
    // 2026-11-07: 주/월 전환·오늘 버튼 없이 날짜 줄 양끝 화살표만 있다.
    assert.equal(await page.getByRole('button', { name: '월', exact: true }).count(), 0);
    assert.equal(await page.getByRole('button', { name: '오늘', exact: true }).count(), 0);
    // 화면 높이에 맞춰 한 주가 스크롤 없이 들어간다.
    const grid = page.locator('.week-calendar');
    assert.equal(await grid.evaluate(el => el.scrollHeight > el.clientHeight + 1), false);
    assert.equal(await page.getByRole('alert').count(), 0);
  } finally { await browser.close(); }
});
