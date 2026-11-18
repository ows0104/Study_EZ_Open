"""Named root product checks. Every subcommand must succeed; owned fixtures only."""
from pathlib import Path
import os
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
# worktree에는 server/.venv가 없을 수 있다. 그때는 메인 체크아웃의 venv를 STUDYEZ_SERVER_PYTHON으로 준다(PYTHONPATH가 이 ROOT라 계약은 이쪽 것).
SERVER = Path(os.environ.get('STUDYEZ_SERVER_PYTHON') or ROOT / 'server/.venv/Scripts/python.exe')
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


def browser(fixture='tests.serve_main_quiz_ui_fixture', api_port=8027, web_port=5193, page='root-learning', url_env='ROOT_TEST_URL'):
    logs = ROOT / 'runs/_development' / ENV.get('STUDYEZ_TEST_CHANGE_ID','2026-11-02-root-learning-product')
    logs.mkdir(parents=True, exist_ok=True)
    ENV.update(VITE_LOCAL_TEST_TOKEN='local-test-admin', VITE_API_BASE_URL='', VITE_DEV_API=f'http://127.0.0.1:{api_port}',
               MAIN_QUIZ_UI_PORT=str(api_port), MAIN_QUIZ_BATCH_PORT=str(api_port))
    ENV[url_env] = f'http://127.0.0.1:{web_port}/tests/{page}.html'
    ENV['ROOT_TEST_OUTPUT'] = str(logs)
    bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
    if bundled.exists():
        ENV.setdefault('PLAYWRIGHT_MODULE', str(bundled))
    with (logs / 'fixture-api.log').open('w', encoding='utf-8') as api_log, (logs / 'fixture-web.log').open('w', encoding='utf-8') as web_log:
        api = subprocess.Popen([str(SERVER), '-m', fixture], cwd=ROOT/'server', env=ENV, stdout=api_log, stderr=subprocess.STDOUT)
        web = None
        try:
            ready(api, f'http://127.0.0.1:{api_port}/api/health')
            web = subprocess.Popen(['node', 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', str(web_port), '--strictPort'],
                                   cwd=ROOT/'web', env=ENV, stdout=web_log, stderr=subprocess.STDOUT)
            ready(web, ENV[url_env])
            run(['node', '--test', f'tests/{page}.test.cjs'], ROOT/'web')
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
    elif name == 'root-batch':
        # Main-Quiz 모아풀기(2026-11-18): 합성 두 강의를 섞어 푼다.
        browser('tests.serve_main_quiz_batch_fixture', 8029, 5195, 'root-batch', 'ROOT_BATCH_URL')
    elif name == 'jokbo-mix':
        # 족보 모아풀기(2026-11-18-jokbo-mix): 합성 족보 세 칸을 고르게 배분해 푼다.
        browser('tests.serve_jokbo_mix_fixture', 8033, 5199, 'jokbo-mix', 'JOKBO_MIX_URL')
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
