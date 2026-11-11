"""Lecture-list card columns for Main-Quiz, per question (docs/changes/2026-11-11-main-quiz-list-columns).

unseen + recognized + retrieving + retained == total; 「저장」 needs Good/Easy on two study days and
mastery now >= the rating's target retention; 「복습」 is today's plan's '복습 확인' count.
"""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, publish, document, POLICY, NOW
client, user, SessionLocal = setup()
from app.root_learning.planning import plan
from app.root_learning.policy import target_parameters
from app.root_learning.state import question_progress, replay
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash

STAGES = ('unseen', 'recognized', 'retrieving', 'retained')
PARAMS = target_parameters()
counter = [0]


def progress(doc, events, available, when):
    result = question_progress(doc, events, available, when, POLICY, plan(doc, events, available, when, POLICY))
    assert sum(result[k] for k in STAGES) == result['total'], result
    return result


def reveal(task, direction, at, revision='v1'):
    counter[0] += 1
    return {'id': f'reveal-{counter[0]}', 'kind': 'reveal', 'revision': revision, 'at': at,
            'payload': {'task_id': task, 'direction_id': direction, 'attempted': True, 'policy': POLICY}}


def rate(task, direction, at, rating='Easy', revision='v1', helped=False):
    counter[0] += 1
    grade = {'Again': 'missed', 'Hard': 'partial', 'Good': 'independent', 'Easy': 'independent'}[rating]
    return {'id': f'rate-{counter[0]}', 'kind': 'rate', 'revision': revision, 'at': at + timedelta(seconds=1),
            'payload': {'task_id': task, 'direction_id': direction, 'grade': grade, 'helped': helped, 'policy': POLICY,
                        'exam_date': '2026-12-31', 'selfRating': rating, 'targetParameters': PARAMS}}


# --- Older documents: per-direction state, one served question per direction ---------------------
doc = document()
doc['exam_date'] = '2026-12-31'
doc['tasks'].append({'task_id': 'task4', 'question_id': 'Q1', 'direction_id': 'D1'})  # never served: D1 has task1
available = {'task1', 'task2', 'task3', 'task4'}

empty = progress(doc, [], available, NOW)
assert empty == {'total': 3, 'unseen': 3, 'recognized': 0, 'retrieving': 0, 'retained': 0, 'reviewDue': 0}, empty
assert progress(doc, [], {'task1', 'task2'}, NOW)['total'] == 2  # not prepared: left out like suspended cards

events = [reveal('task1', 'D1', NOW)]
assert progress(doc, events, available, NOW + timedelta(minutes=1))['recognized'] == 1  # seen, not rated

events += [rate('task1', 'D1', NOW, 'Hard')]
assert progress(doc, events, available, NOW + timedelta(minutes=1))['recognized'] == 1  # last not Good/Easy

# Many Easy results on one study day: mastery may pass the target, but one day is not 「저장」.
day1 = list(events)
for i in range(12):
    day1 += [rate('task1', 'D1', NOW + timedelta(minutes=2 + i), 'Easy')]
_, values = replay(doc, day1, NOW + timedelta(hours=1), POLICY)
assert values['D1']['mastery'] >= values['D1']['target'], values['D1']
one_day = progress(doc, day1, available, NOW + timedelta(hours=1))
assert one_day['retrieving'] == 1 and one_day['retained'] == 0, one_day

# A second study day with Easy, mastery above target -> 「저장」.
day2 = day1 + [rate('task1', 'D1', NOW + timedelta(days=1), 'Easy')]
two_days = progress(doc, day2, available, NOW + timedelta(days=1, hours=1))
assert two_days['retained'] == 1 and two_days['unseen'] == 2, two_days

# Forgetting: long after, mastery now falls below the target -> back to 「인출」.
later = progress(doc, day2, available, NOW + timedelta(days=200))
assert later['retained'] == 0 and later['retrieving'] == 1, later

# An undone rating does not count; a helped Good is not Good (graded partial).
undo = {'id': 'undo-last', 'kind': 'undo', 'revision': 'v1', 'at': NOW + timedelta(days=1, seconds=5),
        'payload': {'undo': day2[-1]['id']}}
assert progress(doc, day2 + [undo], available, NOW + timedelta(days=1, hours=1))['retained'] == 0
helped = [reveal('task2', 'D2', NOW), rate('task2', 'D2', NOW, 'Good', helped=True)]
assert progress(doc, helped, available, NOW + timedelta(minutes=5))['recognized'] == 1

# Ratings without a target (before 2026-11-09) never count as 「저장」.
legacy = [reveal('task3', 'D3', NOW), {'id': 'legacy-a', 'kind': 'rate', 'revision': 'v1', 'at': NOW + timedelta(seconds=1),
          'payload': {'task_id': 'task3', 'direction_id': 'D3', 'grade': 'independent', 'helped': False, 'policy': POLICY}},
          {'id': 'legacy-b', 'kind': 'rate', 'revision': 'v1', 'at': NOW + timedelta(days=3),
          'payload': {'task_id': 'task3', 'direction_id': 'D3', 'grade': 'independent', 'helped': False, 'policy': POLICY}}]
assert progress(doc, legacy, available, NOW + timedelta(days=3, hours=1))['retrieving'] == 1

# 「복습」 = today's plan '복습 확인': rated and due; unseen questions are never review.
due_at = NOW + timedelta(days=60)
review = progress(doc, day2, available, due_at)
expected = sum(t['reason'] == '복습 확인' for t in plan(doc, day2, available, due_at, POLICY)['tasks'])
assert review['reviewDue'] == expected == 1 and review['unseen'] == 2, review
assert progress(doc, day2, available, NOW + timedelta(days=1, hours=1))['reviewDue'] == 0  # assessed today

# --- root-generation/4: every prepared task is its own question ------------------------------------
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))
v4 = copy.deepcopy(FIXTURE['result']['document'])
v4.update(generation_policy='root-generation/4', revision='v4a')
bank = v4['bank_snapshot']
for i in (3, 4):
    q = copy.deepcopy(bank['questions'][0])
    q.update(question_id=f'Q{i}', question=f'Synthetic part {i} of goal 1?', answer=f'Secret part {i}', answer_units=[f'Secret part {i}'])
    bank['questions'].append(q)
    m = copy.deepcopy(v4['review']['mappings'][0]); m['question_id'] = f'Q{i}'
    v4['review']['mappings'].append(m)
v4['tasks'] = [{'task_id': 'task-q1', 'question_id': 'Q1', 'direction_id': 'D1'},
               {'task_id': 'task-q3', 'question_id': 'Q3', 'direction_id': 'D1'},
               {'task_id': 'task-q4', 'question_id': 'Q4', 'direction_id': 'D1'},
               {'task_id': 'task-q2', 'question_id': 'Q2', 'direction_id': 'D2'}]
v4['review']['bank_sha256'] = document_hash(bank)
by_id = {q['question_id']: q for q in bank['questions']}
for m in v4['review']['mappings']:
    m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
v4 = validate_document(v4)
every = {t['task_id'] for t in v4['tasks']}
assert progress(v4, [], every, NOW)['total'] == 4  # three questions on D1 are three rows
v4_events = [reveal('task-q1', 'D1', NOW, 'v4a'), rate('task-q1', 'D1', NOW, 'Good', 'v4a')]
one = progress(v4, v4_events, every, NOW + timedelta(minutes=1))
assert one['retrieving'] == 1 and one['unseen'] == 3, one  # siblings on the same direction are untouched

# --- API: the list's catalog carries the counts next to the unchanged summary ----------------------
publish(client, user)
response = client.get('/api/root-learning')
assert response.status_code == 200, response.text
row = response.json()['lectures'][0]
assert row['questionProgress'] == {'total': 3, 'unseen': 3, 'recognized': 0, 'retrieving': 0, 'retained': 0, 'reviewDue': 0}, row
assert row['summary']['total'] == 3
print('PASS: per-question stages, two-day and target rule, forgetting, undo/help/legacy, plan review count, v4 tasks, catalog field')
