/* Start the isolated fixture and browser in the same permission/network context. */
const { spawn } = require('node:child_process');
const http = require('node:http');
const path = require('node:path');
const web = path.resolve(__dirname, '..');
const port = process.env.PROFESSOR_TEST_PORT || '5199';
const env = { ...process.env,
  PROFESSOR_TEST_URL: `http://127.0.0.1:${port}/tests/professor-preview.html`,
  CALENDAR_TEST_URL: `http://127.0.0.1:${port}/tests/calendar-loading.html` };
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', port, '--strictPort'],
  { cwd: web, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
let output = '';
server.stdout.on('data', data => { output += data; });
server.stderr.on('data', data => { output += data; });
async function ready() {
  for (let i = 0; i < 100; i++) {
    if (server.exitCode !== null) throw new Error(output);
    const ok = await new Promise(resolve => {
      const req = http.get(env.PROFESSOR_TEST_URL, res => { res.resume(); resolve(res.statusCode === 200); });
      req.on('error', () => resolve(false));
      req.setTimeout(300, () => { req.destroy(); resolve(false); });
    });
    if (ok) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('Local fixture did not become ready: ' + output);
}
(async () => {
  try {
    await ready();
    const files = process.argv.includes('--all') ? ['professor-preview.test.cjs', 'calendar-loading.test.cjs'] : ['professor-preview.test.cjs'];
    const code = await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, ['--test', ...files.map(f => path.join(__dirname, f))],
        { env, windowsHide: true, stdio: 'inherit' });
      child.on('error', reject);
      child.on('exit', code => resolve(code ?? 1));
    });
    process.exitCode = code;
  } catch (e) { console.error(e); process.exitCode = 1; }
  finally { server.kill(); }
})();
