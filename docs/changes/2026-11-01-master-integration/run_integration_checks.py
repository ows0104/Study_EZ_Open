"""Run extension, web rendering, and isolated browser fixtures; never contact the live API."""
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
BASE = 'http://127.0.0.1:5199'
env = os.environ.copy()
env.update(PLAYWRIGHT_MODULE=str(ROOT / 'tmp/browser-runtime/node_modules/playwright'),
           STUDY_TEST_OUTPUT=str(ROOT / 'tmp/master-browser-output'),
           STUDY_TEST_URL=BASE, CATALOG_TEST_URL=BASE + '/tests/bank-catalog.html',
           CALENDAR_TEST_URL=BASE + '/tests/calendar-loading.html',
           PROMPT_TEST_URL=BASE + '/tests/shared-preview-prompt.html')
flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def run(paths):
    print('Running:', ', '.join(p.name for p in paths), flush=True)
    return subprocess.call(['node', '--test', '--test-concurrency=1', *map(str, paths)],
                           cwd=ROOT, env=env, creationflags=flags,
                           stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=subprocess.STDOUT)


tests = sorted((ROOT / 'web/tests').glob('*.test.cjs'))
static = [p for p in tests if 'playwright' not in p.read_text(encoding='utf-8')]
browser = [p for p in tests if p not in static]
bridge = sorted((ROOT / 'tests/bridge').glob('*.cjs'))
code = run(static + bridge)
if code:
    raise SystemExit(code)
log_path = ROOT / 'tmp/master-integration-vite.log'
with log_path.open('w', encoding='utf-8') as log:
    vite = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1',
                             '--port', '5199', '--strictPort'], cwd=ROOT / 'web',
                            stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
    try:
        deadline = time.monotonic() + 30
        while True:
            if vite.poll() is not None:
                raise RuntimeError('Fixture server exited; see tmp/master-integration-vite.log')
            try:
                with urllib.request.urlopen(BASE + '/tests/matching.html', timeout=1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        management = {'quiz-publication.test.cjs', 'study-loading.test.cjs', 'study-management.test.cjs'}
        code = run([p for p in browser if p.name not in management])
        if not code:
            env['STUDY_TEST_URL'] = BASE + '/tests/study-management.html'
            code = run([p for p in browser if p.name in management])
    finally:
        vite.terminate()
        vite.wait(timeout=10)
raise SystemExit(code)
