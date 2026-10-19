"""KST cutoff, source identity, independent upload state, and lightweight refresh."""
import os,tempfile
from pathlib import Path
from datetime import date,datetime,UTC
tmp=Path(tempfile.mkdtemp(prefix='publication-'))
os.environ.update(ENVIRONMENT='local-test',DATABASE_URL=f'sqlite:///{(tmp/"db.sqlite").as_posix()}',RUNNER_TOKEN='runner-token',STUDYEZ_LOCAL_STORAGE_DIR=str(tmp/'storage'))
from fastapi.testclient import TestClient
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user
from app.database import Base,SessionLocal,engine
from app.main import app
from app.models import Lecture,QuizBank
from app.models.quiz_publication import QuizPublicationCheck
from app.routes.quiz_publication import CUTOFF


def main():
 Base.metadata.create_all(engine)
 with SessionLocal() as db:
  for i in range(3):
   db.add(Lecture(subject='약리학',run_id=str(i),uid=f'p{i}',date=date(2026,10,16),slot=i+1,slot_end=i+1,start_time='09:00',title=f'강의{i}'))
  db.commit()
  db.add(QuizBank(subject='약리학',run_id='0',share_url='https://chatgpt.com/share/first',status='failed',bank={'questions':[{'id':'one'}]},built_at=CUTOFF,responded_at=datetime(2026,10,16,tzinfo=UTC),open_to_students=True))
  db.commit()
 c=TestClient(app);read='/api/timetable/quiz-publication';write='/api/admin/quiz-publication/check'
 admin={'Authorization':'Bearer local-test-token'};runner={'Authorization':'Bearer runner-token'}
 assert c.get(read).status_code==401
 assert c.get('/api/admin/quiz-publication/sources',headers=runner).status_code==200
 assert c.put(write,json={},headers=admin).status_code!=200
 def first():return c.get(read,headers=admin).json()['lectures'][0]
 assert first()['link']['state']=='unchecked'
 assert first()['upload']['sinceCutoff'] and not first()['upload']['current']
 payload={'runId':'0','shareUrl':'https://chatgpt.com/share/first','state':'complete','completedAt':CUTOFF.isoformat(),'questionCount':12,'rawHash':'a'*64}
 assert c.put(write,json={**payload,'questionCount':0},headers=runner).status_code==422
 assert c.put(write,json={**payload,'shareUrl':'https://chatgpt.com/share/stale'},headers=runner).status_code==409
 assert c.put(write,json=payload,headers=runner).status_code==200
 assert first()['link']['sinceCutoff'] and first()['link']['questionCount']==12
 old={**payload,'completedAt':'2026-10-14T14:59:59+00:00'}
 assert c.put(write,json=old,headers=runner).status_code==200
 assert first()['link']['state']=='complete' and not first()['link']['sinceCutoff']
 with SessionLocal() as db:
  row=db.get(QuizBank,('약리학','0'));row.share_url='https://chatgpt.com/share/new';row.built_at=datetime(2026,10,16,1,tzinfo=UTC);row.status='ready';db.commit()
 assert first()['link']['state']=='unchecked' and first()['upload']['current']
 assert c.put(write,json=payload,headers=runner).status_code==409
 assert c.put(write,json={**payload,'shareUrl':'https://chatgpt.com/share/new','state':'wrong_lecture','completedAt':None,'questionCount':0,'rawHash':None},headers=runner).status_code==200
 assert first()['link']['state']=='wrong_lecture' and not first()['link']['sinceCutoff']
 rows=c.get(read,headers=admin).json()['lectures'];assert len(rows)==3 and rows[1]['link']['state']=='missing' and not rows[1]['upload']['sinceCutoff']
 # Rebuilding a bank cannot destroy its independent public-share verification.
 with SessionLocal() as db:
  db.get(QuizBank,('약리학','0')).validation={'ok':True};db.commit()
 assert first()['link']['state']=='wrong_lecture'
 with SessionLocal() as db:
  row=db.get(QuizBank,('약리학','0'));row.responded_by='manual:admin';row.raw_response='### Q001 | recall\n'+('answer '*50)+'\nSTUDYEZ_BANK_COMPLETE';db.commit()
 saved=first()
 assert saved['responseSource']=='manual' and saved['link']['state']=='complete' and saved['link']['sinceCutoff']
 assert saved['link']['questionCount']==1 and saved['upload']['current']
 assert saved['link']['completedAt']==datetime(2026,10,16,tzinfo=UTC).isoformat()
 assert 'raw' not in str(saved) and 'manual:admin' not in str(saved)
 assert 'raw' not in str(rows) and 'conversationUrl' not in str(rows)
 assert first()['shareUrl']=='https://chatgpt.com/share/new'
 app.dependency_overrides[get_current_user]=lambda: CurrentUser(
  id='student',email='s@example.com',is_admin=False,apps=dict.fromkeys(APP_POLICY,ROLE_ADMIN))
 student=c.get(read).json()['lectures']
 assert len(student)==3 and all('shareUrl' not in row for row in student)
 assert student[0]['upload']==saved['upload'] and student[0]['link']==saved['link']
 assert c.get('/api/admin/quiz-publication/sources').status_code==401
 app.dependency_overrides.clear()
 assert c.get('/api/admin/quiz-publication/sources',headers=runner).json()['lectures'][0]['shareUrl']=='https://chatgpt.com/share/new'
 print('PASS: KST boundary, stale-link rejection, independent upload state, missing lectures, retained verification')


if __name__=='__main__':main()
