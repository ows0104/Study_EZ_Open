const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

test('manual bank response validates completeness, retains failures and saves to the selected lecture', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage();
    let fail = true;
    const requests = [];
    await page.route('**/api/admin/lectures/**/bank-response', async route => {
      requests.push({ url: route.request().url(), method: route.request().method(), body: route.request().postDataJSON() });
      await route.fulfill({ status: fail ? 409 : 200, contentType: 'application/json',
        body: JSON.stringify(fail ? { detail: '이전 문항을 검수 중입니다.' } : { jobId: 1 }) });
    });
    await page.goto(`${process.env.STUDY_TEST_URL || 'http://127.0.0.1:5199'}/tests/bank-response.html`);
    await page.getByText('답변 직접 붙여넣기', { exact: true }).click();
    const input = page.getByLabel('퀴즈뱅크 답변 본문');
    const save = page.getByRole('button', { name: '답변 저장·검수 요청' });
    await input.fill('일부 문항 '.repeat(50));
    assert.equal(await save.isDisabled(), true);
    await input.fill('STUDYEZ_BANK_COMPLETE');
    assert.equal(await save.isDisabled(), true);
    const raw = '전체 문항과 해설 '.repeat(50) + '\nSTUDYEZ_BANK_COMPLETE';
    await input.fill(raw);
    await save.click();
    await page.getByRole('alert').waitFor();
    assert.equal(await input.inputValue(), raw);
    fail = false;
    await save.click();
    await page.getByRole('status').waitFor();
    assert.equal(await input.inputValue(), '');
    assert.equal(await page.locator('body').getAttribute('data-saved'), 'yes');
    assert.equal(requests.length, 2);
    assert.equal(requests[1].method, 'PUT');
    assert.ok(requests[1].url.endsWith('/api/admin/lectures/' + encodeURIComponent('약리학') + '/261016_03/bank-response'));
    assert.deepEqual(requests[1].body, { raw });
  } finally { await browser.close(); }
});
