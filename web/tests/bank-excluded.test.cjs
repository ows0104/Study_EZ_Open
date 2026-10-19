const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const path = require('node:path');
const fs = require('node:fs');
test('Excluded: reveal, personal restore, delete, return and mobile layout', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto((process.env.CATALOG_TEST_URL || 'http://127.0.0.1:5218/tests/bank-catalog.html') + '?excluded');
    await page.getByRole('button', { name: 'Excluded · 1문항', exact: true }).click();
    const card = page.locator('.catalog-card');
    await card.getByText('Excluded', { exact: true }).waitFor();
    assert.equal(await card.count(), 1);
    assert.equal(await card.getByText('예시 정답', { exact: true }).count(), 0);
    await card.getByRole('button', { name: '정답·해설 보기 ↓' }).click();
    await card.getByText('예시 정답', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    const screenshot = path.resolve(__dirname, '../../work/excluded-20261018/mobile.png');
    fs.mkdirSync(path.dirname(screenshot), { recursive: true });
    await page.screenshot({ path: screenshot, fullPage: true });
    await card.getByRole('button', { name: '내 학습에 복원', exact: true }).click();
    await page.getByRole('combobox', { name: '보기', exact: true }).selectOption('restored');
    await card.getByText('내 학습에 복원됨', { exact: true }).waitFor();
    await card.getByRole('button', { name: '내 목록에서 삭제', exact: true }).click();
    await page.getByRole('combobox', { name: '보기', exact: true }).selectOption('deleted');
    await card.getByText('내 목록에서 삭제됨', { exact: true }).waitFor();
    await card.getByRole('button', { name: 'Excluded로 돌리기', exact: true }).click();
    await page.getByRole('combobox', { name: '보기', exact: true }).selectOption('excluded');
    await card.getByText('Excluded', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    assert.equal((await page.evaluate(() => window.catalogTest.requests)).filter(r => r.method === 'PUT').length, 3);
  } finally { await browser.close(); }
});
