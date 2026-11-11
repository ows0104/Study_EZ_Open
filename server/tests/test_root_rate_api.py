"""사이트의 학습률 출구가 모두 같은 Main-Quiz 학습률을 낸다(2026-11-11 spec R2).

시간표·강의 상세·study-progress·Main-Quiz 요약이 같은 강의에서 같은 숫자다. 사용자·공개 범위를 지킨다.
"""
from datetime import date, timedelta
from unittest.mock import patch

from tests.root_support import setup, publish, start, action, ADMIN, NOW
client, user, SessionLocal = setup()
from app.models import Lecture, TimetableEvent
from app.root_learning import content

with SessionLocal() as db:
    db.add(TimetableEvent(id='event', date=date(2026, 11, 3), start_time='09:00', end_time='10:00',
                          title='Synthetic', category='lecture', course='test'))
    db.get(Lecture, ('test', 'demo')).timetable_event_id = 'event'
    db.commit()


def rates(at=NOW):
    with patch('app.lecture_mastery.datetime') as clock:
        clock.now.return_value = at
        timetable = client.get('/api/timetable').json()['events'][0]['lectures'][0]['mastery']
        detail = client.get('/api/lectures/test/demo').json()['mastery']
        progress = client.post('/api/timetable/study-progress',
                               json={'lectures': [{'subject': 'test', 'runId': 'demo'}]}).json()['lectures'][0]
    assert progress['ready'] == (progress['mastery'] is not None)
    return timetable, detail, progress['mastery']


user('a')
assert rates() == (None, None, None)  # 공개 전: 잴 것이 없다
publish(client, user)
empty = rates()
assert empty[0] == empty[1] == empty[2] and empty[0]['score'] == 0 and empty[0]['scope'] == 'main-quiz'
assert empty[0]['status'] == 'not_started' and empty[0]['targetCount'] >= 1

sid = start(client)
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g1', 'rate', selfRating='Good').status_code == 200
after = rates(NOW + timedelta(minutes=1))
assert after[0] == after[1] == after[2] and 0 < after[0]['score'] < 100, after
assert after[0]['status'] == 'needs_review' and after[0]['ratedTargets'] == 1

# Main-Quiz 요약(목록·패널이 읽는 rootRate)도 같은 숫자다.
with patch('app.routes.root_learning.now', return_value=NOW + timedelta(minutes=1)):
    summary = client.get('/api/root-learning/lectures/test/demo').json()['summary']
assert summary['score'] == after[0]['score'], (summary.get('score'), after[0])

# 복습 없이 시간이 지나면 내려간다.
later = rates(NOW + timedelta(days=60))
assert later[0]['score'] < after[0]['score']

user('b')  # 남의 기록은 섞이지 않는다.
assert rates()[0]['score'] == 0
user('admin', True)
assert client.put(ADMIN + '/publication', json={'revision': 'v1', 'reviewed': True, 'enabled': False}).status_code == 200
user('a')
assert rates() == (None, None, None)  # 공개를 멈추면 학습률도 없다(기록은 남는다)
with SessionLocal() as db:
    assert any(e['kind'] == 'rate' for e in content.events_for(db, 'test', 'demo', 'a'))
print('PASS: timetable·detail·study-progress·summary share the Main-Quiz rate; decay, user and publication bounds')
