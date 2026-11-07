"""Read-only, exact-SHA deployment observations; no credential output."""
import argparse,json,subprocess,tomllib,urllib.request
from datetime import datetime,UTC
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'runs/_replacement/261104_02-v1'
API='https://studyez-api-97999573571.asia-northeast3.run.app'

def get(url,headers=None):
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers or{}),timeout=30)as r:return json.load(r)

def main(sha,run):
    value=json.loads(subprocess.run(['gh','run','view',run,'--repo','ows0104/Study_EZ_Open','--json','status,conclusion,jobs,headSha'],
        capture_output=True,text=True,encoding='utf-8',check=True).stdout)
    assert value['headSha']==sha
    jobs=[{'id':j['databaseId'],'name':j['name'],'status':j['status'],'conclusion':j['conclusion'],
        'active':[s['name']for s in j['steps']if s['status']=='in_progress']}for j in value['jobs']]
    cfg=tomllib.loads((Path.home()/'AppData/Roaming/xdg.config/.wrangler/config/default.toml').read_text())
    result=get('https://api.cloudflare.com/client/v4/accounts/d0ec59549fea0c13f1b7fe9f724df93b/pages/projects/study-ez-open/deployments?env=production&per_page=3',
        {'Authorization':'Bearer '+cfg['oauth_token']})
    assert result['success']
    pages=[{'id':p['id'],'url':p['url'],'environment':p['environment'],'stage':p['latest_stage'],
        'sha':p['deployment_trigger']['metadata']['commit_hash']}for p in result['result']]
    health=get(API+'/api/health')
    record={'at':datetime.now(UTC).isoformat(),'sha':sha,'run':run,'workflow':{'status':value['status'],'conclusion':value['conclusion'],'jobs':jobs},'pages':pages,'api':health}
    (OUT/'deployment-observed.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    with(OUT/'deployment-timeline.jsonl').open('a',encoding='utf-8')as f:f.write(json.dumps(record)+'\n')
    print(json.dumps({'workflow':record['workflow'],'pages':pages[0],'apiRevision':health.get('revision')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sha',required=True);p.add_argument('--run',required=True);a=p.parse_args();main(a.sha,a.run)
