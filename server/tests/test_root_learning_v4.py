"""root-generation/4 learner state is per task (docs/changes/2026-11-10-importance-at-authoring spec R8, option B).

One goal direction D1 is asked by three questions (Q1, Q3, Q4) on different parts; D2 by Q2.
Older documents (no generation_policy, root-generation/2) keep the per-direction path unchanged.
"""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, publish, start, view, action, document, POLICY, NOW, BASE, ADMIN
client, user, SessionLocal = setup()
from app.models.root_learning import RootEvent
from app.root_learning import content
from app.root_learning.planning import plan
from app.root_learning.policy import target_parameters
from app.root_learning.state import replay, replay_tasks, summary
from app.routes.root_learning import prior_exposure
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash, task_fingerprints

D1_TASKS = ['task-q1', 'task-q3', 'task-q4']
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def rehash(doc):
    bank = doc['bank_snapshot']
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return doc


def v4_document(revision='v4a'):
    """The /2 import fixture with two more questions on D1: three tasks on one direction."""
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision=revision)
    bank = doc['bank_snapshot']
    for i in (3, 4):
        q = copy.deepcopy(bank['questions'][0])
        q.update(question_id=f'Q{i}', question=f'Synthetic part {i} of goal 1?', answer=f'Secret part {i}', answer_units=[f'Secret part {i}'])
        bank['questions'].append(q)
        m = copy.deepcopy(doc['review']['mappings'][0]); m['question_id'] = f'Q{i}'
        doc['review']['mappings'].append(m)
    doc['tasks'] = [{'task_id': 'task-q1', 'question_id': 'Q1', 'direction_id': 'D1'},
                    {'task_id': 'task-q3', 'question_id': 'Q3', 'direction_id': 'D1'},
                    {'task_id': 'task-q4', 'question_id': 'Q4', 'direction_id': 'D1'},
                    {'task_id': 'task-q2', 'question_id': 'Q2', 'direction_id': 'D2'}]
    return validate_document(rehash(doc))


def rated(task_id, direction_id, at, grade='independent', revision='v4a', **extra):
    return [{'id': 'reveal-' + task_id + str(at), 'kind': 'reveal', 'revision': revision, 'at': at,
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'attempted': True, 'policy': POLICY, **extra}},
            {'id': 'rate-' + task_id + str(at), 'kind': 'rate', 'revision': revision, 'at': at + timedelta(seconds=1),
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'grade': grade, 'helped': False,
                         'policy': POLICY, 'exam_date': '2026-11-07', **extra}}]


doc = v4_document()
every = {t['task_id'] for t in doc['tasks']}

# 1. Every prepared task is a candidate: the three D1 tasks each get scheduled, in plan order.
first = plan(doc, [], every, NOW, POLICY)
assert [t['task_id'] for t in first['tasks']] == [*D1_TASKS, 'task-q2'], first['tasks']
assert first['newGoalQuota'] == 1 and first['unpreparedGoals'] == 0
assert plan(doc, [], every - {'task-q3'}, NOW, POLICY)['tasks'][1]['task_id'] == 'task-q4'

# 2. Rating one task leaves its siblings untouched; the direction is not recalled yet.
events = rated('task-q1', 'D1', NOW)
rows, directions, tasks = replay_tasks(doc, events, NOW + timedelta(minutes=1), POLICY)
assert set(tasks) == {'task-q1'} and tasks['task-q1']['rating'] == 'independent'
assert directions['D1']['rating'] == 'independent' and not directions['D1']['recalled'] and directions['D1']['learned']
assert rows[0]['learned'] and not rows[0]['recalled']
later = plan(doc, events, every, NOW + timedelta(minutes=1), POLICY)['tasks']
assert [t['task_id'] for t in later] == ['task-q3', 'task-q4', 'task-q2'], later      # unassessed siblings stay
assert {t['reason'] for t in later} == {'미평가 과제'}
assert summary(doc, events, every, NOW + timedelta(minutes=1), POLICY)['targets'][0]['status'] == '보완 필요'
# A partial on another task makes the direction's rating the lower one; the first task's state is unchanged.
partly = events + rated('task-q3', 'D1', NOW + timedelta(seconds=10), 'partial')
_, directions, tasks = replay_tasks(doc, partly, NOW + timedelta(minutes=1), POLICY)
assert tasks['task-q3']['rating'] == 'partial' and directions['D1']['rating'] == 'partial'
assert tasks['task-q1'] == replay_tasks(doc, events, NOW + timedelta(minutes=1), POLICY)[2]['task-q1']

# 3. The direction (and its target) is recalled only when all three tasks are.
two = events + rated('task-q3', 'D1', NOW + timedelta(seconds=10)) + rated('task-q2', 'D2', NOW + timedelta(seconds=20))
rows, directions, _ = replay_tasks(doc, two, NOW + timedelta(minutes=1), POLICY)
assert directions['D2']['recalled'] and not directions['D1']['recalled'] and not rows[0]['recalled']
three = two + rated('task-q4', 'D1', NOW + timedelta(seconds=30))
rows, directions, tasks = replay_tasks(doc, three, NOW + timedelta(minutes=1), POLICY)
assert directions['D1']['recalled'] and rows[0]['recalled']
assert directions['D1']['due'] == min(tasks[t]['due'] for t in D1_TASKS)
assert replay(doc, three, NOW + timedelta(minutes=1), POLICY) == (rows, directions)
assert summary(doc, three, every, NOW + timedelta(minutes=1), POLICY)['recalled'] == 1
assert plan(doc, three, every, NOW + timedelta(minutes=1), POLICY)['tasks'] == []
# Next day each task is due on its own; all three D1 tasks come back in plan order.
due = plan(doc, three, every, NOW + timedelta(days=1), POLICY)['tasks']
assert [t['task_id'] for t in due] == [*D1_TASKS, 'task-q2'] and {t['reason'] for t in due} == {'복습 확인'}

# 4. prior_exposure: /4 counts only the same task; the older path still counts the direction's relations.
q3 = next(q for q in doc['bank_snapshot']['questions'] if q['question_id'] == 'Q3')
task_q3 = doc['tasks'][1]
sibling_seen = {'reveals': {'task-q1': {'attempted': True}}, 'exposedRelations': ['R1']}
assert prior_exposure(doc, task_q3, q3, sibling_seen) is False
assert prior_exposure(doc, task_q3, q3, {'reveals': {'task-q3': {}}, 'exposedRelations': []}) is True
older = copy.deepcopy(doc); older['generation_policy'] = 'root-generation/2'
assert prior_exposure(older, task_q3, q3, sibling_seen) is True

# 5. /3 documents keep the per-direction path, and with one task per direction it equals the per-task replay.
legacy = document()
ratings = rated('task1', 'D1', NOW, revision='v1') + rated('task2', 'D2', NOW + timedelta(seconds=5), 'partial', revision='v1')
ratings += rated('task3', 'D3', NOW + timedelta(seconds=9), revision='v1', selfRating='Good',
                 targetParameters=target_parameters())
ratings[-1]['payload'].update(grade='independent')
for when in (NOW + timedelta(minutes=1), NOW + timedelta(days=2)):
    old_rows, old_directions = replay(legacy, ratings, when, POLICY)
    new_rows, _, by_task = replay_tasks(legacy, ratings, when, POLICY)
    assert old_rows == new_rows
    assert all(by_task[t['task_id']] == old_directions[t['direction_id']] for t in legacy['tasks'])
assert 'taskIds' not in old_directions['D1']                 # the per-direction path, not the derived one

# 6. API: three tasks in one session, a sibling's reveal does not make the next task "helped",
#    and /4 events record the question fingerprint used for carry-over.
publish(client, user, doc)
sid = start(client)
session = view(client, sid)
assert session['count'] == 4 and session['task']['id'] == 'task-q1'
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g1', 'rate', grade='independent').status_code == 200
nxt = view(client, sid)
assert nxt['task']['id'] == 'task-q3' and nxt['task']['helped'] is False
assert action(client, sid, 'r3', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g3', 'rate', grade='independent').status_code == 200
prints = task_fingerprints(doc)
with SessionLocal() as db:
    assert db.get(RootEvent, ('a', 'g1')).payload['question_sha256'] == prints['task-q1']
overview = client.get(BASE).json()
assert overview['summary']['learned'] == 1 and overview['summary']['recalled'] == 0

# 7. Carry-over between /4 revisions keys on the question fingerprint: Q1 and Q3 unchanged carry,
#    a changed Q4 starts fresh. Never by ID alone, never without a reviewed link.
changed = v4_document('v4b')
next(q for q in changed['bank_snapshot']['questions'] if q['question_id'] == 'Q4')['answer'] = 'Reworded part 4'
changed = rehash(changed)
unlinked = validate_document(copy.deepcopy(changed))
publish(client, user, unlinked)
assert client.get(BASE).json()['summary']['learned'] == 0         # same IDs, no link → nothing carries
linked = copy.deepcopy(changed); linked['revision'] = 'v4c'
linked['equivalences'] = [{'revision': 'v4a', 'from_direction': 'D1', 'to_direction': 'D1', 'reason': 'Reviewed same questions'}]
publish(client, user, validate_document(linked))
with SessionLocal() as db:
    stored = content.events_for(db, 'test', 'demo', 'a')
_, directions, tasks = replay_tasks(linked, stored, NOW, POLICY)
assert set(tasks) == {'task-q1', 'task-q3'} and tasks['task-q1']['rating'] == 'independent'
assert not directions['D1']['recalled'] and client.get(BASE).json()['summary']['learned'] == 1
# A link whose direction shares no unchanged question, or that points at an older-policy revision, is refused.
user('admin', True)
nothing = copy.deepcopy(changed); nothing['revision'] = 'v4d'
nothing['equivalences'] = [{'revision': 'v4a', 'from_direction': 'D1', 'to_direction': 'D2', 'reason': 'Wrong link'}]
assert client.post(ADMIN, json=validate_document(nothing)).status_code == 422
legacy_v2 = copy.deepcopy(FIXTURE['result']['document']); legacy_v2['revision'] = 'v2a'
publish(client, user, legacy_v2)
user('admin', True)
from_v2 = copy.deepcopy(changed); from_v2['revision'] = 'v4e'
from_v2['equivalences'] = [{'revision': 'v2a', 'from_direction': 'D1', 'to_direction': 'D1', 'reason': 'Same Q1'}]
response = client.post(ADMIN, json=validate_document(from_v2))
assert response.status_code == 422 and 'root-generation/4' in response.json()['detail'], response.text
print('PASS: /4 tasks of one direction each scheduled, rated independently, direction recalled only when all are, '
      'same-task exposure only, /3 replay unchanged, carry-over by question fingerprint through a reviewed link')
