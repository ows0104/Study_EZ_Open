"""Owned local/synthetic checks and read-only evidence verification for one pilot."""
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PY=ROOT/'.venv/Scripts/python.exe';SERVER=ROOT/'server/.venv/Scripts/python.exe'
LOGS=ROOT/'runs/_development/2026-11-06-cli-parallel-main-quiz'
HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)


def env():
    value=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONPATH=str(ROOT))
    for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):value.pop(key,None)
    return value


def run(args,cwd=ROOT,extra=None):
    subprocess.run([str(x)for x in args],cwd=cwd,env=extra or env(),check=True,creationflags=HIDDEN,
        stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr)


def tests(paths):
    (ROOT/'tmp').mkdir(exist_ok=True)
    run([PY,'-m','pytest',*paths,'-q','--tb=short','--basetemp','tmp/pc'+str(time.time_ns())[-8:]])


def browser():
    with socket.socket()as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    url=f'http://127.0.0.1:{port}/tests/main-quiz-generation.html'
    childenv=env();childenv.update(VITE_LOCAL_TEST_TOKEN='synthetic-browser-only',VITE_API_BASE_URL='',
        VITE_SUPABASE_URL='',VITE_SUPABASE_ANON_KEY='',GENERATION_BUTTON_URL=url,
        PLAYWRIGHT_MODULE=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
        GENERATION_BUTTON_SCREENSHOT=str(LOGS/'button-mobile.png'))
    LOGS.mkdir(parents=True,exist_ok=True)
    with (LOGS/'browser-vite.log').open('w',encoding='utf-8')as log:
        process=subprocess.Popen(['node','node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(port),'--strictPort'],cwd=ROOT/'web',env=childenv,stdout=log,stderr=subprocess.STDOUT,creationflags=HIDDEN)
        try:
            import urllib.request
            for _ in range(80):
                if process.poll()is not None:raise RuntimeError('Owned Vite startup failed')
                try:
                    with urllib.request.urlopen(url,timeout=1)as r:
                        if r.status==200:break
                except OSError:time.sleep(.1)
            else:raise RuntimeError('Owned Vite startup timeout')
            run(['node','--test','tests/main-quiz-generation-browser.test.cjs'],ROOT/'web',childenv)
        finally:
            if process.poll()is None:process.terminate();process.wait(timeout=15)


def pilot():
    sys.path.insert(0,str(ROOT))
    from runner.root_native_json import validate_all
    from studyez_contracts.roots.automation import validate_result
    out=ROOT/'runs/_parallel-pilot/261104_02'
    read=lambda name:json.loads((out/name).read_text(encoding='utf-8'))
    packet=read('packet.json');result=read('result.json');summary=read('summary.json')
    validate_result(result,packet);validate_all(out,result)
    from studyez_contracts.roots import document_hash
    bundle=read('.runtime-used/manifest.json')
    assert bundle['runtimeHash']==result['manifest']['runtimeHash']
    assert document_hash({'input':bundle['inputHash'],'model':bundle['model'],'code':bundle['code']})==bundle['runtimeHash']
    assert all(hashlib.sha256((out/'.runtime-used'/name).read_bytes()).hexdigest()==digest for name,digest in bundle['code'].items())
    assert summary['completed'] and summary['productionWrites']==0
    assert hashlib.sha256(Path(packet['sources'][0]['localPath']).read_bytes()).hexdigest()==packet['sources'][0]['sha256']
    bank=result['document']['bank_snapshot'];images=[q for q in bank['questions']if q.get('stimuli')]
    assert images and result['document']['tasks']
    rows=result['manifest']['parallelAuthoring']['branches']
    assert max(r['startedAt']for r in rows.values())<min(r['finishedAt']for r in rows.values())
    print(json.dumps({'verified':True,'questions':len(bank['questions']),'visualQuestions':len(images),
        'tasks':len(result['document']['tasks']),'repairs':result['manifest']['repairRounds'],'productionWrites':0}))


def main(mode):
    if mode=='parallel-regression':
        tests(['tests/quizbank/test_connection_parallel.py','tests/quizbank/test_connection_figures.py'])
        run(['node','--test','web/tests/main-quiz-generation-button.test.cjs','web/tests/main-quiz-web-author.test.cjs','web/tests/main-quiz-render.test.cjs'])
        browser()
        for name in ('root_parallel_generation','root_web_generation','root_pipeline_v2'):
            run([SERVER,'-m','tests',name],ROOT/'server')
        # Own API/storage/worker subprocesses, synthetic models, real study/image UI,
        # then the repository's normal typecheck and production build.
        run([PY,'scripts/check_root_pipeline.py','web'])
    elif mode=='source-regression':
        tests(['tests/contracts','tests/quizbank/test_generation_pipeline_v2.py','tests/quizbank/test_authoring_recovery.py','tests/quizbank/test_connection_generate.py','tests/runner/test_root_tier_recovery.py','tests/runner/test_root_native_json.py'])
    elif mode=='runner-regression':
        tests(['tests/runner/test_connection_generation.py','tests/runner/test_status_batch.py','tests/runner/test_status.py','tests/runner/test_root_session_resume.py'])
    elif mode=='pilot-evidence':pilot()
    else:raise SystemExit('Unknown check')


if __name__=='__main__':main(sys.argv[1])
