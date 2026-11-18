"""모아풀기 시작 화면 선택지(docs/changes/2026-11-18-mix-options).

분류(미열람·복습 대상·나중), 두 체크와 중요도로 고르기, 순서, 재개·멱등, 오늘 학습 흐름과의 분리."""
from datetime import timedelta
from tests.root_support import setup, publish, view, action, NOW, BASE
client, user, SessionLocal = setup()
from app.routes import root_learning
from app.root_learning import mix
publish(client, user)
MIX = BASE + '/mix'
SESSIONS = BASE + '/mix-sessions'
ALL = ['Essential', 'Core', 'Important', 'Optional']


def counts():
    r = client.get(MIX); assert r.status_code == 200, r.text
    return r.json()


def begin(request, tiers=ALL, unseen=False, ignore=False, order='ordered'):
    return client.post(SESSIONS, json={'requestId': request, 'tiers': tiers, 'unseen': unseen,
                                       'ignoreSchedule': ignore, 'order': order})


def task_ids(sid):
    with SessionLocal() as db:
        from app.models.root_learning import RootSession
        return [t['task_id'] for t in db.get(RootSession, sid).tasks]


# ── R1: nothing seen yet → every unit is unseen ──
first = counts()
assert first['title'] == 'Synthetic root lecture' and first['open'] == [] and first['closed'] == []
assert first['counts']['Core'] == {'unseen': 3, 'due': 0, 'later': 0}, first
assert all(first['counts'][t] == {'unseen': 0, 'due': 0, 'later': 0} for t in ['Essential', 'Important', 'Optional'])

# ── R2: without 미열람 문항 보기 there is nothing to solve; with it, every unseen task in document order ──
assert begin('none').status_code == 409
assert begin('dup', tiers=['Core', 'Core']).status_code == 422
assert begin('empty', tiers=[]).status_code == 422
r = begin('m1', unseen=True); assert r.status_code == 200, r.text
sid = r.json()['sessionId']
assert r.json()['count'] == 3 and task_ids(sid) == ['task1', 'task2', 'task3']
# 멱등: 같은 요청은 같은 결과, 같은 ID의 다른 내용은 409.
assert begin('m1', unseen=True).json() == r.json()
assert begin('m1', unseen=True, order='random').status_code == 409

# ── R7: the mix session is not today's stream of the single-lecture screen ──
overview = client.get(BASE).json()
assert overview['sessionId'] is None and overview['todayDone'] == 0, overview

# Solve task1 in the mix session: the same events as the lecture screen.
assert action(client, sid, 'mx-r1', 'reveal', attempted=True, response='x').status_code == 200
assert action(client, sid, 'mx-g1', 'rate', grade='independent').status_code == 200
assert view(client, sid)['position'] == 1
after = counts()
assert after['counts']['Core'] == {'unseen': 2, 'due': 0, 'later': 1}, after
assert after['open'] == [{'sessionId': sid, 'options': {'tiers': ALL, 'unseen': True, 'ignoreSchedule': False,
                                                        'order': 'ordered'}, 'left': 2}], after
# The lecture screen's plan sees the rating (task1 left today's recommendation).
assert 'task1' not in [t['task_id'] for t in client.get(BASE).json()['plan']['tasks']]

# ── R6: same options resume; other options open their own session ──
r = begin('m2', unseen=True); assert r.status_code == 200
assert r.json() == {'sessionId': sid, 'version': view(client, sid)['version'], 'count': 3}
r = begin('m3', ignore=True); assert r.status_code == 200, r.text   # 나중(오늘 푼 task1)만
assert r.json()['sessionId'] != sid and task_ids(r.json()['sessionId']) == ['task1']
# 다 푼 회차는 closed로 남는다(마침 화면용).
m3 = r.json()['sessionId']
assert action(client, m3, 'mx-m3r', 'reveal', attempted=True, response='x').status_code == 200
assert action(client, m3, 'mx-m3g', 'rate', grade='independent').status_code == 200
assert counts()['closed'] == [{'sessionId': m3, 'count': 1, 'options': {'tiers': ALL, 'unseen': False, 'ignoreSchedule': True,
                                                                         'order': 'ordered'}}], counts()
assert begin('m4').status_code == 409                                 # 복습 대상 없음

# ── R1 due: much later, task1's review date has come ──
root_learning.now = lambda: NOW + timedelta(days=60)
later = counts()
assert later['counts']['Core'] == {'unseen': 2, 'due': 1, 'later': 0}, later
assert later['open'] == [] and later['closed'] == []   # 어제 회차는 이어 풀지 않는다
r = begin('m5'); assert r.status_code == 200, r.text
assert task_ids(r.json()['sessionId']) == ['task1']
r = begin('m6', unseen=True, ignore=True); assert r.status_code == 200
assert r.json()['count'] == 3

# A task seen but not rated is due, unless touched today.
root_learning.now = lambda: NOW + timedelta(days=61)
sid2 = begin('m7', unseen=True).json()['sessionId']
assert task_ids(sid2) == ['task1', 'task2', 'task3']
assert action(client, sid2, 'mx-g7r', 'reveal', attempted=True, response='x').status_code == 200
assert action(client, sid2, 'mx-g7', 'rate', grade='independent').status_code == 200
assert action(client, sid2, 'mx-r2', 'reveal', attempted=True, response='y').status_code == 200
assert counts()['counts']['Core'] == {'unseen': 1, 'due': 0, 'later': 2}
root_learning.now = lambda: NOW + timedelta(days=62)
assert counts()['counts']['Core']['due'] == 1   # task2: 시도했지만 평가 없음

# ── R3 중요도: 「내 중요도」 follows; only chosen tiers ──
r = client.put(BASE + '/questions/Q3/tier', json={'requestId': 'tier3', 'tier': 'Optional'}); assert r.status_code == 200, r.text
c = counts()['counts']
assert c['Optional'] == {'unseen': 1, 'due': 0, 'later': 0} and c['Core']['unseen'] == 0, c
assert begin('m8', tiers=['Optional'], unseen=True).json()['count'] == 1
assert begin('m9', tiers=['Core'], unseen=True).status_code in (200, 409)
r = begin('m10', tiers=['Core'], unseen=True, ignore=True); assert r.status_code == 200
assert 'task3' not in task_ids(r.json()['sessionId'])
# 강의 화면의 중요도 저장값은 그대로다.
assert client.get(BASE).json()['focus']['tiers'] == ALL

# ── R4 섞어서: same seed same order, prerequisite question first ──
doc = {'tasks': [{'task_id': f't{i}', 'question_id': f'q{i}', 'direction_id': f'd{i}'} for i in range(8)],
       'bank_snapshot': {'questions': [{'question_id': f'q{i}', **({'prerequisites': ['q6']} if i == 2 else {})}
                                        for i in range(8)]}}
orders = set()
for seed in range(40):
    out = [t['task_id'] for t in mix.shuffled(doc, doc['tasks'], str(seed))]
    assert sorted(out) == sorted(t['task_id'] for t in doc['tasks'])
    assert out.index('t6') < out.index('t2'), out
    assert out == [t['task_id'] for t in mix.shuffled(doc, list(reversed(doc['tasks'])), str(seed))]
    orders.add(tuple(out))
assert len(orders) > 20
# 선행 문항이 고르지 않은 쪽이면 끌어오지 않는다.
assert 't6' not in [t['task_id'] for t in mix.shuffled(doc, [t for t in doc['tasks'] if t['task_id'] != 't6'], 's')]

print('root mix: ok')
