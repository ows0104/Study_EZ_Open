const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../../bridge/chatgpt-bridge.js'), 'utf8');
const context = vm.createContext({ setTimeout, console });
vm.runInContext(source.replace('void initialize();', ''), context);

for (const mode of ['personal', 'shared', 'bank', 'review']) {
  test(`${mode}: manual input never submits, including requests without a flag`, async () => {
    for (const autoSend of [false, undefined]) {
      await context.finishInput({mode, autoSend}, {}, () => {}, async () => assert.fail('manual submitted'));
    }
    let calls = 0;
    await context.finishInput({mode, autoSend: true}, {}, () => {}, async () => { calls++; });
    assert.equal(calls, 1);
    assert.notEqual(context.consentScopeFor({provider: 'chatgpt', mode, autoSend: false}),
                    context.consentScopeFor({provider: 'chatgpt', mode, autoSend: true}));
  });
}

function scenario(options = {}) {
  let time = 0;
  const clicks = [];
  const editor = { value: 'Explain the lecture.' };
  const button = {
    disabled: false,
    getAttribute: () => null,
    click() { clicks.push(time); if (!options.unconfirmed) editor.value = ''; },
  };
  const payload = { provider: 'chatgpt', prompt: editor.value, files: [{ filename: 'lecture.pdf', size: options.fileSize || 0 }] };
  const dependencies = {
    now: () => time,
    sleep: async (ms) => { time += ms; options.tick?.({ time, editor, button }); },
    findEditor: () => options.missingEditor ? null : editor,
    composerRoot: () => ({}),
    sendButton: () => options.missingButton ? null : button,
    attachmentStatus: () => options.attachments?.(time) || { ready: true, failed: false },
  };
  return {
    clicks,
    run: () => context.autoSend(payload, {}, () => options.active?.(time), dependencies),
  };
}

test('waits for all attachments, then sends exactly once', async () => {
  const s = scenario({ attachments: time => ({ ready: time >= 4000 }) });
  await s.run();
  assert.deepEqual(s.clicks, [5500]);
});

test('reattached filenames accept provider numeric suffixes but reject different files', () => {
  const name = '[261012_01] 지혈과 혈전증 약리(조정현)_강태우v2.pdf';
  for (const label of [name, name.replace('.pdf', '(1).pdf'), name.replace('.pdf', ' (12).pdf')]) {
    assert.equal(context.attachmentFilenameVisible(label, name), true, label);
  }
  for (const label of [name.replace('v2', 'v3'), name + '.backup', 'other' + name]) {
    assert.equal(context.attachmentFilenameVisible(label, name), false, label);
  }
});

test('large lecture upload can finish after two minutes and submits once', async () => {
  const s = scenario({fileSize: 90 * 1024 * 1024, attachments: time => ({ready: time >= 180000})});
  await s.run();
  assert.deepEqual(s.clicks, [181500]);
});

test('large missing attachment still has a bounded timeout without submitting', async () => {
  const s = scenario({fileSize: 90 * 1024 * 1024, attachments: () => ({ready: false})});
  await assert.rejects(s.run(), /10분/);
  assert.equal(s.clicks.length, 0);
});

test('readiness must stay stable after upload state changes', async () => {
  const s = scenario({ attachments: time => ({ ready: time < 1000 || time >= 3000 }) });
  await s.run();
  assert.deepEqual(s.clicks, [4500]);
});

test('disabled send button prevents submission even when files are present', async () => {
  const s = scenario({ tick: ({ time, button }) => { button.disabled = time < 3000; } });
  await s.run();
  assert.deepEqual(s.clicks, [4500]);
});

test('aria-disabled also prevents submission', async () => {
  const s = scenario({ tick: ({ time, button }) => { button.getAttribute = () => time < 3000 ? 'true' : null; } });
  await s.run();
  assert.deepEqual(s.clicks, [4500]);
});

test('upload failure stops without clicking', async () => {
  const s = scenario({ attachments: () => ({ failed: true }) });
  await assert.rejects(s.run(), /업로드에 실패/);
  assert.equal(s.clicks.length, 0);
});

for (const [name, config] of [
  ['missing attachment', { attachments: () => ({ ready: false }) }],
  ['missing send button', { missingButton: true }],
]) test(`${name} times out without clicking`, async () => {
  const s = scenario(config);
  await assert.rejects(s.run(), /2분/);
  assert.equal(s.clicks.length, 0);
});

for (const value of ['', 'User edited the prompt.']) {
  test(`manual send or edit stops automatic send (${JSON.stringify(value)})`, async () => {
    const s = scenario({ tick: ({ editor }) => { editor.value = value; } });
    await assert.rejects(s.run(), /입력 내용이 바뀌/);
    assert.equal(s.clicks.length, 0);
  });
}

test('cancel or navigation stops while waiting for uploads', async () => {
  const s = scenario({ active: time => { if (time >= 500) throw new Error('cancelled'); } });
  await assert.rejects(s.run(), /cancelled/);
  assert.equal(s.clicks.length, 0);
});

test('uncertain submission never retries the click', async () => {
  const s = scenario({ unconfirmed: true });
  await assert.rejects(s.run(), /자동으로 다시 보내지/);
  assert.equal(s.clicks.length, 1);
});

test('missing editor cannot trigger send', async () => {
  const s = scenario({ missingEditor: true });
  await assert.rejects(s.run(), /입력 내용이 바뀌/);
  assert.equal(s.clicks.length, 0);
});
