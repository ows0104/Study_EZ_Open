"""Publish approved static files and identify exactly the resulting Pages deployment."""
import argparse, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
WRANGLER=Path.home()/'AppData/Local/npm-cache/_npx/32026684e21afda6/node_modules/wrangler/bin/wrangler.js'
p=argparse.ArgumentParser(); p.add_argument('action',choices=['publish','revision','list']); p.add_argument('--artifact'); a=p.parse_args()
receipt=ROOT/'runs/_development/2026-11-01-jokbo-professor-priority/pages-upload.json'
def call(args):
    r=subprocess.run(['node',str(WRANGLER),*args],capture_output=True,text=True,encoding='utf-8',timeout=600)
    if r.returncode: raise SystemExit('Cloudflare command failed; authenticate the existing deployment account and retry.')
    return r.stdout
def deployments():
    return json.loads(call(['pages','deployment','list','--project-name','study-ez-open','--environment','production','--json']))
if a.action=='publish':
    if not a.artifact or not (Path(a.artifact)/'index.html').is_file(): raise SystemExit('Missing approved web artifact')
    output=call(['pages','deploy',a.artifact,'--project-name','study-ez-open','--branch','master','--commit-dirty=true'])
    urls=re.findall(r'https://[a-z0-9-]+\.study-ez-open\.pages\.dev',output)
    if not urls: raise SystemExit('Upload completed but exact deployment URL was not returned')
    rows=[row for row in deployments() if row['Deployment'].rstrip('/')==urls[-1].rstrip('/')]
    if len(rows)!=1 or rows[0]['Environment']!='Production': raise SystemExit('Exact production upload not confirmed')
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(rows[0],indent=2),encoding='utf-8')
    print('Uploaded exact candidate: '+rows[0]['Id'])
elif a.action=='revision':
    expected=json.loads(receipt.read_text(encoding='utf-8'))
    rows=deployments()
    if not rows or rows[0]['Id']!=expected['Id']: raise SystemExit('Newest production deployment differs from this upload')
    print(expected['Id'])
else: print(json.dumps(deployments(),indent=2))
