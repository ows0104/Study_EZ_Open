"""Actual reviewed content in an isolated app; technical learner only."""
import argparse
import json
import os
import sys
from datetime import date,datetime,UTC
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'server'));sys.path.insert(0,str(ROOT))
OUT=ROOT/'runs/_final-plan/261104_02'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
packet=read(OUT/'packet.json');result=read(OUT/'result.json');checked=read(OUT/'checked-for-publication.json')
assert checked['verified']
from tests.root_support import setup
client,user,SessionLocal=setup()
from app.main import app
from app.models import Lecture,Profile
from app.storage import ObjectStorage
from app.root_learning import reviewed_import
from app.routes import root_learning
from studyez_contracts.roots import document_hash
import uvicorn
root_learning.now=lambda:datetime.now(UTC)
with SessionLocal()as db:
    db.add(Lecture(subject=packet['subject'],run_id=packet['runId'],uid='technical-pathology-review',date=date(2026,11,4),
        slot=2,slot_end=2,start_time='10:00',title=packet['title'],professors=['김지은'],author='박준원',version=2))
    db.add(Profile(id='local-pilot',email='local-pilot@example.invalid',is_admin=True));db.commit()
    snapshots=[]
    for s in packet['sources']:
        key='lectures/root-reviewed-import/'+s['sha256']+'/'+s['id'];ObjectStorage().put_bytes(key,Path(s['localPath']).read_bytes())
        snapshots.append({**{k:v for k,v in s.items()if k not in('localPath','downloadUrl','snapshotKey')},'snapshotKey':key})
    registered=reviewed_import.register(db,packet,result,snapshots,expected_control_hash=document_hash(None))
user('local-pilot',True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,required=True);a=p.parse_args()
    (OUT/'local-review.json').write_text(json.dumps({'api':'http://127.0.0.1:'+str(a.port),'technicalUser':'local-pilot',
        'database':os.environ['DATABASE_URL'],'registration':registered,'productionWrites':0},ensure_ascii=False,indent=2),encoding='utf-8')
    uvicorn.run(app,host='127.0.0.1',port=a.port,log_level='warning')
