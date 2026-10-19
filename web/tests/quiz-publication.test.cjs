const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5197/tests/study-management.html';

test('production checks remain visible without study aggregates and refresh after a change', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?lazy');
    await page.getByRole('columnheader', { name: /① 퀴즈 답변 · 링크/ }).waitFor();
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

test('manual response is the primary production source even with a share link', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage();
    await page.goto(base + '?lazy&manual');
    const row = page.locator('.overview-table tbody tr').first();
    await row.getByText('✓ 직접 저장한 답변', { exact: true }).waitFor();
    assert.match(await row.innerText(), /75문항 · 링크보다 우선/);
    assert.equal(await row.locator('.quiz-production a').count(), 0);
    assert.equal(await row.getByRole('button', { name: /퀴즈 만들기/ }).count(), 0);
  } finally { await browser.close(); }
});

test('missing current link offers manual creation with latest prompt and attachments; members cannot create', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base + '?lazy');
    const rows = page.locator('.overview-table tbody tr');
    await rows.nth(1).getByRole('button', { name: '강의 1 퀴즈 만들기' }).waitFor();
    assert.equal(await rows.first().getByRole('button', { name: /퀴즈 만들기/ }).count(), 0);
    await page.evaluate(() => {
      document.documentElement.setAttribute('data-studyez-ai-extension', '99.0.0');
      window.bankDraftRequests = [];
      window.addEventListener('message', event => {
        if (event.data?.type !== 'STUDYEZ_OPEN_PREVIEW') return;
        window.bankDraftRequests.push(event.data.payload);
        window.postMessage({ source: 'studyez-ai-extension', type: 'STUDYEZ_OPEN_PREVIEW_RESULT', requestId: event.data.payload.requestId, ok: true }, location.origin);
      });
    });
    await rows.nth(1).getByRole('button', { name: '강의 1 퀴즈 만들기' }).click();
    await rows.nth(1).getByText(/프롬프트 1.99 준비 완료/).waitFor();
    const requests = await page.evaluate(() => window.bankDraftRequests);
    assert.equal(requests.length, 1);
    assert.equal(requests[0].autoSend, false);
    assert.equal(requests[0].lectureId, 'studyez:bank:1.99:약리학/1');
    assert.equal(requests[0].promptVersion, '1.99');
    assert.equal(requests[0].files[0].filename, '시험 강의.pdf');
    await page.goto(base + '?lazy&student');
    await page.getByText('75문항', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: /퀴즈 만들기/ }).count(), 0);
  } finally { await browser.close(); }
});
