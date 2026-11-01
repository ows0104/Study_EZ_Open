"""Reproduce current production, then apply only the approved professor rules."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
CHANGE=HERE.name
DEPLOYED=ROOT/'runs/_development/2026-11-01-usage-action-clarity/isolated'
OUT=ROOT/'output/releases/jokbo-web-deploy'
OVERLAYS=('web/src/lecture/reviewProfessor.ts','web/src/lecture/reviewPrompt.ts',
          'web/tests/review-professor.test.cjs','content/prompts/bank/bankPrompt.md')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def manifest(folder):return {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

assert not OUT.exists(),'Preserve an existing source'
state=json.loads((ROOT/'docs/changes/2026-11-01-usage-action-clarity/state.json').read_text(encoding='utf-8'))
deployed=next(d for d in state['deployments'] if d['status']=='succeeded' and d['revision']=='a0edf1f4-981e-4568-8b5a-7c2ad1e54617')
baseline=ROOT/deployed['candidate']['artifact']
sys.path.insert(0,str(DEPLOYED/'scripts'));import workflow_scope
assert workflow_scope.fingerprint(DEPLOYED,'site')==deployed['candidate']['source_hash'],'Deployed source changed'
OUT.mkdir(parents=True)
ignore=shutil.ignore_patterns('node_modules','.venv','dist','runs','output','__pycache__','.pytest_cache',
                              '.wrangler','local_test_data','release','.env*','*.pyc','*.tsbuildinfo')
paths=('scripts','web','server','content','bridge','platform','studyez_contracts','data/timetable',
       'tests/contracts','tests/bridge','tests/development','pyproject.toml','requirements.txt','uv.lock')
for name in paths:
    src=DEPLOYED/name;dest=OUT/name
    if src.is_dir():shutil.copytree(src,dest,ignore=ignore)
    else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
shutil.copytree(DEPLOYED/'web/node_modules',OUT/'web/node_modules')
for name in ('.env','.env.local','.env.production','.env.production.local'):
    path=DEPLOYED/'web'/name
    if path.is_file():shutil.copyfile(path,OUT/'web'/name)
subprocess.run(['npm.cmd','run','build'],cwd=OUT/'web',check=True)
actual=manifest(OUT/'web/dist');expected=manifest(baseline)
assert actual==expected,{'only_new':sorted(set(actual)-set(expected)),
                         'only_baseline':sorted(set(expected)-set(actual)),
                         'changed':[n for n in actual.keys()&expected.keys() if actual[n]!=expected[n]]}
baseline_record={'status':'passed','production_revision':deployed['revision'],'candidate':deployed['candidate']['id'],
                 'baseline_source_hash':deployed['candidate']['source_hash'],'files':expected}
save(HERE/'production-baseline.json',baseline_record)
for name in OVERLAYS:
    dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
record={'source':str(OUT),'baseline_source':str(DEPLOYED),'baseline_revision':deployed['revision'],
        'overlays':{name:sha(ROOT/name) for name in OVERLAYS},'production_baseline':baseline_record}
save(HERE/'isolation.json',record)
change=OUT/'docs/changes'/CHANGE;change.parent.mkdir(parents=True,exist_ok=True)
shutil.copytree(HERE,change)
print('PASS: exact current production reproduced; four professor-rule files overlaid at',OUT)
