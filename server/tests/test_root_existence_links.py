"""존재 목표 선행을 문항 단위로 끌어온다(docs/changes/2026-11-18-existence-prereq-by-question).

261110_02(아데노): 존재 간선 T020 → T035가 T020 과제 전부를 필터 밖에서 끌어와, 어느 문항의 전제도 아닌 Optional Q107이 나왔다.
전제 기록(presuppose/1)의 「X의 발문이 전제 → Y가 답함」만 따라가면, 오늘 목록의 X가 전제하는 Y만 앞에 온다.
"""
from datetime import timedelta
from tests.root_support import POLICY, NOW
# 두 목표 판·기록 도우미를 빌려 온다. 그 모듈이 import될 때 setup()(격리된 sqlite)과 자기 검사를 한 번 돈다.
from tests.test_root_prereq_release import two_goal_document, rated, ids, every, later, focus
from app.root_learning.planning import plan, existence_links
from app.root_learning import content
from app.database import SessionLocal
from app.models.root_generation import RootGeneration

doc = two_goal_document()  # T1(D1: Q1·Q3·Q4) → T2(D2: Q2), 존재 간선
link = existence_links(doc, [{'question_id': 'Q2', 'a': 'A', 'b': 'B', 'link': 'A의 B', 'recalled_by': ['Q1'], 'point_id': None}])
assert link == {'Q2': ['Q1']}, link

# 1. 오늘 목록의 Q2가 전제하는 연결을 답하는 Q1만 필터 밖에서 끌어온다. 같은 존재 목표의 Q3·Q4는 따라오지 않는다.
assert ids(plan(doc, [], every, later, POLICY, focus=focus, links=link)) == [('task-q1', '명시적 선행 연결'), ('task-q2', '새 목표')]

# 2. 풀어 주기는 Q1 자신의 기록으로: 쉽게 맞혔으면 끌어오지 않고, 틀렸으면 끌어온다. 연결 없는 Q3을 틀린 것은 상관없다.
easy = rated('task-q1', 'D1', NOW, 'independent') + rated('task-q3', 'D1', NOW + timedelta(seconds=5), 'missed')
assert ids(plan(doc, easy, every, later, POLICY, focus=focus, links=link)) == [('task-q2', '새 목표')]
missed = rated('task-q1', 'D1', NOW, 'missed')
assert [t for t, _ in ids(plan(doc, missed, every, later, POLICY, focus=focus, links=link))] == ['task-q1', 'task-q2']

# 3. 오늘 이미 푼 Q1은 다시 끌어오지 않는다.
today = rated('task-q1', 'D1', later - timedelta(minutes=3), 'missed')
assert ids(plan(doc, today, every, later, POLICY, focus=focus, links=link)) == [('task-q2', '새 목표')]

# 4. 전제하는 문항이 오늘 목록에 없으면 끌어오지 않는다(오늘 목록에서 빠진 Optional의 전제가 다른 문항을 끌어오지 않음).
other = {'Q3': ['Q1']}
assert ids(plan(doc, [], every, later, POLICY, focus=focus, links=other)) == [('task-q2', '새 목표')]

# 5. 연결이 하나도 없는 판(links={})이면 존재 간선은 순서만 정한다. 필터 안이면 앞 목표가 먼저 온다.
assert ids(plan(doc, [], every, later, POLICY, focus=focus, links={})) == [('task-q2', '새 목표')]
inside = ids(plan(doc, [], every, later, POLICY, focus={'task-q1', 'task-q2'}, links={}))
assert [t for t, _ in inside] == ['task-q1', 'task-q2'], inside

# 6. 지도 관계 선행은 그대로(필터 안에서만 목표 단위).
mapped = two_goal_document()
mapped['prerequisites'] = [{'before_target': 'T1', 'after_target': 'T2', 'relation_id': 'RP-C007-C022'}]
assert existence_links(mapped, [{'question_id': 'Q2', 'recalled_by': ['Q1'], 'point_id': None}]) == {}
assert [t for t, _ in ids(plan(mapped, [], every, later, POLICY, focus={'task-q1', 'task-q3', 'task-q2'}, links={}))] == \
    ['task-q1', 'task-q3', 'task-q2']

# 7. links 없음(None)은 11-16 규칙 그대로: 존재 간선이 앞 목표 과제 전부를 끌어온다.
assert [t for t, _ in ids(plan(doc, [], every, later, POLICY, focus=focus))] == ['task-q1', 'task-q3', 'task-q4', 'task-q2']

# 8. existence_links: 포인트로 만든 존재 목표의 문항, 놓이지 않은 문항, 판에 없는 간선(거꾸로·같은 목표).
doc['review']['points'] = [{'point_id': 'P9', 'target_ids': ['T1'], 'text': 'x'}]
records = [{'question_id': 'Q2', 'recalled_by': [], 'point_id': 'P9'},
           {'question_id': 'Q2', 'recalled_by': ['Q404'], 'point_id': None},
           {'question_id': 'Q1', 'recalled_by': ['Q2', 'Q3'], 'point_id': None},
           {'question_id': 'Q404', 'recalled_by': ['Q1'], 'point_id': None}]
assert existence_links(doc, records) == {'Q2': ['Q1', 'Q3', 'Q4']}

# 9. 서버: 판 auto-<id>의 생성 기록에서 읽는다. 기록이 없는 판은 None(이전 규칙).
gid = 'e' * 32
with SessionLocal() as db:
    db.add(RootGeneration(id=gid, job_id=990001, subject='test', run_id='demo', user_id='admin', request_id='req-links',
                          input_digest='1' * 64, baseline='b' * 64, packet={}, result_digest='2' * 64,
                          result={'manifest': {'presuppositions': [{'question_id': 'Q2', 'recalled_by': ['Q1'], 'point_id': None}]}}))
    db.commit()
    class Row:
        subject, run_id, document = 'test', 'demo', doc
    published = Row(); published.revision = 'auto-' + gid
    assert content.existence_links(db, published) == {'Q2': ['Q1']}
    photo = Row(); photo.revision = 'photo-demo-r1'
    assert content.existence_links(db, photo) is None
    missing = Row(); missing.revision = 'auto-' + 'f' * 32
    assert content.existence_links(db, missing) is None

print('PASS: 존재 선행은 오늘 목록 문항이 전제하는 연결을 답하는 문항만 끌어온다; 풀어 주기는 그 문항 기록으로; 지도 선행·기록 없는 판은 그대로')
