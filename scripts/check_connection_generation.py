"""Revision-bound authoring checks; only owned fixtures and synthetic model calls."""
import os
from pathlib import Path
import subprocess
import sys
import uuid
from check_root_learning import ROOT, SERVER, PYTHON, ENV, run, server, ready


def pytest(*paths):
    temp=ROOT/'tmp'/('t'+uuid.uuid4().hex[:8]);temp.mkdir(parents=True)
    ENV.update(TMP=str(temp),TEMP=str(temp))
    run([PYTHON,'-m','pytest',*paths,'-q','--tb=short','--basetemp='+str(ROOT/'tmp'/('g'+uuid.uuid4().hex[:8]))])


def browser():
    logs=ROOT/'runs/_development'/ENV.get('STUDYEZ_TEST_CHANGE_ID','2026-11-03-connection-generation-pipeline');logs.mkdir(parents=True,exist_ok=True)
    ENV.update(VITE_LOCAL_TEST_TOKEN='local-test-admin',VITE_API_BASE_URL='',VITE_DEV_API='http://127.0.0.1:8028',
        ROOT_TEST_URL='http://127.0.0.1:5194/tests/root-learning.html',ROOT_TEST_OUTPUT=str(logs))
    bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
    if bundled.exists():ENV.setdefault('PLAYWRIGHT_MODULE',str(bundled))
    with (logs/'generation-api.log').open('w',encoding='utf-8') as a,(logs/'generation-web.log').open('w',encoding='utf-8') as w:
        api=subprocess.Popen([str(SERVER),'-m','tests.serve_generation_fixture'],cwd=ROOT/'server',env=ENV,stdout=a,stderr=subprocess.STDOUT)
        web=None
        try:
            ready(api,'http://127.0.0.1:8028/api/health')
            web=subprocess.Popen(['node','node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5194','--strictPort'],cwd=ROOT/'web',env=ENV,stdout=w,stderr=subprocess.STDOUT)
            ready(web,ENV['ROOT_TEST_URL'])
            run(['node','--test','tests/root-generation.test.cjs'],ROOT/'web')
        finally:
            for process in (web,api):
                if process and process.poll() is None:process.terminate();process.wait(timeout=10)


def main(name):
    if name in ('contract','contracts'):pytest('tests/contracts')
    elif name=='generation':pytest('tests/quizbank/test_connection_generate.py','tests/quizbank/test_generate.py','tests/quizbank/test_runtime.py')
    elif name=='runner':pytest('tests/runner/test_connection_generation.py','tests/runner/test_bank.py')
    elif name=='server':
        for pattern in ('root_generation','root_web_generation','root_one_click','route_contract','usage'):server(pattern)
    elif name=='ui':browser()
    elif name=='web':
        run([SERVER,'scripts/check_root_learning.py','--check','web-types'])
        ENV['VITE_LOCAL_TEST_TOKEN']='release-root-test-token'
        run([SERVER,'scripts/check_web_release.py'])
    elif name in ('web-types','web-build'):
        run([SERVER,'scripts/check_root_learning.py','--check',name])
    elif name=='root-regression':
        for check in ('root-state','root-api','root-planning','root-preservation','usage-actions','root-ui'):
            run([SERVER,'scripts/check_root_learning.py','--check',check])
    else:raise SystemExit('Unknown required check: '+name)


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--check':raise SystemExit('Usage: --check <name>')
    main(sys.argv[2])
