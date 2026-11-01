"""Shared import authorization, stale-input protection, publication and queue safety."""
import os,tempfile,hashlib,datetime
from pathlib import Path
tmp=Path(tempfile.mkdtemp(prefix='shared-response-'))
os.environ.update(ENVIRONMENT='local-test',DATABASE_URL=f'sqlite:///{(tmp/"db.sqlite").as_posix()}',RUNNER_TOKEN='runner-token',STUDYEZ_LOCAL_STORAGE_DIR=str(tmp/'storage'))
from fastapi.testclient import TestClient
from app.database import Base,SessionLocal,engine
from app.main import app
from app.models import Lecture,QuizBank,PrequizJob


def main():
 Base.metadata.create_all(engine)
 with SessionLocal() as db:
  db.add(Lecture(subject='약리학',run_id='260929_03',uid='pk2',date=datetime.date(2026,9,29),slot=3,slot_end=3,start_time='11:00',title='약동학2'))
  db.commit()
  db.add(QuizBank(subject='약리학',run_id='260929_03',raw_response='old',status='ready',open_to_students=True,bank={'preserved':True},share_url='https://chatgpt.com/share/source'))
  db.commit()
 c=TestClient(app);base='/api/admin/lectures/약리학/260929_03'
 headers={'Authorization':'Bearer runner-token'}
 assert c.get(base+'/bank/shared-source').status_code==401
 source=c.get(base+'/bank/shared-source',headers=headers).json()
 raw='### Q001\n'+'문항 본문 '*60+'\nSTUDYEZ_BANK_COMPLETE'
 payload={'raw':raw,'shareUrl':source['shareUrl'],'expectedRespondedAt':source['respondedAt'],'expectedRawHash':hashlib.sha256(b'old').hexdigest(),'extractionStrategy':'fixture'}
 bad={**payload,'expectedRawHash':'0'*64}
 assert c.put(base+'/bank-shared-response',json=bad,headers=headers).status_code==409
 assert c.put(base+'/bank-shared-response',json={**payload,'raw':raw.replace('STUDYEZ_BANK_COMPLETE','')},headers=headers).status_code==422
 assert c.put(base+'/bank-shared-response',json={**payload,'shareUrl':'https://chatgpt.com/share/other'},headers=headers).status_code==409
 saved=c.put(base+'/bank-shared-response',json=payload,headers=headers)
 assert saved.status_code==200,saved.text
 with SessionLocal() as db:
  row=db.get(QuizBank,('약리학','260929_03'))
  assert row.bank=={'preserved':True} and row.open_to_students and row.raw_response==raw
  assert row.prompt_version=='' and row.conversation_url==''
  assert db.query(PrequizJob).count()==1
 assert c.put(base+'/bank-shared-response',json=payload,headers=headers).status_code==409
 fresh=c.get(base+'/bank/shared-source',headers=headers).json()
 same={**payload,'expectedRespondedAt':fresh['respondedAt'],'expectedRawHash':hashlib.sha256(raw.encode()).hexdigest()}
 assert c.put(base+'/bank-shared-response',json=same,headers=headers).json()['reused']
 with SessionLocal() as db: assert db.query(PrequizJob).count()==1
 # A newly saved public link queues recovery even without a browser response body.
 admin={'Authorization':'Bearer local-test-token'}
 link={'shareUrl':'https://chatgpt.com/share/new-source'}
 assert c.put(base+'/bank/links',json=link,headers=admin).status_code==200
 with SessionLocal() as db:
  assert db.query(PrequizJob).count()==1
  row=db.get(QuizBank,('약리학','260929_03'))
  linked=row.linked_at
 assert c.get(base+'/bank/shared-source',headers=headers).json()['importShare']
 fresh=c.get(base+'/bank/shared-source',headers=headers).json()
 same.update(shareUrl=fresh['shareUrl'],expectedRespondedAt=fresh['respondedAt'])
 assert c.put(base+'/bank-shared-response',json=same,headers=headers).json()['reused']
 assert not c.get(base+'/bank/shared-source',headers=headers).json()['importShare']
 with SessionLocal() as db:
  assert db.get(QuizBank,('약리학','260929_03')).linked_at==linked
  db.query(PrequizJob).update({'state':'done'})
  db.commit()
 assert c.put(base+'/bank/links',json=link,headers=admin).status_code==200
 with SessionLocal() as db: assert db.query(PrequizJob).count()==1
 assert c.put(base+'/bank/links',json={'shareUrl':'https://chatgpt.com/share/third-source'},headers=admin).status_code==200
 with SessionLocal() as db:
  assert db.query(PrequizJob).count()==2
  db.query(PrequizJob).filter_by(state='queued').update({'state':'running'})
  db.commit()
 assert c.put(base+'/bank/links',json={'shareUrl':'https://chatgpt.com/share/fourth-source'},headers=admin).status_code==409
 # Manual provenance survives identical resaves, later links and stale collectors.
 assert c.put(base+'/bank-response',json={'raw':raw,'source':'manual'},headers=admin).status_code==200
 manual=c.get(base+'/bank/shared-source',headers=headers).json()
 assert manual['responseSource']=='manual' and not manual['importShare']
 assert c.put(base+'/bank/links',json={'shareUrl':'https://chatgpt.com/share/fourth-source'},headers=admin).status_code==200
 with SessionLocal() as db: assert db.query(PrequizJob).count()==2
 assert c.put(base+'/bank-response',json={'raw':raw+'\nnew\nSTUDYEZ_BANK_COMPLETE'},headers=admin).status_code==409
 blocked={**same,'shareUrl':'https://chatgpt.com/share/fourth-source'}
 assert c.put(base+'/bank-shared-response',json=blocked,headers=headers).status_code==409
 with SessionLocal() as db:
  row=db.get(QuizBank,('약리학','260929_03'))
  assert row.raw_response==raw and row.responded_by.startswith('manual:') and row.bank=={'preserved':True}
 print('PASS: authentication, incomplete source, stale source, wrong link, preservation, queue, idempotency')


if __name__=='__main__': main()
