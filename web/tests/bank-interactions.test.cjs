const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5199';

for (const fixture of ['matching', 'sequence', 'prepared-answer', 'bank-advance', 'bank-advance?batch', 'common-editor',
  'bank-buffer', 'bank-buffer?batch', 'bank-buffer?revealFailure', 'bank-buffer-refill', 'bank-buffer-staged']) {
  test(`study interaction: ${fixture}`, async () => {
    const browser = await chromium.launch({ headless: true, channel: 'chrome' });
    try {
      const page = await browser.newPage();
      const [name, query] = fixture.split('?');
      await page.goto(`${base}/tests/${name}.html${query ? '?' + query : ''}`);
      await page.waitForFunction(() => /ALL PASSED|FAIL/.test(document.getElementById('results')?.textContent || ''), { timeout: 30000 });
      const result = await page.locator('#results').innerText();
      assert.match(result, /ALL PASSED/, result);
      assert.doesNotMatch(result, /FAIL/);
    } finally { await browser.close(); }
  });
}
