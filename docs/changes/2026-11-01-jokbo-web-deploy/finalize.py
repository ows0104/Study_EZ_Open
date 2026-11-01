"""Preserve deployment evidence in the shared record without changing live data."""
from pathlib import Path
import json,shutil,sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
ISO=ROOT/'output/releases/jokbo-web-deploy';record=ISO/'docs/changes'/HERE.name
state=json.loads((record/'state.json').read_text(encoding='utf-8'))
deploy=state['deployments'][-1]
assert deploy['status']=='succeeded' and deploy['postchecks'][-1]['passed']
assert deploy['revision']=='0ca1ec7b-bdc2-4775-8916-4b1dca98563d'
shutil.copyfile(HERE/'post-deploy.md',record/'post-deploy.md')
state['verification_root']=str(ISO)
(record/'state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
shutil.copytree(record,HERE,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
logs=ISO/'runs/_development'/HERE.name
shared=ROOT/'runs/_development'/HERE.name
shutil.copytree(logs,shared,dirs_exist_ok=True)
sys.path.insert(0,str(ROOT/'scripts'));import development as d
old,_=d.load('2026-11-01-jokbo-professor-priority')
def supersede(s):
    prior=s.get('web_deployment_decision')
    if prior:s.setdefault('web_deployment_decision_history',[]).append(prior)
    s['web_deployment_decision']={'at':d.now(),'status':'deployed_under_followup_approval',
        'evidence':'현재 사용자: 오케이 그럼 웹배포도 해줘. 앞선 보류 해제.',
        'change':HERE.name,'revision':deploy['revision'],'web_deployed':True}
d.update(old,supersede)
print(json.dumps({'status':'deployed_and_verified','revision':deploy['revision'],
                  'health':deploy['postchecks'][-1]['health']['status'],'smoke_exit_code':deploy['postchecks'][-1]['smoke_exit_code'],
                  'verification_root':str(ISO)},ensure_ascii=False))
