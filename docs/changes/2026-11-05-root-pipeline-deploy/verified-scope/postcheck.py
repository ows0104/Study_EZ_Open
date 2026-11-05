"""Read-only exact deployed web bytes plus existing health/auth checks."""
import argparse,concurrent.futures,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def get(url):
    r=subprocess.run(['curl.exe','-sS','--max-time','40','--retry','2','-w','\n%{http_code}',url],capture_output=True,check=True)
    body,code=r.stdout.rsplit(b'\n',1)
    if code!=b'200':raise ValueError('Unexpected HTTP status '+code.decode())
    return body
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True);p.add_argument('--artifact',required=True,type=Path);a=p.parse_args()
    subprocess.run([sys.executable,str(ROOT/'scripts/root_production_smoke.py'),'--revision',a.revision],check=True)
    origins=['https://studyez.kr','https://study-ez-open.pages.dev',f'https://{a.revision[:8]}.study-ez-open.pages.dev']
    for origin in origins:
        for name in ('index.html','studyez-extension.zip'):
            path='/'if name=='index.html'else'/'+name
            assert get(origin+path+'?release='+a.revision)==(a.artifact/name).read_bytes(),(origin,name)
    assets=[p for p in(a.artifact/'assets').iterdir()if p.suffix in('.js','.css')]
    def compare(p):
        name=p.relative_to(a.artifact).as_posix();assert get('https://study-ez-open.pages.dev/'+name)==p.read_bytes(),name
        return name
    with concurrent.futures.ThreadPoolExecutor(max_workers=6)as pool:verified=list(pool.map(compare,assets))
    print(json.dumps({'revision':a.revision,'htmlAndZipExactOrigins':origins,'assetsExact':len(verified),'dataWrites':False}))
if __name__=='__main__':main()
