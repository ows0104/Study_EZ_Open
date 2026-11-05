"""Fetch public primary references only; sends no lecture or user data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC,datetime
from html.parser import HTMLParser
from pathlib import Path
import hashlib,json,re,sys,urllib.request
import fitz

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'runs/_examples/cholinergic-findings-20261104/references'
REFERENCES=[
 ('E01','Galantamine IR official label','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=261889d3-41c8-4655-98f7-41317778e7a1'),
 ('E02','Ambenonium MYTELASE manufacturer prescribing information','https://products.sanofi.us/mytelase/mytelase.html'),
 ('E03','Echothiophate PHOSPHOLINE IODIDE official label','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=8afc8951-db76-4f27-8752-7c0d6aa47244'),
 ('E04','Physostigmine injection official label','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=9a448a78-356c-50f7-e053-2995a90adefa'),
 ('E05','Donepezil including23mg official label','https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=caebc31c-5a35-4434-b7e2-80f6405383ca'),
 ('E06','Rivastigmine capsule official label','https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=c246a0e5-1e77-41ee-a7b3-384f21f2f2e0'),
 ('E07','Pilocarpine ophthalmic official label','https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=84428e9a-f486-44d9-ad93-4ea9069a6787'),
 ('E08','Cevimeline official label','https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=ca0409bc-2685-4ffd-b806-04898902a597'),
 ('E09','Comparative tolerability retrospective118patients2014 primary research','https://pubmed.ncbi.nlm.nih.gov/25065774/'),
 ('E10','Comparative hyposalivation retrospective110patients2019 primary research','https://pubmed.ncbi.nlm.nih.gov/31520497/'),
 ('E11','Malathion human hepatic carboxylesterases primary experiment','https://pubmed.ncbi.nlm.nih.gov/16421896/'),
 ('E12','ACh endothelium dependent relaxation original1980 experiment','https://pubmed.ncbi.nlm.nih.gov/6253831/'),
 ('E13','Asoxime chloride official chemical identity/synonyms','https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/135444627/synonyms/JSON'),
 ('E14','Pralidoxime official chemical identity/synonyms','https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/135398747/synonyms/JSON'),
 ('E15','AHA2025 adult bradycardia algorithm official','https://cpr.heart.org/-/media/CPR-Files/CPR-Guidelines-Files/2025-Accessible/Algorithm-ACLS-Bradycardia-LngDscrp-250725-Ed.pdf'),
 ('E16','Cognex tacrine archived manufacturer prescribing information','https://media.corporate-ir.net/media_files/irol/12/120763/downloads/Cognex2.pdf'),
]
class Text(HTMLParser):
 def __init__(self):super().__init__();self.skip=0;self.parts=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','noscript'):self.skip+=1
  if tag in ('p','div','section','h1','h2','h3','h4','tr','li','br'):self.parts.append('\n')
 def handle_endtag(self,tag):
  if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
  if tag in ('p','div','tr','li'):self.parts.append('\n')
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
def fetch(row):
 id,title,url=row
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'StudyEZ-example-reference-check/1.0'})
  with urllib.request.urlopen(request,timeout=60) as response:
   raw=response.read();final=response.url;ctype=response.headers.get_content_type()
  suffix='.pdf' if raw.startswith(b'%PDF') else '.json' if 'json' in ctype else '.html'
  (OUT/(id+suffix)).write_bytes(raw)
  if suffix=='.pdf':
   with fitz.open(stream=raw,filetype='pdf') as pdf:text='\n'.join(f'Page{i+1}\n'+p.get_text() for i,p in enumerate(pdf))
  elif suffix=='.json':text=json.dumps(json.loads(raw),ensure_ascii=False,indent=2)
  else:
   parser=Text();parser.feed(raw.decode('utf-8',errors='replace'));text='\n'.join(re.sub(r'\s+',' ',p).strip() for p in ''.join(parser.parts).splitlines() if p.strip())
  if len(text)<200:raise ValueError('Insufficient reference body')
  text=f'{id}: {title}\nURL: {url}\nFetched final URL: {final}\nEXTERNAL PRIMARY REFERENCE; NOT LECTURE/EXAM SCOPE EVIDENCE.\n\n'+text
  body=text.encode('utf-8');(OUT/(id+'.txt')).write_bytes(body)
  return {'id':id,'title':title,'url':url,'finalUrl':final,'fetchedAt':datetime.now(UTC).isoformat(),
    'rawFile':id+suffix,'rawSha256':hashlib.sha256(raw).hexdigest(),'textFile':id+'.txt','textSha256':hashlib.sha256(body).hexdigest(),'characters':len(text)}
 except Exception as e:return {'id':id,'title':title,'url':url,'error':str(e)}
if __name__=='__main__':
 OUT.mkdir(exist_ok=False)
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(fetch,REFERENCES))
 good=[r for r in results if 'error' not in r];failed=[r for r in results if 'error' in r]
 (OUT/'manifest.json').write_text(json.dumps({'schema_version':'primary-reference-pack/1','purpose':'clinical-verification-only',
  'references':good,'failed':failed,'fetcherSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'downloaded':len(good),'failed':failed,'totalCharacters':sum(r['characters'] for r in good)},ensure_ascii=False))
 if failed:sys.exit(2)
