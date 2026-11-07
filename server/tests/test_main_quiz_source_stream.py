"""Reference PDFs reach PDF.js through the API (R2 has no CORS rule): read-only, exact snapshot, ranges."""
import hashlib
from tests.root_support import setup,publish,document,start,view,BASE,ADMIN
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash
client,user,SessionLocal=setup()
from app.models.root_generation import RootGeneration
from app.models.root_learning import RootEvent
from app.storage import ObjectStorage

body=b'%PDF-1.4\n'+bytes(range(256))*40+b'\n%%EOF\n';digest=hashlib.sha256(body).hexdigest();doc=document()
doc['review']['sources'][0].update(label='notes.pdf',sha256=digest,kind='notes',page_count=2)
for q in doc['bank_snapshot']['questions']:q['source_refs']=[{'source_id':'S1','locator':'p2'}]
doc['review']['bank_sha256']=document_hash(doc['bank_snapshot'])
for m,q in zip(doc['review']['mappings'],doc['bank_snapshot']['questions']):m['question_sha256']=question_hash(q,doc['bank_snapshot'])
publish(client,user,doc)
key='lectures/synthetic-stream/'+digest+'/notes.pdf';ObjectStorage().put_bytes(key,body)
with SessionLocal()as db:
    db.add(RootGeneration(id='f'*32,job_id=20001,subject='test',run_id='demo',user_id='fixture',request_id='fixture',
        input_digest=digest,baseline='0'*64,packet={'revision':doc['revision'],'sources':[
            {'id':'S1','sha256':digest,'filename':'notes.pdf','snapshotKey':key,'pageCount':2},
            {'id':'S2','sha256':'0'*64,'filename':'other.pdf','snapshotKey':key,'pageCount':2}]},
        result={'sourceAudit':{'question_checks':{'reviews':[]},'input_issues':[]},'medical':{'reviews':[]},
            'validation':{'errors':[],'warnings':[]}},result_digest='1'*64));db.commit()
    events_before=db.query(RootEvent).count()

# The revealed answer carries the API path next to the signed link.
sid=start(client)
client.post(f'/api/root-learning/sessions/{sid}/events',json={'requestId':'r1','version':view(client,sid)['version'],
    'kind':'reveal','attempted':False,'response':''})
slide=view(client,sid)['task']['answer']['pdfSlides'][0]
assert slide['page']==2 and slide['proxyPath']==BASE+f'/sources/S1?sha={digest}',slide
with SessionLocal()as db:events_before=db.query(RootEvent).count()

URL=BASE+'/sources/S1'
full=client.get(URL)
assert full.status_code==200 and full.content==body and full.headers['content-type']=='application/pdf'
assert full.headers['accept-ranges']=='bytes' and full.headers['content-length']==str(len(body))
part=client.get(URL,headers={'Range':'bytes=9-18'})
assert part.status_code==206 and part.content==body[9:19] and part.headers['content-range']==f'bytes 9-18/{len(body)}'
tail=client.get(URL,headers={'Range':'bytes=-7'})
assert tail.status_code==206 and tail.content==body[-7:]
open_end=client.get(URL,headers={'Range':f'bytes={len(body)-3}-'})
assert open_end.status_code==206 and open_end.content==body[-3:]
clipped=client.get(URL,headers={'Range':f'bytes=0-{len(body)*2}'})
assert clipped.status_code==206 and clipped.content==body
for bad in [f'bytes={len(body)}-',f'bytes=5-2','bytes=-','items=0-1','bytes=0-1,4-5']:
    r=client.get(URL,headers={'Range':bad});assert r.status_code==416 and r.headers['content-range']==f'bytes */{len(body)}',(bad,r.status_code)

# Unknown source, hash mismatch with the reviewed document, missing object: 404, never another file.
assert client.get(BASE+'/sources/S9').status_code==404
assert client.get(BASE+'/sources/S2').status_code==404
ObjectStorage().delete(key)
assert client.get(URL).status_code==404
ObjectStorage().put_bytes(key,body)

# Same audience as the study content: a pilot limited to another account hides the file.
user('admin',True)
r=client.put(ADMIN+'/publication',json={'revision':doc['revision'],'reviewed':True,'enabled':True,'allowedUsers':['someone']});assert r.status_code==200
user('a');assert client.get(URL).status_code==404
user('someone');assert client.get(URL).status_code==200
user('admin',True)
r=client.put(ADMIN+'/publication',json={'revision':doc['revision'],'reviewed':True,'enabled':False});assert r.status_code==200
user('someone');assert client.get(URL).status_code==404

with SessionLocal()as db:
    publications=db.query(RootEvent).filter(RootEvent.kind=='publication').count()
    assert db.query(RootEvent).count()==events_before+2 and publications>=3  # only the two publication changes above
print('PASS: API streams the exact reviewed PDF with byte ranges, 404 outside the audience/snapshot, no learning writes')
