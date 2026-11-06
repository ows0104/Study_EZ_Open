const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PROMPT_TEST_URL || 'http://127.0.0.1:5199/tests/shared-preview-prompt.html';

test('admin saves, reloads, resets and sends latest shared prompt; personal remains separate', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage();
  try {
    await page.goto(base);
    await page.getByRole('button', { name: '모든 강의의 기본 예습 프롬프트 수정 (관리자)' }).click();
    const text = page.getByRole('textbox', { name: '기본 예습 프롬프트', exact: true });
    await text.waitFor();
    const original = await text.inputValue();
    const custom = '{파일명}\n{강의} 핵심만 설명해줘.';
    await text.fill(custom);
    await page.getByRole('button', { name: '저장', exact: true }).click();
    await page.getByRole('status').filter({ hasText: '저장했습니다.' }).waitFor();
    await page.reload();
    await page.getByRole('button', { name: '모든 강의의 기본 예습 프롬프트 수정 (관리자)' }).click();
    await page.waitForFunction(() => document.querySelector('textarea')?.value.includes('핵심만'));
    assert.equal(await text.inputValue(), custom);
    // Another administrator changed the server after this editor loaded.
    await page.evaluate(() => { window.promptTest.stored = '{파일명}\n최신 {강의}'; });
    await page.getByRole('button', { name: '기본 링크 생성 · 첨부 후 자동 전송 (관리자)' }).click();
    await page.waitForFunction(() => window.promptTest.sent.length === 1);
    assert.equal(await page.evaluate(() => window.promptTest.sent[0].prompt), '작년 필기.pdf\n최신 예시 강의');
    await page.getByRole('button', { name: '개인 대화 만들기' }).click();
    await page.waitForFunction(() => window.promptTest.sent.length === 2);
    assert.equal(await page.evaluate(() => window.promptTest.sent[1].prompt), '내 개인 프롬프트');
    // A failed save retains the draft and the previous stored value.
    await page.evaluate(() => { window.promptTest.fail = true; });
    await text.fill('저장 실패 초안');
    await page.getByRole('button', { name: '저장', exact: true }).click();
    await page.getByText('저장 서버 오류', { exact: true }).waitFor();
    assert.equal(await text.inputValue(), '저장 실패 초안');
    await page.evaluate(() => { window.promptTest.fail = false; });
    await page.getByRole('button', { name: '기본값으로', exact: true }).click();
    await page.getByRole('status').filter({ hasText: '저장했습니다.' }).waitFor();
    assert.equal(await text.inputValue(), original);
    assert.equal(await page.evaluate(() => window.promptTest.stored), '');
  } finally { await browser.close(); }
});

test('admin edits without extension on mobile; students have no shared editor or API read', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  try {
    await page.goto(base + '?noExtension');
    await page.getByRole('button', { name: '모든 강의의 기본 예습 프롬프트 수정 (관리자)' }).click();
    await page.getByRole('textbox', { name: '기본 예습 프롬프트', exact: true }).fill('모바일 수정');
    await page.getByRole('button', { name: '저장', exact: true }).click();
    await page.getByRole('status').filter({ hasText: '저장했습니다.' }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.goto(base + '?student');
    await page.getByRole('button', { name: '내 예습 프롬프트 고치기' }).waitFor();
    assert.equal(await page.getByRole('button', { name: /모든 강의의 기본/ }).count(), 0);
    assert.equal(await page.evaluate(() => window.promptTest.requests.some(r => r.includes('/api/admin/preview-prompt'))), false);
  } finally { await browser.close(); }
});
