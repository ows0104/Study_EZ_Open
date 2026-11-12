"""오늘 추천의 시험일: 출제 때 문서에 시험일이 없어도 시간표의 현재 시험일을 쓴다. 문서는 바꾸지 않는다."""
from copy import deepcopy
from datetime import date
from tests.root_support import setup, publish, document, BASE
client, user, SessionLocal = setup()
doc = deepcopy(document()); doc['exam_date'] = None
publish(client, user, doc)
assert client.get(BASE).json()['plan']['deadline'] is None
from app.models import Lecture, TimetableEvent
with SessionLocal() as db:
    db.add(TimetableEvent(id='ev-lec', date=date(2026, 11, 3), start_time='09:00', end_time='09:50', title='Synthetic 1',
                          category='lecture', course='Synthetic', course_key='synthetic', slot=1))
    db.add(TimetableEvent(id='ev-exam', date=date(2026, 11, 20), start_time='09:00', end_time='11:00', title='Synthetic 시험',
                          category='exam', course='Synthetic', course_key='synthetic', slot=1))
    db.get(Lecture, ('test', 'demo')).timetable_event_id = 'ev-lec'
    db.commit()
plan = client.get(BASE).json()['plan']
assert plan['deadline'] is not None and plan['days'] is not None, plan
from app.models.root_learning import RootContent
with SessionLocal() as db:
    assert db.query(RootContent).one().document['exam_date'] is None
print('ok')
