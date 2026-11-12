"""The plan never receives a task whose prerequisite is missing (docs/changes/2026-11-12-plan-prereq-closure).

Production 2026-11-12: `GET /api/root-learning` and `…/focus` answered 500 with `order_plan` →
「Prepared prerequisite became unavailable」. Main-Quiz documents are standalone, and `availability` returned
before the /2·/4 dependency rule, so a personally excluded prerequisite left its dependents available. The
importance filter then narrowed the set given to `plan` without any rule at all.

Rules checked here:
- A prerequisite that is not available (personal exclude) drops its dependents, as for /2·/4 bank sources.
- A prerequisite that is available but outside today's chosen tiers is brought forward as 「명시적 선행 문항」
  when it is not yet assessed (order_plan's own rule); an assessed one is not served again.
- Learner records are not changed by either."""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, publish, start, view, document, POLICY, NOW, BASE
client, user, SessionLocal = setup()
from app.models.root_learning import RootContent, RootEvent
from app.root_learning import content
from app.root_learning.planning import plan
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))
REVISION = 'pq1'


def prerequisite_document():
    """/4 document, one target T1: D1 asked by Q1·Q3·Q4, D2 by Q2. Q4 needs Q2 (a question prerequisite)."""
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision=REVISION)
    doc['review']['lecture_id'] = 'test/demo'
    bank = doc['bank_snapshot']
    for i in (3, 4):
        q = copy.deepcopy(bank['questions'][0])
        q.update(question_id=f'Q{i}', question=f'Synthetic part {i} of goal 1?', answer=f'Secret part {i}', answer_units=[f'Secret part {i}'])
        bank['questions'].append(q)
        m = copy.deepcopy(doc['review']['mappings'][0]); m['question_id'] = f'Q{i}'
        doc['review']['mappings'].append(m)
    next(q for q in bank['questions'] if q['question_id'] == 'Q4')['prerequisites'] = ['Q2']
    doc['tasks'] = [{'task_id': 'task-q2', 'question_id': 'Q2', 'direction_id': 'D2'},
                    {'task_id': 'task-q1', 'question_id': 'Q1', 'direction_id': 'D1'},
                    {'task_id': 'task-q3', 'question_id': 'Q3', 'direction_id': 'D1'},
                    {'task_id': 'task-q4', 'question_id': 'Q4', 'direction_id': 'D1'}]
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return validate_document(doc)


def overview():
    r = client.get(BASE); assert r.status_code == 200, r.text
    return r.json()


def planned(info):
    return [t['task_id'] for t in info['plan']['tasks']]


def records(uid):
    with SessionLocal() as db:
        return sorted((e.request_id, e.kind, json.dumps(e.payload, sort_keys=True))
                      for e in db.query(RootEvent).filter(RootEvent.user_id == uid))


doc = prerequisite_document()
assert doc['bank_source'] == 'standalone'
publish(client, user, doc)
ALL = {'task-q1', 'task-q2', 'task-q3', 'task-q4'}

# Every task available: the prerequisite comes before its dependent.
user('a')
first = planned(overview())
assert set(first) == ALL and first.index('task-q2') < first.index('task-q4'), first

# ── 1. Personal exclude of the prerequisite drops its dependent from availability, plan and every entry point ──
with SessionLocal() as db:
    db.add(RootEvent(user_id='a', request_id='x-q2', session_id="", subject='test', run_id='demo', revision=REVISION,
                     kind='exclude', payload={'question_id': 'Q2'}, result={}, created_at=NOW - timedelta(hours=1)))
    db.commit()
    row = db.get(RootContent, ('test', 'demo', REVISION))
    available, problems = content.availability(db, row, 'a')
assert available == {'task-q1', 'task-q3'}, available
assert problems == {'task-q2': '개인 제외', 'task-q4': '명시적 선행 문항이 준비되지 않음'}, problems
before = records('a')
info = overview()
assert sorted(planned(info)) == ['task-q1', 'task-q3'], info['plan']['tasks']
assert info['preparationProblems'] == 2
for path in ('/api/root-learning', '/api/main-quiz/lectures/test/demo/entry'):
    r = client.get(path); assert r.status_code == 200, (path, r.text)
assert view(client, start(client, 'a-start'))['count'] == 2
assert [r for r in records('a') if r[1] != 'start'] == [r for r in before if r[1] != 'start']

# ── 2. Importance filter leaving out an unassessed prerequisite brings it forward instead of failing ──
user('b')
r = client.put(BASE + '/questions/Q2/tier', json={'requestId': 'b-t2', 'tier': 'Optional'}); assert r.status_code == 200, r.text
r = client.put(BASE + '/focus', json={'requestId': 'b-f1', 'tiers': ['Essential', 'Core', 'Important']}); assert r.status_code == 200, r.text
before = records('b')
info = overview()
tasks = info['plan']['tasks']
order = [t['task_id'] for t in tasks]
assert set(order) == ALL and order.index('task-q2') < order.index('task-q4'), order
assert next(t for t in tasks if t['task_id'] == 'task-q2')['reason'] == '명시적 선행 문항', tasks
assert info['focus']['counts'] == {'Essential': 0, 'Core': 3, 'Important': 0, 'Optional': 1}  # counts are unchanged
for path in ('/api/root-learning', '/api/main-quiz/lectures/test/demo/entry'):
    r = client.get(path); assert r.status_code == 200, (path, r.text)
assert records('b') == before

# Without the dependent, the filtered-out prerequisite is not brought in.
focus = {'task-q1', 'task-q3'}
assert sorted(t['task_id'] for t in plan(doc, [], ALL, NOW, POLICY, focus=focus)['tasks']) == ['task-q1', 'task-q3']
# An assessed prerequisite outside the filter is not served again for its dependent.
rated = [{'id': 'reveal-q2', 'kind': 'reveal', 'revision': REVISION, 'at': NOW - timedelta(minutes=5),
          'payload': {'task_id': 'task-q2', 'direction_id': 'D2', 'attempted': True, 'policy': POLICY}},
         {'id': 'rate-q2', 'kind': 'rate', 'revision': REVISION, 'at': NOW - timedelta(minutes=4),
          'payload': {'task_id': 'task-q2', 'direction_id': 'D2', 'grade': 'independent', 'helped': False,
                      'policy': POLICY, 'exam_date': '2026-11-07'}}]
later = plan(doc, rated, ALL, NOW, POLICY, focus=ALL - {'task-q2'})['tasks']
assert 'task-q2' not in [t['task_id'] for t in later] and 'task-q4' in [t['task_id'] for t in later], later
# Without a filter, plan is called as before.
assert plan(doc, [], ALL, NOW, POLICY) == plan(doc, [], ALL, NOW, POLICY, focus=ALL)

# ── 3. Older documents without /2·/4 dependencies are unchanged by the closure ──
legacy = document()
assert content.close_prerequisites(legacy, {'task1'}, {}) == ({'task1'}, {})
print('PASS: an excluded prerequisite drops its dependents, a filtered-out unassessed prerequisite is brought forward, '
      'catalog/overview/entry answer 200, learner records unchanged')
