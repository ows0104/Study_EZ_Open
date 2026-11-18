"""선행 문항 포함/미포함(docs/changes/2026-11-18-prereq-toggle).

Important까지만 켜도 Optional이 나왔다: 오늘 고른 문항의 선행 문항을 중요도 칩과 상관없이 끌어오기 때문이다.
오늘 학습은 과목마다 끌 수 있고(기본 포함), 모아풀기는 켤 수 있다(기본 미포함).
"""
import copy
# 두 목표 판·기록 도우미. 그 모듈이 import될 때 setup()(격리된 sqlite)과 자기 검사를 한 번 돈다.
from tests.test_root_prereq_release import two_goal_document, rated, ids, every, later, focus
from tests.root_support import POLICY, NOW, BASE, publish
from app.root_learning.planning import plan
from app.root_learning import mix

# ── R1 계획: 존재 목표의 문항 단위 연결 ──
doc = two_goal_document()  # T1(D1: Q1·Q3·Q4) → T2(D2: Q2), 존재 간선
link = {'Q2': ['Q1']}
assert ids(plan(doc, [], every, later, POLICY, focus=focus, links=link)) == [('task-q1', '명시적 선행 연결'), ('task-q2', '새 목표')]
assert ids(plan(doc, [], every, later, POLICY, focus=focus, links=link, prereqs=False)) == [('task-q2', '새 목표')]
# links 없는 판(존재 목표 전체를 끌어오던 규칙)도 끄면 필터 안에서만.
assert [t for t, _ in ids(plan(doc, [], every, later, POLICY, focus=focus))] == ['task-q1', 'task-q3', 'task-q4', 'task-q2']
assert ids(plan(doc, [], every, later, POLICY, focus=focus, prereqs=False)) == [('task-q2', '새 목표')]
# 필터 안의 선행은 끈 뒤에도 그대로 끌어온다.
assert [t for t, _ in ids(plan(doc, [], every, later, POLICY, focus={'task-q1', 'task-q2'}, links=link, prereqs=False))] == \
    ['task-q1', 'task-q2']
# 중요도가 모두 켜졌으면(focus 없음) 선택은 효과가 없다.
for links in (link, None):
    assert plan(doc, [], every, later, POLICY, links=links, prereqs=False) == plan(doc, [], every, later, POLICY, links=links)

# ── R1 계획: 문항 선행(questions[].prerequisites, order_plan) ──
hard = two_goal_document(prerequisite=False)
next(q for q in hard['bank_snapshot']['questions'] if q['question_id'] == 'Q2')['prerequisites'] = ['Q1']
assert ids(plan(hard, [], every, later, POLICY, focus=focus)) == [('task-q1', '명시적 선행 문항'), ('task-q2', '새 목표')]
assert ids(plan(hard, [], every, later, POLICY, focus=focus, prereqs=False)) == [('task-q2', '새 목표')]

# ── R2 모아풀기 고르기 ──
tiers = {'task-q1': 'Optional', 'task-q3': 'Optional', 'task-q4': 'Optional', 'task-q2': 'Core'}
classes = dict.fromkeys(tiers, 'unseen')
pick = lambda d, cls=classes, **kw: [t['task_id'] for t in mix.select(d, cls, tiers, ['Core'], True, False, **kw)]
assert pick(hard) == ['task-q2']  # 기본: 지금과 같다
assert pick(hard, prereqs=True) == ['task-q1', 'task-q2']
# 존재 연결도 따라간다. 연결이 없는 Q4는 오지 않는다.
assert pick(doc, prereqs=True, links={'Q2': ['Q3']}) == ['task-q3', 'task-q2']
# 이미 익힌(나중) 선행은 더하지 않고, 복습 대상은 더한다.
assert pick(hard, {**classes, 'task-q1': 'later'}, prereqs=True) == ['task-q2']
assert pick(hard, {**classes, 'task-q1': 'due'}, prereqs=True) == ['task-q1', 'task-q2']
# 거슬러 올라가며 이어진다: Q2 ← Q1 ← Q3.
chain = copy.deepcopy(hard)
next(q for q in chain['bank_snapshot']['questions'] if q['question_id'] == 'Q1')['prerequisites'] = ['Q3']
assert pick(chain, prereqs=True) == ['task-q1', 'task-q3', 'task-q2']
# 고른 문항이 없으면 선행만으로 회차를 열지 않는다.
assert [t for t in mix.select(hard, {**classes, 'task-q2': 'later'}, tiers, ['Core'], True, False, prereqs=True)] == []

# ── 서버 경로: 오늘 학습 저장값, 모아풀기 조건 ──
from fastapi.testclient import TestClient
from app.main import app
from app.auth import CurrentUser, get_current_user, APP_POLICY, ROLE_ADMIN


def user(uid='a', admin=False):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=uid, email=f'{uid}@example.com', is_admin=admin, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


client = TestClient(app)
publish(client, user)
user('a')
FOCUS = BASE + '/focus'
assert client.get(BASE).json()['focus']['prereqs'] is True  # 기본 포함
r = client.put(FOCUS, json={'requestId': 'f1', 'tiers': ['Core'], 'prereqs': False}); assert r.status_code == 200, r.text
assert r.json()['focus'] == {**r.json()['focus'], 'tiers': ['Core'], 'prereqs': False}
# 생략하면 지난 선택을 둔다(칩만 바꾸는 요청).
r = client.put(FOCUS, json={'requestId': 'f2', 'tiers': ['Core', 'Important']}); assert r.json()['focus']['prereqs'] is False
# 멱등: 같은 요청은 같은 결과, 같은 ID의 다른 내용은 409.
assert client.put(FOCUS, json={'requestId': 'f1', 'tiers': ['Core'], 'prereqs': False}).status_code == 200
assert client.put(FOCUS, json={'requestId': 'f1', 'tiers': ['Core'], 'prereqs': True}).status_code == 409
r = client.put(FOCUS, json={'requestId': 'f3', 'tiers': ['Core'], 'prereqs': True}); assert r.json()['focus']['prereqs'] is True
# 다른 사용자는 따로다.
user('b')
assert client.get(BASE).json()['focus']['prereqs'] is True

# 모아풀기: 켠 조건은 회차 조건에 남고, 끈 조건은 예전 모양 그대로다.
user('a')
SESSIONS = BASE + '/mix-sessions'
body = {'tiers': ['Essential', 'Core', 'Important', 'Optional'], 'unseen': True, 'ignoreSchedule': False, 'order': 'ordered'}
plain = client.post(SESSIONS, json={'requestId': 'm1', **body}); assert plain.status_code == 200, plain.text
withpre = client.post(SESSIONS, json={'requestId': 'm2', **body, 'prereqs': True}); assert withpre.status_code == 200, withpre.text
assert plain.json()['sessionId'] != withpre.json()['sessionId']
mixed = client.get(BASE + '/mix').json()['open']
assert sorted(map(str, (o['options'] for o in mixed))) == sorted(map(str, [body | {}, body | {'prereqs': True}])), mixed
# 같은 조건이면 열린 회차를 잇는다.
assert client.post(SESSIONS, json={'requestId': 'm3', **body, 'prereqs': False}).json()['sessionId'] == plain.json()['sessionId']

print('PASS: 선행 문항 포함/미포함 — 오늘 학습(과목별, 기본 포함)·모아풀기(회차 조건, 기본 미포함), 기록 그대로')
