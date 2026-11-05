"""Export HEAD and overlay only the authorized root product and web pipeline."""
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'runs/_development/2026-11-03-root-web-deployment/checkout'
FILES='''quizbank/connection_generate.py
runner/connection_generation.py
runner/bank_flow/execution.py
studyez_contracts/pyproject.toml
server/app/main.py
server/app/models/__init__.py
server/app/models/root_learning.py
server/app/models/root_generation.py
server/app/routes/root_learning.py
server/app/routes/root_generation.py
server/app/routes/bank_api/publication.py
server/app/routes/usage.py
server/app/usage_actions.py
server/deploy.ps1
server/tests/root_support.py
server/tests/serve_root_fixture.py
server/tests/serve_generation_fixture.py
server/tests/test_route_contract.py
web/src/App.tsx
web/src/bank/BankStart.tsx
web/src/bank/BankStudy.tsx
web/src/bank/StudyOverview.tsx
web/src/bank/BankPanel.tsx
web/src/bank/bankBridge.ts
web/src/bank/prompt.ts
web/src/bank/rootWeb.ts
web/src/bank/RootLearning.tsx
web/src/bank/RootMap.tsx
web/src/bank/RootSolve.tsx
web/src/bank/RootToday.tsx
web/src/bank/RootGenerationPanel.tsx
web/src/bank/useRootStudyWrites.ts
web/src/bank/roots.css
web/src/types/rootLearning.ts
web/src/notices/GuidePage.tsx
web/tests/root-learning.html
web/tests/root-learning.tsx
web/tests/root-learning.test.cjs
web/tests/root-generation.test.cjs
tests/contracts/root_fixture.py
tests/contracts/automation_fixture.py
tests/contracts/test_root_automation.py
tests/contracts/test_roots.py
tests/contracts/test_learning_links.py
tests/quizbank/test_connection_generate.py
tests/quizbank/generation_fixture_cli.py
tests/runner/test_connection_generation.py
tests/runner/generation_fixture_worker.py
scripts/check_root_learning.py
scripts/check_connection_generation.py
scripts/prepare_root_release.py
scripts/root_production_schema.py
scripts/root_production_smoke.py
scripts/cloudflare_release.py'''.splitlines()
FOLDERS=['studyez_contracts/roots','studyez_contracts/learning_links','server/app/root_learning',
         'content/prompts/learning-links/automation','docs/changes/2026-11-03-root-web-deployment']


def replace(path,old,new):
    text=path.read_text(encoding='utf-8')
    if old not in text:raise ValueError('Expected scoped edit not found: '+str(path))
    path.write_text(text.replace(old,new),encoding='utf-8')


def main():
    if DEST.exists():raise ValueError('Use the existing scoped copy; do not erase its evidence or outputs.')
    DEST.mkdir(parents=True)
    archive=DEST.parent/'head.zip'
    subprocess.run(['git','archive','--format=zip','HEAD','-o',str(archive)],cwd=ROOT,check=True)
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if not (DEST/item.filename).resolve().is_relative_to(DEST.resolve()):raise ValueError('Invalid archive path')
        z.extractall(DEST)
    files=list(FILES)+[p.relative_to(ROOT).as_posix() for p in (ROOT/'server/tests').glob('test_root_*.py')]
    for folder in FOLDERS:
        files += [p.relative_to(ROOT).as_posix() for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    for name in sorted(set(files)):
        target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    replace(DEST/'server/app/main.py','from app.routes import connections\n','')
    replace(DEST/'server/app/main.py','app.include_router(connections.router, prefix="/api")\n','')
    replace(DEST/'server/app/models/__init__.py','from app.models.connections import ConnectionContent, ConnectionState, ConnectionEvent\n','')
    usage=DEST/'server/app/routes/usage.py'
    replace(usage,'from app.models.connections import ConnectionEvent\n','')
    replace(usage,'    connection_saves = _count_by_user(db, ConnectionEvent, ConnectionEvent.created_at, span)\n','')
    replace(usage,'        (ConnectionEvent, ConnectionEvent.created_at),\n','')
    replace(usage,'                "connectionSaves": connection_saves.get(uid, 0),\n','')
    replace(usage,'            "connectionSaves": {"count": 0, "lastAt": None},\n','')
    text=usage.read_text(encoding='utf-8');start=text.index('    for subject, run_id, count, last in db.execute(select(\n        ConnectionEvent')
    end=text.index('    for event in db.scalars(select(RootEvent)',start)
    usage.write_text(text[:start]+text[end:],encoding='utf-8')
    replace(DEST/'server/app/usage_actions.py',"    Action('connection_save', '연결 학습 저장 (이동·열람·자기확인)', 'quizzes', ('connectionSaves',),\n           ('connectionSaves', 'count'), ('connectionSaves', 'lastAt'), '작업', '작업'),\n",'')
    path=DEST/'server/tests/test_route_contract.py';text=path.read_text(encoding='utf-8')
    start=text.index('    connection_routes = ');end=text.index('    root_routes = ',start)
    text=text[:start]+text[end:];text=text.replace("ROUTES + '\\n' + connection_routes + '\\n' + root_routes","ROUTES + '\\n' + root_routes")
    path.write_text(text,encoding='utf-8')
    for name in ('App.tsx','bank/BankStart.tsx','bank/BankStudy.tsx'):
        path=DEST/'web/src'/name;text=path.read_text(encoding='utf-8')
        text='\n'.join(line for line in text.split('\n') if 'ConnectionLearning' not in line and 'ConnectionEntry' not in line)
        path.write_text(text,encoding='utf-8')
    path=DEST/'web/src/notices/GuidePage.tsx';text=path.read_text(encoding='utf-8')
    start=text.index('        <p>Main-Quiz의 <b>연결부터 학습하기');end=text.index('</p>',start)+4
    text=text[:start]+text[end:];text='\n'.join(line for line in text.split('\n') if '빈칸 문제는 답을 펼치면' not in line)
    path.write_text(text,encoding='utf-8')
    # Environment copies are never part of the artifact, and their values are never printed.
    for name in ('server/.env','web/.env','web/.env.local','web/.env.production','web/.env.production.local'):
        if (ROOT/name).exists():shutil.copy2(ROOT/name,DEST/name)
    path=DEST/'server/.env';text=path.read_text(encoding='utf-8-sig')
    lines=[line for line in text.splitlines() if not line.startswith('STUDYEZ_ROOT_LEARNING_ENABLED=')]
    path.write_text('\n'.join(lines)+'\nSTUDYEZ_ROOT_LEARNING_ENABLED=true\n',encoding='utf-8')
    for name,target in [('.venv',ROOT/'.venv'),('server/.venv',ROOT/'server/.venv'),('web/node_modules',ROOT/'web/node_modules')]:
        quote=lambda value:"'"+str(value).replace("'","''")+"'"
        subprocess.run(['powershell','-NoProfile','-Command',f'New-Item -ItemType Junction -Path {quote(DEST/name)} -Target {quote(target)}'],check=True,capture_output=True)
    (DEST.parent/'scoped-files.json').write_text(json.dumps(sorted(set(files)),indent=2),encoding='utf-8')
    print(DEST)


if __name__=='__main__':main()
