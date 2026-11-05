/** Pages publishes a web commit only after its tested API commit is live. */
import { setTimeout as sleep } from 'node:timers/promises';
import { pathToFileURL } from 'node:url';

export async function waitForApi({ sha, branch, api, timeoutMs = 900_000,
  fetchImpl = fetch, sleepImpl = sleep, now = Date.now, log = console.log }) {
  if (branch !== 'master' || !/^[a-f0-9]{40}$/.test(sha || '')) {
    throw new Error('Production build requires the exact master commit from Cloudflare Pages');
  }
  const base = new URL(api);
  if (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash) {
    throw new Error('API base must be public HTTPS without credentials or query');
  }
  const deadline = now() + timeoutMs;
  do {
    try {
      const response = await fetchImpl(new URL('/api/health', base), {
        cache: 'no-store', signal: AbortSignal.timeout(10_000),
      });
      const body = response.ok ? await response.json() : null;
      if (body?.status === 'ok' && body.environment === 'production' && body.revision === sha) {
        log(`Verified production API commit ${sha}`);
        return;
      }
    } catch { /* Temporary network failures are retried within the same deadline. */ }
    if (now() >= deadline) break;
    log('Waiting for this commit to pass GitHub checks and reach the API...');
    await sleepImpl(Math.min(15_000, Math.max(0, deadline - now())));
  } while (now() <= deadline);
  throw new Error('This commit is not live on the API; refusing to publish the web build');
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    await waitForApi({ sha: process.env.CF_PAGES_COMMIT_SHA,
      branch: process.env.CF_PAGES_BRANCH,
      api: process.env.VITE_API_BASE_URL,
      ...(process.argv.includes('--check') ? { timeoutMs: 0 } : {}),
    });
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
