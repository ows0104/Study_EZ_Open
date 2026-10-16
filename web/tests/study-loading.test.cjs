const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5197/tests/study-management.html';

test('list renders before progress; only selected blocks load in bounded batches', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '?lazy');
    await page.getByRole('heading', { name: '학습 현황', exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 0);
    assert.equal(await page.locator('.overview-stats').count(), 0);
    assert.equal(await page.locator('.overview-table thead th').count(), 4);
    assert.equal(await page.locator('.overview-table tbody tr td:last-child > a').count(), 10);
    await page.getByText('학습 현황 보기', { exact: true }).click();
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 1);
    assert.equal(await page.locator('.overview-table tbody tr').count(), 10);
    assert.equal(await page.locator('.overview-stats strong').nth(1).innerText(), '—개');
    let batches = await page.evaluate(() => window.studyTest.progressRequests);
    assert.equal(batches[0].length, 8);
    assert(batches[0].every(l => l.subject === '약리학'));
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 2);
    assert.equal(await page.locator('.overview-stats strong').nth(1).innerText(), '—개');
    batches = await page.evaluate(() => window.studyTest.progressRequests);
    assert.equal(batches[1].length, 2);
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => document.querySelectorAll('.overview-table tbody tr td:last-child > a').length === 10);
    assert.equal(await page.locator('.overview-stats strong').nth(1).innerText(), '1,000개');
    const blocks = page.locator('.overview-heading select');
    await blocks.selectOption('다른 블록');
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 3);
    assert.equal(await page.locator('.overview-table tbody tr').count(), 1);
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => document.querySelector('.overview-stats strong')?.textContent === '1강의'
      && document.querySelectorAll('.overview-table tbody tr td:last-child > a').length === 1);
    await blocks.selectOption('약리학');
    assert.equal(await page.locator('.overview-stats strong').nth(1).innerText(), '1,000개');
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 3);
    await page.getByText('학습 현황 접기', { exact: true }).click();
    await blocks.selectOption('');
    assert.equal(await page.locator('.overview-stats').count(), 0);
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 3);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});

test('closing cancels remaining batches; a failed summary can be retried', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?lazy');
    await page.getByText('학습 현황 보기', { exact: true }).click();
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 1);
    await page.getByText('학습 현황 접기', { exact: true }).click();
    await page.locator('.overview-heading select').selectOption('다른 블록');
    await page.evaluate(() => window.studyTest.release());
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 1);
    assert.equal(await page.locator('.overview-stats').count(), 0);
    await page.getByText('학습 현황 보기', { exact: true }).click();
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 2);
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests[1][0].subject), '다른 과목');
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => document.querySelector('.overview-stats strong:nth-child(2)')?.textContent === '1강의');
    await page.goto(base + '?lazy&progressError');
    await page.getByText('학습 현황 보기', { exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '학습 현황 조회 실패' }).waitFor();
    assert.equal(await page.locator('.overview-table tbody tr').count(), 10);
    await page.getByRole('button', { name: '다시 시도', exact: true }).click();
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 2);
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => window.studyTest.progressRequests.length === 3);
    await page.evaluate(() => window.studyTest.release());
    await page.waitForFunction(() => document.querySelectorAll('.overview-table tbody tr td:last-child > a').length === 10
      && document.querySelectorAll('[role="alert"]').length === 0);
  } finally { await browser.close(); }
});
