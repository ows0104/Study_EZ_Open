"""Named root product checks. Every subcommand must succeed; owned fixtures only."""
from pathlib import Path
import os
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'server/.venv/Scripts/python.exe'
PYTHON = ROOT / '.venv/Scripts/python.exe'
ENV = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONPATH':str(ROOT)}


def run(command, cwd=ROOT):
    result = subprocess.run([str(x) for x in command], cwd=cwd, env=ENV)
    if result.returncode:
        raise SystemExit(result.returncode)


def server(pattern):
    run([SERVER, '-m', 'tests', pattern], ROOT / 'server')


def ready(process, url):
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError('Owned fixture exited before readiness')
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError('Owned fixture readiness timeout')


def browser():
    logs = ROOT / 'runs/_development' / ENV.get('STUDYEZ_TEST_CHANGE_ID','2026-11-02-root-learning-product')
    logs.mkdir(parents=True, exist_ok=True)
    ENV.update(VITE_LOCAL_TEST_TOKEN='local-test-admin', VITE_API_BASE_URL='', VITE_DEV_API='http://127.0.0.1:8027')
    ENV['ROOT_TEST_URL'] = 'http://127.0.0.1:5193/tests/root-learning.html'
    ENV['ROOT_TEST_OUTPUT'] = str(logs)
    bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
    if bundled.exists():
        ENV.setdefault('PLAYWRIGHT_MODULE', str(bundled))
    with (logs / 'fixture-api.log').open('w', encoding='utf-8') as api_log, (logs / 'fixture-web.log').open('w', encoding='utf-8') as web_log:
        api = subprocess.Popen([str(SERVER), '-m', 'tests.serve_root_fixture'], cwd=ROOT/'server', env=ENV, stdout=api_log, stderr=subprocess.STDOUT)
        web = None
        try:
            ready(api, 'http://127.0.0.1:8027/api/health')
            web = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5193', '--strictPort'],
                                   cwd=ROOT/'web', env=ENV, stdout=web_log, stderr=subprocess.STDOUT)
            ready(web, ENV['ROOT_TEST_URL'])
            run(['node', '--test', 'tests/root-learning.test.cjs'], ROOT/'web')
        finally:
            for process in (web, api):
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


def main(name):
    if name == 'root-contract':
        run([PYTHON, '-m', 'pytest', 'tests/contracts', '-q'])
    elif name in ('root-state', 'root-api', 'root-planning'):
        server(name.replace('-', '_'))
        if name == 'root-api':
            server('root_exposure')
            server('root_policy_api')
            server('route_contract')
        if name == 'root-planning':
            server('root_adaptive')
    elif name == 'root-preservation':
        for pattern in ('root_preservation', 'study_retention', 'bank_personal', 'bank_excluded'):
            server(pattern)
    elif name == 'usage-actions':
        for pattern in ('root_usage', 'usage'):
            server(pattern)
    elif name == 'root-ui':
        browser()
    elif name == 'web-types':
        run(['node', 'web/node_modules/typescript/bin/tsc', '-b', 'web/tsconfig.json', '--noEmit'])
    elif name == 'web-build':
        run(['npm.cmd', '--prefix', 'web', 'run', 'build'])
    else:
        raise SystemExit('Unknown required check: ' + name)


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--check':
        raise SystemExit('Usage: check_root_learning.py --check <name>')
    main(sys.argv[2])
