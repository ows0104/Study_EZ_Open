"""Reproducible checks for the approved UI restoration; isolated synthetic data."""
import os,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOGS=ROOT/'runs/_development/2026-11-07-main-quiz-pharm-ui'
HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)

def env():
    result={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','ENVIRONMENT':'local-test','PYTHONPATH':str(ROOT)}
    for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):result.pop(key,None)
    return result

def run(args,cwd=ROOT,settings=None):
    subprocess.run([str(x)for x in args],cwd=cwd,env=settings or env(),check=True,
        creationflags=HIDDEN,stdin=subprocess.DEVNULL)

def port():
    with socket.socket()as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

def wait(url,process):
    for _ in range(120):
        if process.poll()is not None:raise RuntimeError('Owned fixture exited')
        try:
            with urllib.request.urlopen(url,timeout=1)as response:
                if response.status==200:return
        except OSError:pass
        time.sleep(.25)
    raise RuntimeError('Owned fixture did not become ready')

def main(mode):
    if mode=='web':
        run(['npm.cmd','run','typecheck'],ROOT/'web')
        run(['node','--test','tests/main-quiz-render.test.cjs'],ROOT/'web')
        run(['npm.cmd','run','build'],ROOT/'web');return
    if mode=='server-regression':
        for pattern in ('root_api','root_exposure','root_adaptive','root_state','root_preservation','main_quiz','root_replacement_import','root_reviewed_import','root_usage','usage_actions','route_contract'):
            run([sys.executable,'-m','tests',pattern],ROOT/'server')
        return
    if mode!='browser':raise ValueError('Unknown check')
    api_port,web_port=port(),port();api=f'http://127.0.0.1:{api_port}'
    LOGS.mkdir(parents=True,exist_ok=True)
    settings=env();settings.update(MAIN_QUIZ_UI_PORT=str(api_port),VITE_DEV_API=api,VITE_API_BASE_URL='',
        PUBLIC_API_BASE_URL='',VITE_SUPABASE_URL='',VITE_SUPABASE_ANON_KEY='',VITE_LOCAL_TEST_TOKEN='synthetic-ui-only',
        ROOT_TEST_URL=f'http://127.0.0.1:{web_port}/tests/root-learning.html',ROOT_TEST_OUTPUT=str(LOGS/'screenshots'))
    bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'
    if bundled.exists():settings.setdefault('PLAYWRIGHT_MODULE',str(bundled))
    processes=[]
    run(['npm.cmd','run','prepare-pdf'],ROOT/'web',settings)
    with (LOGS/'fixture-api.log').open('w',encoding='utf-8')as api_log,(LOGS/'fixture-web.log').open('w',encoding='utf-8')as web_log:
        try:
            server=subprocess.Popen([sys.executable,'-m','tests.serve_main_quiz_ui_fixture'],cwd=ROOT/'server',env=settings,stdout=api_log,stderr=subprocess.STDOUT,creationflags=HIDDEN);processes.append(server)
            wait(api+'/api/health',server)
            web=subprocess.Popen(['node','node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',str(web_port),'--strictPort'],cwd=ROOT/'web',env=settings,stdout=web_log,stderr=subprocess.STDOUT,creationflags=HIDDEN);processes.append(web)
            wait(settings['ROOT_TEST_URL'],web)
            run(['node','--test','tests/root-learning.test.cjs'],ROOT/'web',settings)
        finally:
            for process in reversed(processes):
                if process.poll()is None:
                    process.terminate();process.wait(timeout=10)

if __name__=='__main__':main(sys.argv[1])
