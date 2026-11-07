"""Read-only public Main Quiz asset and unchanged source verification."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from urllib.parse import urljoin
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'runs/_replacement/261104_02-v1'
WEB='https://study-ez-open.pages.dev'
def get(path):
    return subprocess.run(['curl.exe','--fail','--silent','--show-error',urljoin(WEB,path)],capture_output=True,check=True).stdout
def main(revision):
    old=json.loads((OUT/'deployed-ui-before.json').read_text(encoding='utf-8'))
    changed=subprocess.run(['git','diff','--name-only','7b96003f',revision,'--',*old['sourceFiles']],cwd=ROOT,capture_output=True,text=True,check=True).stdout
    assert not changed.strip(),'Main Quiz UI source changed'
    html=get('/').decode();index=re.search(r'<script[^>]+src="([^"]+)"',html).group(1)
    js=get(index).decode()
    paths=set('/assets/'+p.split('/')[-1]for p in re.findall(r'[^"\s,]*RootLearning-[^"\s,]+\.js',js))
    assert len(paths)==1,paths
    asset=paths.pop();digest=hashlib.sha256(get(asset)).hexdigest()
    value={**old,'sourceRevisionCompared':revision,'publicAsset':asset,'sha256':digest,'matchesBeforeAsset':digest==old['sha256'],'productionWrites':0}
    before=get('https://8898e76f.study-ez-open.pages.dev'+old['publicAsset'])
    assert hashlib.sha256(before).hexdigest()==old['sha256'],'Changed immutable baseline'
    current=get(asset)
    # Vite rewrites dependency file hashes after unrelated reviewPrompt changes.
    # Strip only the eight-character hashes in quoted relative JS import paths.
    normalize=lambda b:re.sub(r'"\./([^"/]+)-[A-Za-z0-9_-]{8}\.js"',r'"./\1-<build>.js"',b.decode())
    value['compiledUiEqualExceptDependencyFilenames']=normalize(before)==normalize(current)
    assert value['compiledUiEqualExceptDependencyFilenames'],'Actual Main Quiz compiled code changed'
    (OUT/'deployed-ui-after.json').write_text(json.dumps(value,indent=2),encoding='utf-8');print(json.dumps(value))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True);a=p.parse_args();main(a.revision)
