"""Bounded local checks; synthetic models and isolated test databases only."""
import os
from pathlib import Path
import subprocess
import sys
import uuid
ROOT=Path(__file__).resolve().parents[3];MAIN=ROOT.parents[1]
PY=MAIN/'.venv/Scripts/python.exe';SERVER=MAIN/'server/.venv/Scripts/python.exe'
temp=MAIN/'tmp'/('ti-env-'+uuid.uuid4().hex[:6]);temp.mkdir(parents=True)
env={**os.environ,'TEMP':str(temp),'TMP':str(temp),'PYTHONIOENCODING':'utf-8','PYTHONPATH':str(ROOT)}
for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(key,None)
def run(args,cwd=ROOT):subprocess.run([str(x)for x in args],cwd=cwd,env=env,check=True,timeout=180)
tests=(['tests/runner/test_root_tier_recovery.py']if sys.argv[1]=='tier-contract'else
       ['tests/contracts','tests/quizbank/test_authoring_recovery.py','tests/quizbank/test_generation_pipeline_v2.py',
        'tests/quizbank/test_connection_generate.py','tests/runner/test_root_native_json.py'])
if sys.argv[1]not in('tier-contract','tier-regression'):raise SystemExit('Unknown check')
run([PY,'-m','pytest',*tests,'-q','--tb=short','--basetemp='+str(MAIN/'tmp'/('ti-c-'+uuid.uuid4().hex[:6]))])
if sys.argv[1]=='tier-regression':
    for pattern in ('root_generation','root_pipeline_v2','root_preservation'):run([SERVER,'-m','tests',pattern],ROOT/'server')
