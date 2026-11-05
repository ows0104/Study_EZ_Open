import { test } from 'node:test';
import assert from 'node:assert/strict';
import { waitForApi } from '../scripts/wait-for-api.mjs';

const sha = 'a'.repeat(40);
const options = { sha, branch: 'master', api: 'https://example.invalid',
  timeoutMs: 0, log() {}, fetchImpl: async () => ({ ok: true,
    json: async () => ({ status: 'ok', environment: 'production', revision: sha }) }) };

test('only the matching live production commit opens the gate', async () => {
  await waitForApi(options);
  for (const body of [{ status: 'ok', environment: 'production', revision: 'b'.repeat(40) },
    { status: 'ok', environment: 'local-test', revision: sha }, { status: 'failed', revision: sha }]) {
    await assert.rejects(waitForApi({ ...options,
      fetchImpl: async () => ({ ok: true, json: async () => body }) }), /refusing/);
  }
});
test('fails closed on branch, SHA, HTTP, network and URL errors', async () => {
  for (const override of [{ branch: 'feature' }, { sha: '' }, { api: 'http://example.invalid' },
    { api: 'https://secret@example.invalid' }, { fetchImpl: async () => ({ ok: false }) },
    { fetchImpl: async () => { throw new Error('offline'); } }]) {
    await assert.rejects(waitForApi({ ...options, ...override }));
  }
});
test('retries a delayed API within the bounded deadline', async () => {
  let elapsed = 0, calls = 0;
  await waitForApi({ ...options, timeoutMs: 20_000, now: () => elapsed,
    sleepImpl: async ms => { elapsed += ms; }, fetchImpl: async () => ({ ok: true,
      json: async () => ({ status: 'ok', environment: 'production',
        revision: ++calls === 2 ? sha : '' }) }) });
  assert.equal(calls, 2);
});
