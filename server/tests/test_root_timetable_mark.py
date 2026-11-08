"""시간표가 검토·공개된 Main-Quiz(뿌리 학습)를 강의마다 `marks.mainQuiz`로 알린다.

Quiz Bank가 없고 Main-Quiz만 있는 강의(감염병리1)는 캘린더 칸과 강의 목록에서
「퀴즈 없음」으로 그려졌다. `marks.quiz`(Quiz Bank)는 그대로 두고 따로 센다.
"""
import os
from datetime import date
from tests.root_support import setup, publish, ADMIN

client, user, SessionLocal = setup()
from app.models import Lecture, TimetableEvent

with SessionLocal() as db:
    db.add(TimetableEvent(id='event', date=date(2026, 11, 3), start_time='09:00', end_time='10:00',
                          title='Synthetic', category='lecture', course='test'))
    db.get(Lecture, ('test', 'demo')).timetable_event_id = 'event'
    db.add(Lecture(subject='test', run_id='other', uid='root-other', date=date(2026, 11, 3), slot=1, slot_end=1,
                   start_time='09:00', title='No main quiz', professors=[], author='', version=1, timetable_event_id='event'))
    db.commit()


def marks(include_study=True):
    response = client.get('/api/timetable', params={'include_study': str(include_study).lower()})
    assert response.status_code == 200, response.text
    lectures = {l['runId']: l['marks'] for e in response.json()['events'] for l in e['lectures']}
    return {run: (m['mainQuiz'], m['quiz']) for run, m in lectures.items()}


user('a')
assert marks() == {'demo': (False, False), 'other': (False, False)}
user('admin', True)
assert client.post(ADMIN, json=__import__('tests.root_support', fromlist=['document']).document()).status_code == 200
# 등록만 하고 공개하지 않았으면 아직 없다.
user('a')
assert marks()['demo'] == (False, False)
publish(client, user)
assert marks() == {'demo': (True, False), 'other': (False, False)}
assert marks(include_study=False)['demo'] == (True, False)

user('admin', True)
assert client.put(ADMIN + '/publication', json={'revision': 'v1', 'reviewed': True, 'enabled': True,
                                                'allowedUsers': ['a']}).status_code == 200
user('b')
assert marks()['demo'] == (False, False)
user('a')
assert marks()['demo'] == (True, False)
user('admin', True)
assert marks()['demo'] == (True, False)

os.environ['STUDYEZ_ROOT_LEARNING_ENABLED'] = 'false'
user('a')
assert marks()['demo'] == (False, False)
os.environ['STUDYEZ_ROOT_LEARNING_ENABLED'] = 'true'

user('admin', True)
assert client.put(ADMIN + '/publication', json={'revision': 'v1', 'reviewed': True, 'enabled': False}).status_code == 200
user('a')
assert marks()['demo'] == (False, False)
print('PASS: timetable marks published Main-Quiz per account, flag and stop; Quiz Bank mark untouched')
