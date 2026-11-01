"""Publish one approved candidate, guarding the current production version."""
import argparse,ctypes,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
EXPECTED='0ca1ec7b-bdc2-4775-8916-4b1dca98563d'
WRANGLER=Path.home()/'AppData/Local/npm-cache/_npx/32026684e21afda6/node_modules/wrangler/bin/wrangler.js'
receipt=HERE/'pages-upload.json'
def short(path):
    fn=ctypes.windll.kernel32.GetShortPathNameW
    fn.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint32];fn.restype=ctypes.c_uint32
    buf=ctypes.create_unicode_buffer(32768);n=fn(str(path),buf,len(buf));value=buf.value
    if value.startswith('\\\\?\\'):value=value[4:]
    assert n and os.path.samefile(path,value),'Short path must identify the same directory'
    return value
def call(args):
    result=subprocess.run(['node',str(WRANGLER),*args],cwd=short(ROOT),capture_output=True,text=True,encoding='utf-8',timeout=600)
    if result.returncode:
        (HERE/'cloudflare-command-failure.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        raise SystemExit('Cloudflare command failed; inspect the preserved log before any retry.')
    return result.stdout
def deployments():return json.loads(call(['pages','deployment','list','--project-name','study-ez-open','--environment','production','--json']))
p=argparse.ArgumentParser();p.add_argument('action',choices=['publish','revision']);p.add_argument('--artifact');args=p.parse_args()
if args.action=='publish':
    assert args.artifact and (Path(args.artifact)/'index.html').is_file()
    assert deployments()[0]['Id']==EXPECTED,'Production changed since validation; stop before upload'
    output=call(['pages','deploy',short(Path(args.artifact)),'--project-name','study-ez-open','--branch','master','--commit-dirty=true'])
    urls=re.findall(r'https://[a-z0-9-]+\.study-ez-open\.pages\.dev',output)
    assert urls,'Exact deployment URL was not returned'
    rows=[r for r in deployments() if r['Deployment'].rstrip('/')==urls[-1].rstrip('/')]
    assert len(rows)==1 and rows[0]['Environment']=='Production'
    receipt.write_text(json.dumps(rows[0],indent=2)+'\n',encoding='utf-8')
    print('Uploaded exact candidate:',rows[0]['Id'])
else:
    expected=json.loads(receipt.read_text(encoding='utf-8'));assert deployments()[0]['Id']==expected['Id']
    print(expected['Id'])
