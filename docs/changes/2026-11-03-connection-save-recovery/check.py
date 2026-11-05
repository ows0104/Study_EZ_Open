"""Run all subchecks, with an owned local Vite server for browser regression."""
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

root = Path(__file__).resolve().parents[3]
env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}


def run(command, cwd=root):
    result = subprocess.run(command, cwd=cwd, env=env)
    if result.returncode:
        raise SystemExit(result.returncode)


if sys.argv[1] == 'server':
    run([str(root / 'server/.venv/Scripts/python.exe'), str(root / 'docs/changes/2026-11-03-connection-learning-product/check.py')])
elif sys.argv[1] == 'recovery-ui':
    run(['node', '--test', 'tests/connection-recovery.test.cjs'], root / 'web')
    env['VITE_LOCAL_TEST_TOKEN'] = 'local-test-admin'
    env['VITE_API_BASE_URL'] = ''
    env['CONNECTION_TEST_URL'] = 'http://127.0.0.1:5191/tests/connection-learning.html'
    bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
    if bundled.exists():
        env.setdefault('PLAYWRIGHT_MODULE', str(bundled))
    with open(Path(__file__).with_name('browser-server.log'), 'w', encoding='utf-8') as output:
        server = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5191', '--strictPort'],
                                  cwd=root / 'web', env=env, stdout=output, stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError('Owned Vite server exited before readiness')
                try:
                    with urlopen(env['CONNECTION_TEST_URL'], timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError('Vite readiness timeout')
            run(['node', '--test', 'tests/connection-learning.test.cjs'], root / 'web')
        finally:
            server.terminate()
            server.wait(timeout=10)
else:
    raise SystemExit('Expected server or recovery-ui')
