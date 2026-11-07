"""Retry one failed, exact-SHA Pages build only after matching API readiness."""
import argparse,json,tomllib,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'runs/_replacement/261104_02-v1'
API='https://studyez-api-97999573571.asia-northeast3.run.app'
BASE='https://api.cloudflare.com/client/v4/accounts/d0ec59549fea0c13f1b7fe9f724df93b/pages/projects/study-ez-open/deployments/'
def call(url,headers=None,method='GET'):
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers or{},method=method),timeout=45)as r:return json.load(r)
def short(v):return {'id':v['id'],'sha':v['deployment_trigger']['metadata']['commit_hash'],'stage':v['latest_stage'],'url':v['url']}
def main(sha,did):
    assert not(OUT/'pages-retry.json').exists(),'Explicit retry already recorded'
    health=call(API+'/api/health');assert health.get('revision')==sha and health.get('environment')=='production'
    cfg=tomllib.loads((Path.home()/'AppData/Roaming/xdg.config/.wrangler/config/default.toml').read_text())
    headers={'Authorization':'Bearer '+cfg['oauth_token']}
    old=call(BASE+did,headers);assert old['success'];before=short(old['result'])
    assert before['sha']==sha and before['stage']['status']=='failure','Only exact failed build may be retried'
    response=call(BASE+did+'/retry',headers,'POST');assert response['success']
    after=short(response['result']);assert after['sha']==sha
    value={'sameShaOnly':True,'apiRevision':sha,'before':before,'after':after,'reason':'Original web build timed out while exact API revision was awaiting full CI. Retry after API readiness; no code/settings change.'}
    (OUT/'pages-retry.json').write_text(json.dumps(value,indent=2),encoding='utf8');print(json.dumps(value))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sha',required=True);p.add_argument('--id',required=True);a=p.parse_args();main(a.sha,a.id)
