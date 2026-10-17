const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

test('manual bank response validates completeness, retains failures and saves to the selected lecture', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage();
    let fail = true;
    let stored = '';
    const requests = [];
    await page.route('**/api/admin/lectures/**/bank/shared-source', route => route.fulfill({
      status: stored ? 200 : 404, contentType: 'application/json', body: JSON.stringify(stored ? { raw: stored } : { detail: '없음' }),
    }));
    await page.route('**/api/admin/lectures/**/bank-response', async route => {
      requests.push({ url: route.request().url(), method: route.request().method(), body: route.request().postDataJSON() });
      if (!fail) stored = route.request().postDataJSON().raw;
      await route.fulfill({ status: fail ? 409 : 200, contentType: 'application/json',
        body: JSON.stringify(fail ? { detail: '이전 문항을 검수 중입니다.' } : { jobId: 1 }) });
    });
    await page.goto(`${process.env.STUDY_TEST_URL || 'http://127.0.0.1:5199'}/tests/bank-response.html`);
    await page.getByText('답변 직접 붙여넣기', { exact: true }).click();
    const input = page.getByLabel('퀴즈뱅크 답변 본문');
    const save = page.getByRole('button', { name: '답변 저장·검수 요청' });
    await input.fill('일부 문항 '.repeat(50));
    assert.equal(await save.isEnabled(), true);
    await save.click();
    await page.getByRole('alert').waitFor();
    assert.match(await page.getByRole('alert').innerText(), /완료 표시/);
    assert.equal(requests.length, 0);
    await input.fill('STUDYEZ_BANK_COMPLETE');
    await save.click();
    assert.match(await page.getByRole('alert').innerText(), /200자/);
    assert.equal(requests.length, 0);
    const raw = '전체 문항과 해설 '.repeat(50) + '\nSTUDYEZ_BANK_COMPLETE';
    await input.fill(raw.replace('STUDYEZ_BANK_COMPLETE', '**STUDYEZ_BANK_COMPLETE**\n```'));
    await save.click();
    await page.getByRole('alert').waitFor();
    assert.ok((await input.inputValue()).endsWith('**STUDYEZ_BANK_COMPLETE**\n```'));
    fail = false;
    await save.click();
    await page.getByRole('status').waitFor();
    assert.equal(await input.inputValue(), raw);
    assert.equal(await page.locator('body').getAttribute('data-saved'), 'yes');
    assert.equal(requests.length, 2);
    assert.equal(requests[1].method, 'PUT');
    assert.ok(requests[1].url.endsWith('/api/admin/lectures/' + encodeURIComponent('약리학') + '/261016_03/bank-response'));
    assert.deepEqual(requests[1].body, { raw, source: 'manual' });
    const manual = '완료 표시가 없는 전체 답변 '.repeat(50);
    await input.fill(manual);
    await save.click();
    await page.getByRole('alert').waitFor();
    assert.equal(requests.length, 2);
    await page.getByRole('checkbox', { name: '답변 전체를 끝까지 붙여 넣었습니다' }).check();
    await save.click();
    await page.getByRole('status').waitFor();
    assert.equal(requests.length, 3);
    assert.deepEqual(requests[2].body, { raw: manual.trim() + '\nSTUDYEZ_BANK_COMPLETE', source: 'manual' });
    assert.equal(await input.inputValue(), stored);
    await page.reload();
    await page.getByText('답변 직접 붙여넣기', { exact: true }).click();
    await page.getByRole('status').waitFor();
    assert.equal(await input.inputValue(), stored);
    assert.equal(requests.length, 3, 'reopening only reads the saved response');
  } finally { await browser.close(); }
});

test('loading an old saved response never overwrites newly pasted text', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage();
    let finish;
    const pending = new Promise(resolve => { finish = resolve; });
    await page.route('**/api/admin/lectures/**/bank/shared-source', async route => {
      await pending;
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ raw: 'old saved text' }) });
    });
    await page.goto(`${process.env.STUDY_TEST_URL || 'http://127.0.0.1:5199'}/tests/bank-response.html`);
    await page.getByText('답변 직접 붙여넣기', { exact: true }).click();
    const input = page.getByLabel('퀴즈뱅크 답변 본문');
    await input.fill('new pasted text');
    finish();
    await page.getByText('저장된 답변을 불러오는 중…').waitFor({ state: 'hidden' });
    assert.equal(await input.inputValue(), 'new pasted text');
  } finally { await browser.close(); }
});
