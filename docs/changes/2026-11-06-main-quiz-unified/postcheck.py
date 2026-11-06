"""Read-only same-SHA API/Pages/assets check; never writes learner or content data."""
import argparse,json,re,tomllib
from pathlib import Path
from datetime import datetime,UTC
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urljoin
p=argparse.ArgumentParser();p.add_argument('--sha');p.add_argument('--output',type=Path);a=p.parse_args()
def get(url,headers=None):
 with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Cache-Control':'no-cache',**(headers or {})}),timeout=30)as response:return response.read()
API='https://studyez-api-97999573571.asia-northeast3.run.app'
health=json.loads(get(API+'/api/health'))
config=tomllib.loads((Path.home()/'AppData/Roaming/xdg.config/.wrangler/config/default.toml').read_text(encoding='utf-8'))
cf=json.loads(get('https://api.cloudflare.com/client/v4/accounts/d0ec59549fea0c13f1b7fe9f724df93b/pages/projects/study-ez-open/deployments?env=production&per_page=1',{'Authorization':'Bearer '+config['oauth_token']}))['result'][0]
result={'at':datetime.now(UTC).isoformat(),'health':health,'pages':{k:cf.get(k)for k in ['id','url','environment','latest_stage']},'pagesSha':cf['deployment_trigger']['metadata']['commit_hash']}
if a.sha:
 assert health['status']=='ok' and health['environment']=='production' and health['revision']==a.sha, 'Expected API commit is not live'
 assert result['pagesSha']==a.sha and cf['latest_stage']['name']=='deploy' and cf['latest_stage']['status']=='success', 'Expected Pages commit is not published'
 try:get(API+'/api/main-quiz/lectures/test/demo/entry')
 except HTTPError as error:assert error.code==401;result['entryAnonymousStatus']=error.code
 else:raise AssertionError('Main Quiz entry must require authentication')
 base='https://study-ez-open.pages.dev/'
 html=get(base).decode();scripts=re.findall(r'<script[^>]+src="([^"]+)"',html)
 entry=next(urljoin(base,x)for x in scripts if '/assets/index-'in x)
 source=get(entry).decode()
 names=sorted(set(re.findall(r'(?:BankStudy|RootLearning|RootGenerationPanel|LectureMastery)-[\w-]+\.js',source)))
 assert names,'Expected Main Quiz modules were not linked'
 chunks={name:get(urljoin(entry,name)).decode()for name in names}
 required=['main-quiz/lectures','Main Quiz','내 답 적기','회상 자기평가','Main Quiz 추가 출제 지침']
 visited={entry};queue=[entry]+[urljoin(entry,n)for n in names]
 bodies={entry:source,**{urljoin(entry,k):v for k,v in chunks.items()}}
 while queue:
  current=queue.pop(0);body=bodies[current]
  combined='\n'.join(bodies.values())
  if all(text in combined for text in required):break
  for relative in re.findall(r'''(?:from|import)\s*["'](\./[^"']+\.js)["']''',body):
   target=urljoin(current,relative)
   if target in bodies:continue
   assert len(bodies)<60,'Unexpected module graph'
   bodies[target]=get(target).decode();queue.append(target)
 combined='\n'.join(bodies.values())
 for text in required:assert text in combined,text
 names=sorted(url.rsplit('/',1)[-1]for url in bodies)
 assert 'local-test-main'not in combined
 prompt=json.loads(get(urljoin(base,'bank-prompt.json')));assert prompt['version']=='1.82'
 result.update(assets=names,entryAsset=entry,promptVersion=prompt['version'],mainQuizChecks=True)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
