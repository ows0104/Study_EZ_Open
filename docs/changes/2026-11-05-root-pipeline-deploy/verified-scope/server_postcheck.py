"""Read-only API checks and preservation of the existing enabled root feature."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--revision',required=True);a=p.parse_args()
r=subprocess.run(['gcloud.cmd','run','revisions','describe',a.revision,'--project','meddeck-503318','--region','asia-northeast3','--format=json'],capture_output=True,text=True,check=True)
env=json.loads(r.stdout)['spec']['containers'][0]['env']
assert any(e.get('name')=='STUDYEZ_ROOT_LEARNING_ENABLED'and e.get('value')=='true'for e in env),'Existing enabled feature flag missing'
subprocess.run([sys.executable,str(ROOT/'scripts/root_production_smoke.py'),'--revision',a.revision],check=True)
print(json.dumps({'revision':a.revision,'existingRootFeatureEnabled':True,'dataWrites':False}))
