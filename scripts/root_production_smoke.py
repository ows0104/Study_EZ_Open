"""Read-only deployed root routes and existing auth boundary checks."""
import argparse,json,subprocess,sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--revision',required=True);a=p.parse_args()
subprocess.run([sys.executable,str(ROOT/'scripts/production_smoke.py'),'--revision',a.revision],check=True)
api='https://studyez-api-97999573571.asia-northeast3.run.app'
def status(path,token=None):
    try:
        with urlopen(Request(api+path,headers={'Authorization':'Bearer '+token} if token else {}),timeout=40) as response:return response.status
    except HTTPError as error:return error.code
token=dotenv_values(ROOT/'server/.env').get('RUNNER_TOKEN');assert token
checks={'root_catalog_requires_login':status('/api/root-learning')==401,
        'root_admin_requires_login':status('/api/admin/root-learning/lectures/x/x/generation')==401,
        'runner_generation_route_and_table':status('/api/admin/root-generation/'+'0'*32+'/input',token)==404}
print(json.dumps({'revision':a.revision,'rootChecks':checks}))
raise SystemExit(0 if all(checks.values()) else 1)
