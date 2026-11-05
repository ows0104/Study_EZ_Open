"""Prepare a new isolated checkout without changing the original or deployed baselines."""
import hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'tmp/preview-bridge-20261105'
DEST=ROOT/'tmp/rp5'
CHANGE='2026-11-05-root-pipeline-deploy'
IGNORE=shutil.ignore_patterns('__pycache__','.venv','node_modules','dist','build','local_test_data','*.egg-info')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy(name,source=ROOT):
    src=source/name;dst=DEST/name
    if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True,ignore=IGNORE)
    else:dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def main():
    if DEST.exists()and('--resume-preparation'not in sys.argv or (DEST/'docs/changes'/CHANGE/'scope.json').exists()):raise ValueError('Keep existing evidence; destination must be new')
    DEST.mkdir(parents=True,exist_ok=True)
    archive=ROOT/'runs/_development'/CHANGE/'head.zip';archive.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','archive','--format=zip','HEAD','-o',str(archive)],cwd=ROOT,check=True)
    with zipfile.ZipFile(archive)as z:
        assert all((DEST/i.filename).resolve().is_relative_to(DEST.resolve())for i in z.infolist())
        z.extractall(DEST)
    for name in ['bridge','content','data','platform','server/app','server/tests','web/src','web/tests',
                 'web/scripts','studyez_contracts','scripts','tests/bridge']:
        copy(name,BASE)
    for name in ['web/package.json','web/package-lock.json','server/deploy.ps1','server/deploy-revision.ps1','server/prepare-build.ps1']:
        if (BASE/name).exists():copy(name,BASE)
    for name in ['server/.env','web/.env','web/.env.local','web/.env.production','web/.env.production.local']:
        if (BASE/name).exists():copy(name,BASE)
    for name,target in [('.venv',ROOT/'.venv'),('server/.venv',ROOT/'server/.venv'),('web/node_modules',ROOT/'web/node_modules')]:
        q=lambda p:"'"+str(p).replace("'","''")+"'"
        if not (DEST/name).exists():subprocess.run(['powershell','-NoProfile','-Command',f'New-Item -ItemType Junction -Path {q(DEST/name)} -Target {q(target)}'],capture_output=True,check=True)
    log=DEST/'baseline-build.log'
    with log.open('w',encoding='utf-8')as out:
        subprocess.run(['npm.cmd','run','build'],cwd=DEST/'web',stdout=out,stderr=subprocess.STDOUT,check=True)
    deployed=json.loads((BASE/'docs/changes/2026-11-05-preview-bridge-deploy/state.json').read_text(encoding='utf-8'))['deployments'][-1]['candidate']['files']
    actual={p.relative_to(DEST/'web/dist').as_posix():sha(p)for p in (DEST/'web/dist').rglob('*')if p.is_file()}
    assert actual==deployed,'Baseline rebuild differs from currently deployed web'
    server=json.loads((ROOT/'docs/changes/2026-11-04-coverage-requirement/verified-scope/state.json').read_text(encoding='utf-8'))['deployments'][-1]['candidate']['files']
    mismatches=[n for n,h in server.items()if not (DEST/('server/'+n if not n.startswith('studyez_contracts/')else n)).is_file()or sha(DEST/('server/'+n if not n.startswith('studyez_contracts/')else n))!=h]
    # The preview baseline inherits the last API source; prove it before overlay.
    assert not mismatches,('Server baseline differs',mismatches)
    files='''quizbank/connection_generate.py
quizbank/connection_generate_v2.py
quizbank/connection_visuals.py
runner/connection_generation.py
runner/root_session_resume.py
studyez_llm/codex.py
studyez_contracts/bank/schema.py
studyez_contracts/bank/validate.py
server/app/routes/root_generation.py
server/app/routes/root_learning.py
server/app/routes/bank_api/presentation.py
server/app/quiz_cloze.py
web/src/bank/BankQuestion.tsx
web/src/bank/review-notes.css
web/src/bank/RootSolve.tsx
web/src/bank/RootMap.tsx
web/src/types/bank.ts
web/src/types/rootLearning.ts
web/tests/root-generation.test.cjs
tests/contracts/automation_fixture.py
tests/contracts/generation_v2_fixture.py
tests/contracts/test_generation_v2.py
tests/quizbank/test_generation_pipeline_v2.py
tests/runner/test_connection_generation.py
tests/runner/test_root_session_resume.py
tests/runner/generation_fixture_worker.py
tests/studyez_llm/test_codex.py
server/tests/serve_generation_fixture.py
server/tests/test_root_pipeline_v2.py
server/tests/test_root_generation.py
server/tests/test_root_source_assessment.py
scripts/check_root_pipeline.py
scripts/cloudflare_release.py
scripts/root_production_smoke.py'''.splitlines()
    folders=['studyez_contracts/roots','studyez_contracts/learning_links','server/app/root_learning',
             'content/prompts/learning-links/automation']
    for name in files+folders:copy(name)
    for folder in folders:
        files += [p.relative_to(ROOT).as_posix()for p in (ROOT/folder).rglob('*')if p.is_file()and '__pycache__'not in p.parts]
    copy('docs/changes/'+CHANGE)
    # Immutable originals are copied only so the same read-only preservation check runs in this checkout.
    for name in ['runs/_examples/cholinergic-exception-20261105/result.json','runs/_examples/cholinergic-findings-20261104/result.json',
                 'runs/_examples/cholinergic-20261104/assembled-result.json',
                 'runs/_root-generation/f0a8f3b68e3642598f85bbf462e1dc55/source-0.pdf',
                 'runs/_root-generation/f0a8f3b68e3642598f85bbf462e1dc55/source-1.md']:copy(name)
    proof={'baselineWebExact':True,'baselineServerExact':True,'files':{n:sha(ROOT/n)for n in sorted(set(files))},'originalRoot':str(ROOT)}
    (DEST/'docs/changes'/CHANGE/'scope.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps({'checkout':str(DEST),'baselineWebExact':True,'baselineServerExact':True,'overlayFiles':len(set(files))}))
if __name__=='__main__':main()
