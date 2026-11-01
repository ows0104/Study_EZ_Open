const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.STUDY_TEST_URL || 'http://127.0.0.1:5199';

test('private question creation, retry, editing and confirmed deletion', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    await page.goto(`${base}/tests/personal-questions.html`);
    await page.getByRole('button', { name: '＋ 문제 추가' }).click();
    const dialog = page.getByRole('dialog');
    assert.equal(await dialog.getByRole('button', { name: '내 학습에 추가' }).isDisabled(), true);
    await dialog.getByLabel('발문').fill('꼭 외울 질문\n두 번째 줄');
    await dialog.getByRole('textbox', { name: '정답', exact: true }).fill('나의 정답');
    await dialog.getByLabel('설명 (선택)').fill('교수님 설명');
    await dialog.getByLabel('중요도').selectOption('Essential');
    await page.evaluate(() => { window.personalTest.failAdd = true; });
    await dialog.getByRole('button', { name: '내 학습에 추가' }).click();
    await dialog.getByRole('alert').waitFor();
    assert.equal(await dialog.getByRole('textbox', { name: '정답', exact: true }).inputValue(), '나의 정답');
    await page.evaluate(() => { window.personalTest.failAdd = false; });
    await dialog.getByRole('button', { name: '내 학습에 추가' }).click();
    await page.getByText('내가 추가한 문제 1개').click();
    assert.equal(await page.getByText('★ Must-Know', { exact: true }).count(), 1);
    const calls = await page.evaluate(() => window.personalTest.calls.filter(c => c.path.endsWith('/personal-questions')));
    assert.equal(calls[0].body.clientId, calls[1].body.clientId, 'retry keeps the same idempotency key');
    assert.equal(calls[0].body.sourceQuestionId, undefined, 'starting screen has no current question');
    await page.getByRole('button', { name: '수정', exact: true }).click();
    await dialog.getByRole('heading', { name: '내가 추가한 문제 수정' }).waitFor();
    assert.equal(await dialog.getByText('제보 강조', { exact: true }).count(), 0);
    assert.equal(await dialog.getByRole('button', { name: '원본으로 되돌리기' }).count(), 0);
    await dialog.getByLabel('발문').fill('수정한 질문');
    await dialog.getByLabel('설명 (선택)').fill('수정한 설명');
    await dialog.getByRole('button', { name: '내 수정본 저장', exact: true }).click();
    await page.getByText('수정한 질문', { exact: false }).waitFor();
    await page.getByRole('button', { name: '삭제', exact: true }).click();
    await page.getByRole('button', { name: '취소', exact: true }).click();
    assert.equal(await page.getByText('내가 추가한 문제 1개').count(), 1);
    await page.getByRole('button', { name: '삭제', exact: true }).click();
    await page.getByRole('button', { name: '삭제 확인' }).click();
    await page.getByText('내가 추가한 문제 1개').waitFor({ state: 'detached' });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'mobile content fits');
  } finally { await browser.close(); }
});

test('solve screen exposes Essential and adding a card does not reveal the current answer', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage();
    await page.goto(`${base}/tests/personal-questions.html?solve`);
    assert.equal(await page.getByRole('combobox', { name: '내 문제 중요도' }).inputValue(), 'Essential');
    await page.getByText('문제 변경/추가/삭제', { exact: true }).click();
    await page.getByRole('button', { name: '＋ 문제 추가' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByText('현재 문제의 슬라이드를 자동 선택했습니다. 선택을 바꾸거나 삭제할 수 있습니다.').waitFor();
    await dialog.getByLabel('발문').fill('새 질문');
    await dialog.getByRole('textbox', { name: '정답', exact: true }).fill('새 답');
    await dialog.getByRole('button', { name: '내 학습에 추가' }).click();
    await page.getByText('내 문제를 추가했습니다.', { exact: true }).waitFor();
    assert.equal(await page.getByText('기존 문제', { exact: true }).count(), 1);
    const created = await page.evaluate(() => window.personalTest.calls.find(c => c.method === 'POST' && c.path.endsWith('/personal-questions')));
    assert.equal(created.body.sourceQuestionId, 'Q1');
    assert.deepEqual(created.body.slideAssetIds, ['slide-3']);
    assert.equal(await page.evaluate(() => window.personalTest.calls.some(c => c.path.endsWith('/reveal') || c.path.endsWith('/rate'))), false);
  } finally { await browser.close(); }
});

for (const removeAll of [false, true]) {
  test(`reference slides can be ${removeAll ? 'removed entirely' : 'replaced'} before adding`, async () => {
    const browser = await chromium.launch({ headless: true, channel: 'chrome' });
    try {
      const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
      await page.goto(`${base}/tests/personal-questions.html?solve`);
      await page.getByText('문제 변경/추가/삭제', { exact: true }).click();
      await page.getByRole('button', { name: '＋ 문제 추가' }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByRole('button', { name: 'PDF 3쪽 연결 삭제' }).click();
      await dialog.getByText('연결된 슬라이드 없음', { exact: true }).waitFor();
      await dialog.getByText('슬라이드 선택·변경', { exact: true }).click();
      await dialog.getByRole('checkbox', { name: 'PDF 7쪽', exact: true }).check();
      await dialog.getByRole('button', { name: 'PDF 7쪽 크게 보기' }).waitFor();
      if (removeAll) await dialog.getByRole('button', { name: '연결 모두 삭제' }).click();
      await dialog.getByLabel('발문').fill('슬라이드 선택 확인');
      await dialog.getByRole('textbox', { name: '정답', exact: true }).fill('답');
      await dialog.getByRole('button', { name: '내 학습에 추가' }).click();
      await dialog.waitFor({ state: 'detached' });
      const call = await page.evaluate(() => window.personalTest.calls.find(c => c.method === 'POST' && c.path.endsWith('/personal-questions')));
      assert.deepEqual(call.body.slideAssetIds, removeAll ? [] : ['slide-7']);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    } finally { await browser.close(); }
  });
}

test('creation sends format, retrieval direction and recall-first choice answers', async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    await page.goto(`${base}/tests/personal-questions.html`);
    await page.getByRole('button', { name: '＋ 문제 추가' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('문항 형식').selectOption('mcq');
    await dialog.getByLabel('회상 방식').selectOption('reverse');
    await dialog.getByLabel('객관식 학습 유형').selectOption('recall_first');
    await dialog.getByRole('textbox', { name: /^보기/ }).fill('정답 보기\n다른 보기');
    await dialog.getByRole('radio', { name: '1. 정답 보기', exact: true }).check();
    await dialog.getByLabel('발문').fill('역방향으로 떠올리세요.');
    await dialog.getByRole('textbox', { name: '정답', exact: true }).fill('정답 보기');
    await dialog.getByRole('button', { name: '내 학습에 추가' }).click();
    await dialog.waitFor({ state: 'detached' });
    const call = await page.evaluate(() => window.personalTest.calls.find(c => c.method === 'POST' && c.path.endsWith('/personal-questions')));
    assert.equal(call.body.format, 'mcq');
    assert.equal(call.body.retrieval_direction, 'reverse');
    assert.equal(call.body.mcq_mode, 'recall_first');
    assert.deepEqual(call.body.options, [{ id: '1', text: '정답 보기' }, { id: '2', text: '다른 보기' }]);
    assert.deepEqual(call.body.correct_option_ids, ['1']);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  } finally { await browser.close(); }
});
