"""Revision-bound checks; no new model calls or production services."""
import os
from pathlib import Path
import subprocess
import sys
import uuid
import hashlib,json
ROOT=Path(__file__).resolve().parents[3];MAIN=ROOT.parents[1]
PY=MAIN/'.venv/Scripts/python.exe';SERVER=MAIN/'server/.venv/Scripts/python.exe'
temp=MAIN/'tmp'/('ru-env-'+uuid.uuid4().hex[:6]);temp.mkdir(parents=True)
env={**os.environ,'TEMP':str(temp),'TMP':str(temp),'PYTHONIOENCODING':'utf-8','PYTHONPATH':str(ROOT)}
for key in ('PYTHONHOME','UV_INTERNAL__PYTHONHOME'):env.pop(key,None)
def run(args,cwd=ROOT):subprocess.run([str(x)for x in args],cwd=cwd,env=env,check=True,timeout=180)
check=sys.argv[1]
if check in ('recall-contract','pipeline-regression'):
    tests=['tests/contracts/test_recall_units.py','tests/quizbank/test_generation_pipeline_v2.py']if check=='recall-contract'else[
        'tests/contracts','tests/quizbank/test_generation_pipeline_v2.py','tests/quizbank/test_connection_generate.py','tests/runner/test_root_native_json.py']
    run([PY,'-m','pytest',*tests,'-q','--tb=short','--basetemp='+str(MAIN/'tmp'/('ru-check-'+uuid.uuid4().hex[:6]))])
    if check=='pipeline-regression':
        for pattern in ('root_generation','root_pipeline_v2','root_preservation','root_recall_units'):run([SERVER,'-m','tests',pattern],ROOT/'server')
elif check=='main-quiz-ui':
    run(['node','--test','tests/stem-artifacts.test.cjs'],ROOT/'web')
    run(['node','node_modules/typescript/bin/tsc','-p','tsconfig.json','--noEmit'],ROOT/'web')
    run(['node','node_modules/typescript/bin/tsc','-p','../docs/changes/2026-11-06-recall-units/tsconfig.json','--noEmit'],ROOT/'web')
    files=['web/src/bank/BankStem.tsx','web/tests/stem-artifacts.test.cjs',
        'docs/changes/2026-11-06-recall-units/compare.tsx','docs/changes/2026-11-06-recall-units/compare.css']
    (MAIN/'runs/_recall/261106/ui-checks.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in files},indent=2),encoding='utf-8')
elif check=='live-comparison':run([PY,ROOT/'docs/changes/2026-11-06-recall-units/comparison.py','verify'])
else:raise SystemExit('Unknown check')
