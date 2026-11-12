const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5197/tests/study-management.html';

// 강의 목록은 시간표만으로 행·제목·▶를 바로 그린다(2026-11-12). 숫자 칸만 Main-Quiz 요약(/api/root-learning)을
// 기다린다 — 운영에서 6.5–8.8 s 걸리는 요청이다. 목록은 study-progress로 다시 채점하지 않는다.
const rows = page => page.locator('.list-table .list-row:not(.is-head)');
const cards = page => page.locator('.list-stats b').nth(2).innerText();
const pickBlock = async (page, name) => {
  await page.locator('.block-picker-button').click();
  await page.getByRole('option', { name: new RegExp(`^${name}`) }).click();
};
const statsAre = (page, text) => page.waitForFunction(value => document.querySelectorAll('.list-stats b')[2]?.textContent === value, text);

test('rows and ▶ show before the Main-Quiz summary; numbers fill in when it arrives', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '?lazy');
    await page.getByRole('heading', { name: '강의 목록', exact: true }).waitFor();
    await page.waitForFunction(() => window.studyTest.rootRequests.length === 1);
    // The summary is still held: every row is listed, open and playable; only the number cells wait.
    assert.equal(await rows(page).count(), 10);
    assert.equal(await rows(page).first().locator('.list-title strong').innerText(), '강의 0');
    assert.equal(await page.locator('.list-table .list-row.is-closed').count(), 0);
    assert.equal(await page.getByRole('button', { name: '강의 0 복습 퀴즈' }).isEnabled(), true);
    assert.equal(await page.locator('.list-table .is-loading').count(), 10 * 7);
    assert.equal(await cards(page), '…장');
    assert.equal(await page.locator('.list-stats').getAttribute('aria-busy'), 'true');
    await page.evaluate(() => window.studyTest.releaseRoot());
    await statsAre(page, '1,000장');
    assert.equal(await page.locator('.list-table .is-loading').count(), 0);
    assert.equal(await page.locator('.stage-legend .stage-text-retained').innerText(), '250');
    assert.equal(await rows(page).first().locator('.rate-text').innerText(), '50%');
    // Another block reads the same (cached) summary — no new request.
    await pickBlock(page, '다른 블록');
    assert.equal(await rows(page).count(), 1);
    await statsAre(page, '100장');
    assert.equal(await page.evaluate(() => window.studyTest.rootRequests.length), 1);
    // The list no longer re-scores lectures through study-progress.
    assert.equal(await page.evaluate(() => window.studyTest.progressRequests.length), 0);
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});

test('a failed summary leaves dashes, not an endless loading state', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?lazy&rootError');
    await page.waitForFunction(() => window.studyTest.rootRequests.length === 1);
    await page.evaluate(() => window.studyTest.releaseRoot());
    await page.waitForFunction(() => document.querySelectorAll('.list-table .is-loading').length === 0);
    assert.equal(await rows(page).count(), 10);
    assert.equal(await rows(page).first().locator('.rate-text').innerText(), '—');
    assert.equal(await page.getByRole('button', { name: '강의 0 복습 퀴즈' }).isEnabled(), true);
  } finally { await browser.close(); }
});
