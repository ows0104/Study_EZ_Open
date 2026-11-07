"""Start owned local API/UI processes; keep real experimental learner events."""
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from experiment import ROOT,OUT,check_inputs

def ready(p,url):
    for _ in range(180):
        if p.poll()is not None:raise RuntimeError('Local process exited: '+url)
        try:
            with urlopen(url,timeout=1)as r:
                if r.status==200:return
        except OSError:time.sleep(.2)
    raise RuntimeError('Local readiness timeout: '+url)

def start():
    check_inputs();state=OUT/'local-app';state.mkdir(exist_ok=True)
    assert not(state/'processes.json').exists(),'Preserve ownership record; do not start duplicate servers'
    env={**os.environ,'PYTHONIOENCODING':'utf-8','VITE_LOCAL_TEST_TOKEN':'e2e-local-only',
         'VITE_API_BASE_URL':'','VITE_DEV_API':'http://127.0.0.1:8036',
         'VITE_SUPABASE_URL':'','VITE_SUPABASE_ANON_KEY':'','VITE_SESSION_DOMAIN':''}
    # The authoring interpreter exports uv's Python home. The server has its own
    # interpreter; inheriting that home mixes two different standard libraries.
    for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(key,None)
    api_log=(state/'api.log').open('a',encoding='utf-8');web_log=(state/'web.log').open('a',encoding='utf-8')
    flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
    server_python=ROOT.parents[1]/'server/.venv/Scripts/python.exe'
    api=subprocess.Popen([str(server_python),str(HERE/'local_app.py')],cwd=ROOT,env=env,
        stdin=subprocess.DEVNULL,stdout=api_log,stderr=subprocess.STDOUT,creationflags=flags)
    web=None
    try:
        ready(api,'http://127.0.0.1:8036/api/health')
        web=subprocess.Popen(['node',str(ROOT/'web/node_modules/vite/bin/vite.js'),
            '--config',str(HERE/'vite.config.ts'),'--host','127.0.0.1','--port','5196','--strictPort'],
            cwd=ROOT/'web',env=env,stdin=subprocess.DEVNULL,stdout=web_log,stderr=subprocess.STDOUT,creationflags=flags)
        ready(web,'http://127.0.0.1:5196/')
        value={'apiPid':api.pid,'webPid':web.pid,'apiPort':8036,'webPort':5196,
               'database':str(state/'study.db'),'productionConnected':False}
        (state/'processes.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
        print(json.dumps(value),flush=True)
    except BaseException:
        for p in (web,api):
            if p and p.poll()is None:p.terminate();p.wait(timeout=10)
        raise

if __name__=='__main__':start()
