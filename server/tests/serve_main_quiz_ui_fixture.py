"""Owned synthetic two-page PDF and isolated local study data only."""
import hashlib,os
from fastapi import Request
from tests.root_support import setup,publish,document
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import document_hash

def pdf_bytes():
    streams=[b'BT /F1 24 Tf 40 200 Td (PAGE ONE - NOT THE REFERENCE) Tj ET',
             b'0.1 0.3 0.7 rg 20 30 360 120 re f 0 0 0 rg BT /F1 24 Tf 40 220 Td (REFERENCE PAGE TWO) Tj ET']
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Count 2 /Kids [3 0 R 5 0 R] >>']
    for i,stream in enumerate(streams):
        objects.extend([f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 300] /Resources << /Font << /F1 7 0 R >> >> /Contents {4+i*2} 0 R >>'.encode(),
            b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream'])
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    body=b'%PDF-1.4\n';offsets=[0]
    for i,value in enumerate(objects,1):
        offsets.append(len(body));body+=f'{i} 0 obj\n'.encode()+value+b'\nendobj\n'
    xref=len(body);body+=f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    body+=b''.join(f'{offset:010d} 00000 n \n'.encode()for offset in offsets[1:])
    return body+f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()

client,user,SessionLocal=setup()
body=pdf_bytes();digest=hashlib.sha256(body).hexdigest();doc=document()
doc['review']['sources'][0].update(label='two-pages.pdf',sha256=digest,kind='notes',page_count=2)
for q in doc['bank_snapshot']['questions']:q['source_refs']=[{'source_id':'S1','locator':'p2'}]
doc['review']['bank_sha256']=document_hash(doc['bank_snapshot'])
for m,q in zip(doc['review']['mappings'],doc['bank_snapshot']['questions']):m['question_sha256']=question_hash(q,doc['bank_snapshot'])
publish(client,user,doc)
from app.main import app
from app.models.root_generation import RootGeneration
from app.storage import ObjectStorage
from app.auth import CurrentUser,get_current_user,APP_POLICY,ROLE_ADMIN
key='lectures/synthetic-ui/'+digest+'/two-pages.pdf';ObjectStorage().put_bytes(key,body)
with SessionLocal()as db:
    db.add(RootGeneration(id='e'*32,job_id=10001,subject='test',run_id='demo',user_id='fixture',request_id='fixture',
        input_digest=digest,baseline='0'*64,packet={'revision':doc['revision'],'sources':[
            {'id':'S1','sha256':digest,'filename':'two-pages.pdf','snapshotKey':key,'pageCount':2}]},
        result={'sourceAudit':{'question_checks':{'reviews':[]},'input_issues':[]},'medical':{'reviews':[]},
            'validation':{'errors':[],'warnings':[]}},result_digest='1'*64));db.commit()

def test_user(request:Request):
    uid=request.headers.get('X-Root-Test-User','a')
    return CurrentUser(id=uid,email=f'{uid}@example.com',is_admin=False,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
app.dependency_overrides[get_current_user]=test_user
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('MAIN_QUIZ_UI_PORT','8027')),log_level='warning')
