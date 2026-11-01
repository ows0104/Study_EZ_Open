from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
iso=ROOT/'output/releases/jokbo-web-deploy';target=iso/'docs/changes'/HERE.name
meta=json.loads((target/'isolation.json').read_text(encoding='utf-8'))
meta['baseline_artifact']=str(ROOT/'runs/_development/2026-11-01-usage-action-clarity/candidates'/meta['production_baseline']['candidate'])
for folder in (HERE,target):
    (folder/'isolation.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for name in ('runner','quizgen','quizbank'):
    dest=iso/name
    if not dest.exists():shutil.copytree(Path(meta['baseline_source'])/name,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for name in ('verify_production_base.py','cloudflare_release.py'):
    shutil.copyfile(HERE/name,target/name)
shutil.copyfile(ROOT/'scripts/production_smoke.py',target/'production_smoke.py')
src=(HERE.parent/'2026-11-01-jokbo-professor-priority/postcheck.py').read_text(encoding='utf-8')
src=src.replace('ROOT = Path(__file__).resolve().parents[3]',
                'ROOT = Path(__file__).resolve().parents[3]\nHERE = Path(__file__).resolve().parent\nSECRETS_ROOT = Path('+repr(str(ROOT))+')')
src=src.replace("str(ROOT / 'scripts/production_smoke.py')","str(HERE / 'production_smoke.py')")
src=src.replace("ROOT / 'server/.env'","SECRETS_ROOT / 'server/.env'")
(target/'postcheck.py').write_text(src,encoding='utf-8')
config=json.loads((HERE.parent/'2026-11-01-jokbo-professor-priority/web-release-config.json').read_text(encoding='utf-8'))
runtime=str(ROOT/'server/.venv/Scripts/python.exe')
config['smoke_command']=[runtime,'-X','utf8','-B',str(target/'postcheck.py'),'--revision','{revision}','--artifact','{artifact}']
config['deploy_command']=[runtime,'-X','utf8','-B',str(target/'cloudflare_release.py'),'publish','--artifact','{artifact}']
config['revision_command']=[runtime,'-X','utf8','-B',str(target/'cloudflare_release.py'),'revision']
config['rollback']='Restore Pages production a0edf1f4-981e-4568-8b5a-7c2ad1e54617 in study-ez-open. Static web only; no DB/API/data reversal.'
(target/'web-release-config.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
print('Isolated source and deployment checks prepared.')
