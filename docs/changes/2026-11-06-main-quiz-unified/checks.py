from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[3]
MAIN=ROOT if (ROOT/'.venv/Scripts/python.exe').exists() else ROOT.parent.parent
PYTHON=Path(os.environ.get('STUDYEZ_CHECK_PYTHON',str(MAIN/'.venv/Scripts/python.exe')))
SERVER=Path(os.environ.get('STUDYEZ_CHECK_SERVER',str(MAIN/'server/.venv/Scripts/python.exe')))
env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','TEMP':str(MAIN/'tmp'),'TMP':str(MAIN/'tmp')}
for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(key,None)
def run(command,cwd=ROOT):
 r=subprocess.run([str(x)for x in command],cwd=cwd,env=env)
 if r.returncode:raise SystemExit(r.returncode)
mode=sys.argv[1]
if mode=='main-quiz-contract':
 run([SERVER,'-m','tests','main_quiz'],ROOT/'server')
 run([PYTHON,'-m','pytest','tests/contracts','tests/quizbank','-q','-p','no:cacheprovider','--basetemp',MAIN/'tmp/mq-release-contract'])
elif mode=='server-regression':
 for pattern in ('root','bank','route_contract','usage'):
  run([SERVER,'-m','tests',pattern],ROOT/'server')
elif mode=='web':
 run(['node','--test','tests/main-quiz-web-author.test.cjs','tests/main-quiz-render.test.cjs','tests/bank-links.test.cjs','tests/stem-artifacts.test.cjs','tests/bank-prompt-current.test.cjs','tests/bank-bridge.test.cjs'],ROOT/'web')
 # Build creates the same prompt with checkout-specific CRLF hashes. Preserve the
 # tracked generated file after checking its text differs only by line endings.
 import json
 prompt=ROOT/'web/public/bank-prompt.json';original=prompt.read_bytes()
 try:
  run(['npm.cmd','run','build'],ROOT/'web')
  a=json.loads(original);b=json.loads(prompt.read_bytes())
  assert a['version']==b['version']
  assert a['template'].replace('\r\n','\n')==b['template'].replace('\r\n','\n')
  for k in a['deliveries']:assert a['deliveries'][k].replace('\r\n','\n')==b['deliveries'][k].replace('\r\n','\n')
 finally:prompt.write_bytes(original)
else:raise SystemExit('unknown check')
