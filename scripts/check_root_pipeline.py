"""Reproducible checks: synthetic models, fresh local databases, owned local servers."""
import hashlib,json,os,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PY=ROOT/'.venv/Scripts/python.exe'
SERVER=ROOT/'server/.venv/Scripts/python.exe'
LOGS=ROOT/'runs/_development/2026-11-05-root-pipeline-guards'
HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)

def run(args,cwd=ROOT,env=None):
    child_env=dict(os.environ if env is None else env)
    for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):child_env.pop(key,None)
    subprocess.run([str(x)for x in args],cwd=cwd,env=child_env,check=True,creationflags=HIDDEN,
        stdin=subprocess.DEVNULL,stdout=sys.stdout,stderr=sys.stderr)

def preservation():
    expected={
        'runs/_examples/cholinergic-exception-20261105/result.json':'783e18927c59f740f997058d1f987743f57e323863a9ec2dafade4d0263de523',
        'runs/_examples/cholinergic-findings-20261104/result.json':'f38bdb64ad60c30bb98797cd13fe23f164b0ffa020d9db43b4e4c08dd828c478',
        'runs/_examples/cholinergic-20261104/assembled-result.json':'e0ef0426dba81f42e29a7cb7a04a269cb4818465c777d2c572bc19e6a7370886',
        'runs/_root-generation/f0a8f3b68e3642598f85bbf462e1dc55/source-0.pdf':'29bb4ad01a626a581c198ea8c4bc96aed1cae225759f946fda076b3d394e3728',
        'runs/_root-generation/f0a8f3b68e3642598f85bbf462e1dc55/source-1.md':'505f589dea926fb522e92411b7e5f37b67945e8ec6bad1b4e5983d1af6231b37'}
    for name,digest in expected.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:raise ValueError('Preserved example changed: '+name)
    print('PASS read-only hashes: three original cholinergic examples and two frozen source files untouched',flush=True)

def port():
    with socket.socket()as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]

def stop(p):
    if p.poll()is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=HIDDEN)
    else:p.terminate()
    p.wait(timeout=15)

def wait_http(url,p):
    for _ in range(120):
        if p.poll()is not None:raise RuntimeError('Owned fixture exited before ready')
        try:
            with urllib.request.urlopen(url,timeout=1)as r:
                if r.status==200:return
        except OSError:pass
        time.sleep(.25)
    raise RuntimeError('Owned local server startup timed out')

def web():
    api_port=port();web_port=port();api='http://127.0.0.1:'+str(api_port)
    LOGS.mkdir(parents=True,exist_ok=True);tag=str(time.time_ns());env=os.environ.copy()
    for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(key,None)
    env.update(GENERATION_TEST_PORT=str(api_port),VITE_DEV_API=api,VITE_API_BASE_URL='',
        VITE_SUPABASE_URL='',VITE_SUPABASE_ANON_KEY='',VITE_LOCAL_TEST_TOKEN='synthetic-browser-only',
        PLAYWRIGHT_MODULE=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
        GENERATION_TEST_API=api,ROOT_TEST_URL=f'http://127.0.0.1:{web_port}/tests/root-learning.html',ROOT_TEST_OUTPUT=str(LOGS/'browser'))
    Path(env['ROOT_TEST_OUTPUT']).mkdir(parents=True,exist_ok=True)
    processes=[]
    with (LOGS/(tag+'-api.log')).open('w',encoding='utf-8')as api_log,(LOGS/(tag+'-vite.log')).open('w',encoding='utf-8')as vite_log:
        try:
            server=subprocess.Popen([str(SERVER),'-m','tests.serve_generation_fixture'],cwd=ROOT/'server',env=env,stdout=api_log,stderr=subprocess.STDOUT,creationflags=HIDDEN);processes.append(server)
            wait_http(api+'/openapi.json',server)
            vite=subprocess.Popen(['node','node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(web_port),'--strictPort'],cwd=ROOT/'web',env=env,stdout=vite_log,stderr=subprocess.STDOUT,creationflags=HIDDEN);processes.append(vite)
            wait_http(env['ROOT_TEST_URL'],vite)
            run(['node','--test','tests/root-generation.test.cjs'],ROOT/'web',env)
        finally:
            try:urllib.request.urlopen(urllib.request.Request(api+'/__test/stop',method='POST'),timeout=10).close()
            except OSError:pass
            for p in reversed(processes):stop(p)
    # Production build uses the repository's normal environment, never the
    # browser fixture's local API/auth overrides. It is not deployed here.
    build_env=os.environ.copy()
    run(['npm.cmd'if os.name=='nt'else'npm','run','typecheck'],ROOT/'web',build_env)
    run(['npm.cmd'if os.name=='nt'else'npm','run','build'],ROOT/'web',build_env)

def main():
    mode=sys.argv[1]
    if mode=='contracts':
        run([PY,'-m','pytest','tests/contracts','-q','--basetemp','runs/_test-temp/pipeline-contracts-'+str(time.time_ns())]);preservation()
    elif mode=='generator':
        # Native PDF libraries still encounter MAX_PATH on deeply nested legacy
        # evidence-cache tests. This is a new, owned, short temporary directory.
        base=tempfile.mkdtemp(prefix='sepg-')
        run([PY,'-m','pytest','tests/quizbank','tests/studyez_llm','-q','--basetemp',base])
    elif mode=='runner':run([PY,'-m','pytest','tests/runner/test_connection_generation.py','tests/runner/test_root_session_resume.py','-q','--basetemp','runs/_test-temp/pipeline-runner-'+str(time.time_ns())])
    elif mode=='server':
        base=ROOT/'server/local_test_data';base.mkdir(exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix='pipeline-checks-',dir=base));env=os.environ.copy()
        env.update(ENVIRONMENT='local-test',DATABASE_URL='sqlite:///'+(folder/'test.db').as_posix(),STUDYEZ_LOCAL_STORAGE_DIR=str(folder/'storage'))
        for name in ('root_','route_contract','bank_publication','bank_slides','bank_coverage','matching_presentation'):
            run([SERVER,'-m','tests',name],ROOT/'server',env)
    elif mode=='web':web()
    else:raise SystemExit('contracts/generator/runner/server/web')

if __name__=='__main__':main()
