"""Revision-bound checks with owned short temporary paths and isolated server DBs."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[3]
MAIN=ROOT.parents[1];PY=MAIN/'.venv/Scripts/python.exe';SERVER=MAIN/'server/.venv/Scripts/python.exe'
temp=MAIN/'tmp'/('ar-env-'+uuid.uuid4().hex[:6]);temp.mkdir(parents=True)
env={**os.environ,'TEMP':str(temp),'TMP':str(temp),'PYTHONIOENCODING':'utf-8','PYTHONPATH':str(ROOT)}
for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(key,None)

def run(args,cwd=ROOT):
    subprocess.run([str(x)for x in args],cwd=cwd,env=env,check=True,timeout=180)

if sys.argv[1]=='recovery-contract':
    run([PY,'-m','pytest','tests/quizbank/test_authoring_recovery.py','-q','--tb=short',
         '--basetemp='+str(MAIN/'tmp'/('ar-c-'+uuid.uuid4().hex[:6]))])
elif sys.argv[1]=='pipeline-regression':
    run([PY,'-m','pytest','tests/contracts','tests/quizbank/test_generation_pipeline_v2.py',
         'tests/quizbank/test_connection_generate.py','tests/runner/test_root_native_json.py',
         '-q','--tb=short','--basetemp='+str(MAIN/'tmp'/('ar-p-'+uuid.uuid4().hex[:6]))])
    for pattern in ('root_generation','root_pipeline_v2','root_preservation'):
        run([SERVER,'-m','tests',pattern],ROOT/'server')
else:raise SystemExit('Unknown check')
