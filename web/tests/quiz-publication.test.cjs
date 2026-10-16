const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5197/tests/study-management.html';

test('production checks remain visible without study aggregates and refresh after a change', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?lazy');
    await page.getByRole('columnheader', { name: /① 완성 퀴즈 링크/ }).waitFor();
    const row = page.locator('.overview-table tbody tr').first();
    await row.getByText('75문항', { exact: true }).waitFor();
    assert.match(await row.innerText(), /새 응답 미반영/);
    assert.match(await row.innerText(), /필수 검수/);
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 0);
    await page.evaluate(() => { window.setPublicationReady(); window.dispatchEvent(new Event('focus')); });
    await page.waitForFunction(() => document.querySelectorAll('.quiz-production.is-complete').length === 2);
    assert.equal(await row.getByText('새 응답 미반영', { exact: true }).count(), 0);
    assert.equal(await row.locator('.quiz-production.is-complete').count(), 2);
    await page.screenshot({ path: '../work/quiz-publication-20261017/overview.png', fullPage: true });
  } finally { await browser.close(); }
});
