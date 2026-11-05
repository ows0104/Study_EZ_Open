const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.PROFESSOR_TEST_URL || 'http://127.0.0.1:5198/tests/professor-preview.html';
const fs = require('node:fs');
const path = require('node:path');

test('calendar tags, fallback notes, provenance, keyboard and mobile', async () => {
  const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.goto(base, { waitUntil: 'domcontentloaded' });
    const changed = page.getByRole('button', { name: /교수 변경 강의/ });
    await changed.waitFor();
    assert.equal(await changed.locator('.professor-badge').innerText(), '교수 변경');
    const fresh = page.getByRole('button', { name: /신규 교수 강의/ });
    assert.match(await fresh.innerText(), /교수 변경.*신규 교수/s);
    assert.match(await fresh.getAttribute('title'), /작년 자료 사용/);
    assert.match(await fresh.getAttribute('title'), /2024년/);
    const unknown = page.getByRole('button', { name: /담당 확인 강의/ });
    assert.equal(await unknown.locator('.professor-badge').innerText(), '확인 필요');
    assert.equal(await page.getByRole('button', { name: /기존 자료 강의/ }).locator('.professor-badge').count(), 0);
    const screenshotDir = process.env.PROFESSOR_SCREENSHOTS;
    if (screenshotDir) {
      fs.mkdirSync(screenshotDir, { recursive: true });
      await page.screenshot({ path: path.join(screenshotDir, 'calendar-wide.png'), fullPage: true, animations: 'disabled' });
    }
    await changed.focus();
    await page.keyboard.press('Enter');
    const panel = page.locator('.event-panel');
    await panel.getByRole('heading', { name: '교수 변경 강의', exact: true }).waitFor();
    await panel.getByText('2023년 예습 필기', { exact: true }).waitFor();
    assert.match(await panel.locator('.professor-info').innerText(), /예습 자료가 바뀌었습니다/);
    assert.match(await page.evaluate(() => window.professorPreviewTest.prompt()), /^\[231101_01\].*김범준/s);
    if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, 'panel-wide.png'), fullPage: true, animations: 'disabled' });
    await page.keyboard.press('Escape');
    await fresh.click();
    await panel.getByText('2025년 예습 필기', { exact: true }).waitFor();
    assert.match(await panel.locator('.professor-info').innerText(), /작년 자료 사용/);
    assert.match(await panel.locator('.professor-info').innerText(), /신규 교수.*보유 자료/s);
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: '월', exact: true }).click();
    await page.locator('.month-calendar').waitFor();
    assert.equal(await page.getByRole('button', { name: /신규 교수 강의/ }).locator('.professor-badge').innerText(), '신규 교수');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: /신규 교수 강의/ }).click();
    await panel.getByText('2025년 예습 필기', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    if (screenshotDir) await page.screenshot({ path: path.join(screenshotDir, 'panel-mobile.png'), fullPage: true, animations: 'disabled' });
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
});
