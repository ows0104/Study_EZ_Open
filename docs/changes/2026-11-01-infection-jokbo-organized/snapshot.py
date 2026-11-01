"""Read-only production inventory, with a verified local archive for every old exam."""
from pathlib import Path
import hashlib,json,os,sys
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
os.chdir(ROOT/'server');sys.path.insert(0,str(ROOT/'server'))
from sqlalchemy import select
from app.database import SessionLocal
from app.models import Asset,Lecture,QuizBank
from app.config import get_settings

def main():
    assert get_settings().environment=='production'
    old=json.loads((HERE.parent/'2026-11-01-infection-jokbo-2026/upload-plan.json').read_text(encoding='utf-8'))
    expected={r['run_id']:r for r in old['lectures']}
    with SessionLocal() as db:
        ls=db.scalars(select(Lecture).where(Lecture.subject=='감염과 면역')).all()
        assets=db.scalars(select(Asset).where(Asset.subject=='감염과 면역')).all()
        banks=db.scalars(select(QuizBank.run_id).where(QuizBank.subject=='감염과 면역')).all()
        lectures=[{k:(str(getattr(l,k)) if k=='date' else getattr(l,k)) for k in
            ('run_id','uid','title','date','slot','slot_end','start_time','professors','author','version','timetable_event_id')} for l in ls]
        rows=[{k:getattr(a,k) for k in ('id','run_id','kind','object_key','filename','size_bytes','content_type')} for a in assets]
    archive=[]
    for row in rows:
        if row['kind']!='jokbo':continue
        item=expected[row['run_id']];path=Path(item['path']);sha=hashlib.sha256(path.read_bytes()).hexdigest()
        assert sha==old['files'][item['section']]['sha256'] and path.name==row['filename']
        assert path.stat().st_size==row['size_bytes']
        archive.append({**row,'preserved_local_path':str(path),'sha256':sha})
    assert len(archive)==80 and len(lectures)==80
    assert sum(r['kind']=='notes_prev' for r in rows)==71
    result={'environment':'production','lectures':lectures,'assets':rows,'quiz_bank_ids':banks,'quiz_banks':len(banks)}
    for name,value in [('remote-before.json',result),('previous-jokbo-archive.json',archive)]:
        target=HERE/name
        assert not target.exists(),'Do not overwrite the pre-replacement snapshot.'
        target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Snapshot preserved: 80 lectures, 71 notes, 80 previous exam assets and',len(banks),'quiz banks.')

if __name__=='__main__':main()
