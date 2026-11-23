"""Main-Quiz 강의 문항 전체 보기(2026-11-23): 읽기 전용 목록·상세, 개인 수정·내 중요도 반영, 권한."""
from sqlalchemy import select, func
from tests.root_support import setup, publish, BASE

client, user, SessionLocal = setup()
from app.models import BankFeedback, BankPersonalEdit
from app.models.root_learning import RootEvent, RootSession

# 공개 전에는 학습자에게 없다.
user('a')
assert client.get(BASE + '/questions').status_code == 404
publish(client, user)


def counts():
    with SessionLocal() as db:
        return tuple(db.scalar(select(func.count()).select_from(t)) for t in (RootEvent, RootSession, BankPersonalEdit, BankFeedback))


before = counts()
listed = client.get(BASE + '/questions')
assert listed.status_code == 200, listed.text
data = listed.json()
assert data['revision'] == 'v1' and data['editable'] is True
assert [s['sourceId'] for s in data['sources']] == ['S1'] and data['sources'][0]['label'] == 'synthetic'
ids = [r['question']['question_id'] for r in data['questions']]
assert ids[:3] == ['Q1', 'Q2', 'Q3'], ids
first = data['questions'][0]
assert first['question']['question'] == 'Synthetic question 1?' and first['answer']['answer']
assert first['question']['tier'] in ('Essential', 'Core', 'Important', 'Optional') and first['question']['format']
assert first['planned'] is True and first['question']['figures'] == 0
assert all(p['sourceId'] == 'S1' and type(p['page']) is int for r in data['questions'] for p in r['pages'])
# 출제 메타(정답 근거·검토용 칸)는 앞면 허용 목록 밖이다.
assert 'source_refs' not in first['question'] or first['question']['source_refs'] == []

detail = client.get(BASE + '/questions/Q1/detail')
assert detail.status_code == 200, detail.text
assert detail.json()['question']['question_id'] == 'Q1' and detail.json()['answer']['answer'] == first['answer']['answer']
assert client.get(BASE + '/questions/NOPE/detail').status_code == 404
# 열람은 아무것도 쓰지 않는다.
assert counts() == before

# 개인 수정·내 중요도는 내 목록에만 보인다.
snap = client.get(BASE + '/questions/Q1/personal').json()
saved = client.put(BASE + '/questions/Q1/personal', json={'revision': snap['revision'], 'question': 'Edited question 1?',
                   'answer': 'Edited answer 1', 'comment': '', 'report': False, 'category': 'content'})
assert saved.status_code == 200, saved.text
tier = 'Optional' if first['question']['tier'] != 'Optional' else 'Core'
assert client.put(BASE + '/questions/Q2/tier', json={'requestId': 'tier-1', 'tier': tier}).status_code == 200
mine_rows = {r['question']['question_id']: r for r in client.get(BASE + '/questions').json()['questions']}
assert mine_rows['Q1']['question']['question'] == 'Edited question 1?' and mine_rows['Q1']['question']['personalEdited']
assert mine_rows['Q1']['answer']['answer'] == 'Edited answer 1'
assert mine_rows['Q2']['question']['tier'] == tier and mine_rows['Q2']['question']['personalTier']
assert client.get(BASE + '/questions/Q1/detail').json()['answer']['answer'] == 'Edited answer 1'

user('b')
other = {r['question']['question_id']: r for r in client.get(BASE + '/questions').json()['questions']}
assert other['Q1']['question']['question'] == 'Synthetic question 1?' and not other['Q1']['question'].get('personalEdited')
assert not other['Q2']['question'].get('personalTier')

# 쪽 번호: 인용 쪽(pages·locator)과 그림 쪽, 중복·범위 밖 제외, 족보 표시.
from app.root_learning.question_list import reference_pages
doc = {'review': {'sources': [{'source_id': 'N', 'kind': 'notes', 'page_count': 30},
                              {'source_id': 'E', 'kind': 'exam', 'page_count': None}]}}
q = {'source_refs': [{'source_id': 'N', 'pages': [3, 3, 31, 0]}, {'source_id': 'N', 'locator': 'p. 5-6'},
                     {'source_id': 'E', 'pages': [12]}, {'source_id': 'EXT', 'pages': [1]}],
     'stimuli': [{'source_id': 'N', 'page': 3}, {'source_id': 'N', 'page': 9}]}
got = [(p['sourceId'], p['page'], p['exam']) for p in reference_pages(doc, q)]
assert got[0] == ('N', 3, False) and ('N', 31, False) not in got and ('N', 0, False) not in got, got
assert ('E', 12, True) in got and ('N', 9, False) in got and all(sid != 'EXT' for sid, _, _ in got), got
assert len(got) == len(set(got)), got
print('root question list ok', got)
