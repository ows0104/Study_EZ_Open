"""Upload only verified jokbo assets; preserve lectures and all other asset records."""
from pathlib import Path
import hashlib, json, os, sys
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'server'));os.chdir(ROOT/'server')
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Asset,Lecture,QuizBank
from app.storage import ObjectStorage
from runner.transport import Client, Upload, DEFAULT_API_BASE, _put_with_retry, lecture_path
from app.config import get_settings

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def inventory(subject):
    with SessionLocal() as db:
        lectures=[{k:str(getattr(l,k)) if k=='date' else getattr(l,k) for k in
                  ('run_id','uid','title','date','slot','slot_end','start_time','professors','author','version','timetable_event_id')}
                  for l in db.scalars(select(Lecture).where(Lecture.subject==subject))]
        assets=[{k:getattr(a,k) for k in ('id','run_id','kind','filename','object_key','size_bytes','content_type')}
                for a in db.scalars(select(Asset).where(Asset.subject==subject))]
        banks=[{'run_id':b.run_id,'build_id':b.build_id} for b in db.scalars(select(QuizBank).where(QuizBank.subject==subject))]
    return {'lectures':lectures,'assets':assets,'banks':banks}

def digest_remote(storage,key):
    response=storage.client.get_object(Bucket=storage.bucket,Key=key)
    body=response['Body'];digest=hashlib.sha256()
    try:
        for chunk in body.iter_chunks(1024*1024):digest.update(chunk)
    finally:body.close()
    return digest.hexdigest()

def main():
    plan=read(HERE/'upload-plan.json');before=read(HERE/'remote-before.json');check=read(HERE/'materials-verification.json')
    assert check['status']=='passed' and check['plan_sha256']==sha(HERE/'upload-plan.json')
    visual=read(HERE/'visual-review.json');assert visual['status']=='passed' and visual['plan_sha256']==check['plan_sha256']
    for meta in plan['files'].values():assert sha(meta['path'])==meta['sha256']
    for path,digest in plan['inputs'].items():assert sha(path)==digest
    live=inventory(plan['subject'])
    sort=lambda rows:sorted(rows,key=lambda r:(r.get('run_id',''),r.get('kind','')))
    assert sort(live['lectures'])==sort(before['lectures']) and sort(live['banks'])==sort(before['banks'])
    fields=('id','run_id','kind','filename','object_key','size_bytes','content_type')
    stripped=[{k:a[k] for k in fields} for a in before['assets']]
    assert sort(live['assets'])==sort(stripped), 'Assets changed since the snapshot; inspect before publishing'
    storage=ObjectStorage()
    old=[a for a in before['assets'] if a['kind']=='jokbo']
    for i,a in enumerate(old,1):
        assert sha(a['preserved_local_path'])==a['sha256']==digest_remote(storage,a['object_key'])
        print('ARCHIVE VERIFIED',i,len(old),flush=True)
    client=Client(DEFAULT_API_BASE,get_settings().runner_token,timeout=180)
    completed=[]
    for row in plan['lectures']:
        upload=Upload('jokbo',Path(row['path']));payload=[upload.payload()]
        base=lecture_path(plan['subject'],row['run_id'])
        signed=client.call('POST',base+'/uploads',payload)
        _put_with_retry(client,signed['files'][0]['uploadUrl'],upload)
        result=client.call('POST',base+'/uploads/complete',payload)
        assert not result.get('missing'),row['run_id']
        completed.append(row['run_id'])
        save(HERE/'upload-result.json',{'completed':completed,'total':len(plan['lectures']),'plan_sha256':check['plan_sha256']})
        print('UPLOADED',len(completed),len(plan['lectures']),row['run_id'],flush=True)
    after=inventory(plan['subject']);assert sort(after['lectures'])==sort(before['lectures']) and sort(after['banks'])==sort(before['banks'])
    assert sort([a for a in after['assets'] if a['kind']!='jokbo'])==sort([a for a in stripped if a['kind']!='jokbo'])
    exams={a['run_id']:a for a in after['assets'] if a['kind']=='jokbo'}
    assert set(exams)=={r['run_id'] for r in plan['lectures']}
    verified=[]
    for i,row in enumerate(plan['lectures'],1):
        a=exams[row['run_id']];meta=plan['files'][row['file_key']];path=Path(row['path'])
        assert a['filename']==path.name and a['size_bytes']==path.stat().st_size and a['content_type']=='application/pdf'
        assert digest_remote(storage,a['object_key'])==meta['sha256']
        verified.append({'run_id':row['run_id'],'filename':path.name,'sha256':meta['sha256']})
        print('REMOTE VERIFIED',i,len(plan['lectures']),flush=True)
    save(HERE/'upload-verification.json',{'status':'passed','lecture_attachments':len(verified),'files':verified,
         'other_assets_unchanged':len([a for a in stripped if a['kind']!='jokbo']),'lectures_unchanged':True,
         'banks_unchanged':True,'previous_pdf_archives':len(old),'plan_sha256':check['plan_sha256']})

if __name__=='__main__':main()
