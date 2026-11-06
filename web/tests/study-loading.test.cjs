const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5197/tests/study-management.html';

// 강의 목록은 학습 현황을 자동으로 읽는다(2026-11 개편, 토글 없음). 목록이 먼저 그려지고 선택한 블럭만 8강의씩 읽는다.
const rows = page => page.locator('.list-table .list-row:not(.is-head)');
const cards = page => page.locator('.list-stats b').nth(2).innerText();
const pickBlock = async (page, name) => {
  await page.locator('.block-picker-button').click();
  await page.getByRole('option', { name: new RegExp(`^${name}`) }).click();
};
const statsAre = (page, text) => page.waitForFunction(value => document.querySelectorAll('.list-stats b')[2]?.textContent === value, text);

test('list renders before progress; only the selected block loads in bounded batches', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '?lazy');
    await page.getByRole('heading', { name: '강의 목록', exact: true }).waitFor();
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 1);
    // The first batch is still held: rows are listed, numbers wait.
    assert.equal(await rows(page).count(), 10);
    assert.equal(await cards(page), '—장');
    assert.equal(await page.locator('.list-table .list-row.is-closed').count(), 10);
    let batches = await page.evaluate(() => window.studyTest.progressRequests);
    assert.equal(batches[0].length, 8);
    assert(batches[0].every(l => l.subject === '약리학'));
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 2);
    assert.equal(await cards(page), '—장');
    batches = await page.evaluate(() => window.studyTest.progressRequests);
    assert.equal(batches[1].length, 2);
    await page.evaluate(() => window.studyTest.release());
    await statsAre(page, '1,000장');
    assert.equal(await page.locator('.list-table .list-row.is-closed').count(), 0);
    assert.equal(await page.locator('.stage-legend .stage-text-retained').innerText(), '250');
    await pickBlock(page, '다른 블록');
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 3);
    assert.equal(await rows(page).count(), 1);
    await page.evaluate(() => window.studyTest.release());
    await statsAre(page, '100장');
    await pickBlock(page, '약리학');
    assert.equal(await cards(page), '1,000장');
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 3);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});

test('switching blocks cancels remaining batches; a failed summary can be retried', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?lazy');
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 1);
    await pickBlock(page, '다른 블록');
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 2);
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests[1][0].subject), '다른 과목');
    // The first release resolves the aborted 약리학 batch; it must not continue to its second batch.
    await page.evaluate(() => { window.studyTest.release(); window.studyTest.release(); });
    await statsAre(page, '100장');
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 2);
    await page.goto(base + '?lazy&progressError');
    await page.getByRole('alert').filter({ hasText: '학습 현황 조회 실패' }).waitFor();
    assert.equal(await rows(page).count(), 10);
    await page.getByRole('button', { name: '다시 시도', exact: true }).click();
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 2);
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 3);
    await page.evaluate(() => window.studyTest.release());
    await statsAre(page, '1,000장');
    await page.waitForFunction(() => document.querySelectorAll('[role="alert"]').length === 0);
  } finally { await browser.close(); }
});
