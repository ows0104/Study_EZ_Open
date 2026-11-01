"""Read-only public HTTP/auth boundary checks; logged-in UI is checked separately."""
import argparse, json, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--revision',default='predeploy'); a=p.parse_args()
api='https://studyez-api-97999573571.asia-northeast3.run.app'
def get(url,headers=None):
    with tempfile.TemporaryDirectory(prefix='studyez-http-') as tmp:
        header=Path(tmp)/'headers.txt'
        args=['curl.exe','-sS','--max-time','40','--retry','2','-D',str(header),'-w','\n%{http_code}',url]
        for key,value in (headers or {}).items(): args.extend(['-H',key+': '+value])
        result=subprocess.run(args,capture_output=True,check=True)
        body,code=result.stdout.rsplit(b'\n',1)
        fields={line.split(':',1)[0].lower():line.split(':',1)[1].strip()
                for line in header.read_text().splitlines() if ':' in line}
        return int(code),body,fields
checks={}
code,body,headers=get(api+'/api/health',{'Origin':'https://studyez.kr'})
checks['health']=code==200 and json.loads(body).get('status')=='ok'
checks['cors']=headers.get('access-control-allow-origin')=='https://studyez.kr'
for path in ('/api/timetable','/api/spotter/db'):
    checks['anonymous_denied:'+path]=get(api+path)[0]==401
    checks['invalid_token_denied:'+path]=get(api+path,{'Authorization':'Bearer release-invalid-token'})[0]==401
for url in ('https://studyez.kr','https://study-ez-open.pages.dev'):
    code,body,_=get(url)
    checks['web:'+url]=code==200 and b'<script' in body.lower() and b'<html' in body.lower()
print(json.dumps({'revision':a.revision,'checks':checks,'authenticated_ui':'separate browser evidence'},ensure_ascii=False))
raise SystemExit(0 if all(checks.values()) else 1)
