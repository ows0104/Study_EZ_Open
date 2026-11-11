"""Main-Quiz 「이 문제 제외」(2026-11-12, 키 5): 현재 문항을 이 판에서 빼고 다음으로, Z면 없던 일로."""
from tests.root_support import setup, publish, start, view, action, BASE
client, user, SessionLocal = setup()
publish(client, user)
sid = start(client)
from app.models.root_learning import RootSession, RootEvent
# 같은 문항의 과제가 뒤에 다시 나오는 회차(다른 방향)를 흉내 낸다: 첫 과제를 목록 끝에 한 번 더 둔다.
with SessionLocal() as db:
    row = db.get(RootSession, sid); row.tasks = [*row.tasks, dict(row.tasks[0])]; db.commit()


def ok(request, kind, **kwargs):
    r = action(client, sid, request, kind, **kwargs); assert r.status_code == 200, r.text
    return r.json()


def position():
    v = view(client, sid)
    return v['position'], v['task']['id'] if v['task'] else None


count = view(client, sid)['count']
first = position()
assert first[0] == 0 and first[1] is not None
excluded_task = first[1]
version = view(client, sid)['version']
first_result = ok('x1', 'exclude')
assert position()[0] >= 1 and position()[1] != excluded_task
# 같은 요청 ID 재요청은 같은 결과, 다른 동작이면 409.
again = client.post('/api/root-learning/sessions/' + sid + '/events', json={'requestId': 'x1', 'version': version, 'kind': 'exclude'})
assert again.status_code == 200 and again.json() == first_result, again.text
assert action(client, sid, 'x1', 'skip').status_code == 409

with SessionLocal() as db:
    tasks = db.get(RootSession, sid).tasks
    qid = next(t['question_id'] for t in tasks if t['task_id'] == excluded_task)
    event = db.query(RootEvent).filter(RootEvent.request_id == 'x1').one()
    assert event.kind == 'exclude' and event.payload['question_id'] == qid
# 남은 과제를 끝까지 넘기면 같은 문항의 과제는 건너뛴다.
seen = []
while not view(client, sid)['finished']:
    seen.append(position()[1]); ok(f's{len(seen)}', 'skip')
assert all(next(t['question_id'] for t in tasks if t['task_id'] == tid) != qid for tid in seen), (seen, qid)
assert len(seen) == count - 2, (seen, count)  # 맨 끝에 다시 둔 같은 문항 과제는 건너뛰었다.

# 오늘 계획·현황에서도 빠진다.
overview = client.get(BASE).json()
planned = [t['question_id'] for t in (overview.get('plan') or {}).get('tasks', [])]
assert qid not in planned, planned
assert overview['preparationProblems'] >= 1, overview

# Z로 끝까지 되돌리면 제외도 풀리고 첫 과제로 돌아온다.
for i in range(len(seen) + 1):
    ok(f'z{i}', 'undo')
assert position() == first, position()
overview = client.get(BASE).json()
assert overview['preparationProblems'] == 0, overview

# 현재 과제가 없으면 409.
ok('x2', 'exclude')
while not view(client, sid)['finished']:
    ok(f'e{view(client, sid)["position"]}', 'skip')
assert action(client, sid, 'x3', 'exclude').status_code == 409
print('PASS: exclude skips the question for this revision, plan drops it, Z restores it, idempotent request')
