"""모아풀기 분류(docs/changes/2026-11-18-mix-options R1)의 root-generation/4 판: 과제마다 따로 센다.

운영 강의는 /4다. 한 방향(D1)을 세 문항이 묻는다 — 한 과제를 풀어도 같은 방향의 다른 과제는 미열람이다."""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, POLICY, NOW
client, user, SessionLocal = setup()
from app.root_learning import mix
from app.root_learning.policy import study_day
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def v4_document():
    """test_root_learning_v4와 같은 모양: D1에 과제 셋(Q1·Q3·Q4), D2에 하나(Q2)."""
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision='v4a')
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
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return validate_document(doc)


def rated(task_id, direction_id, at, grade='independent'):
    return [{'id': 'reveal-' + task_id + str(at), 'kind': 'reveal', 'revision': 'v4a', 'at': at,
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'attempted': True, 'policy': POLICY}},
            {'id': 'rate-' + task_id + str(at), 'kind': 'rate', 'revision': 'v4a', 'at': at + timedelta(seconds=1),
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'grade': grade, 'helped': False,
                         'policy': POLICY, 'exam_date': '2026-11-07'}}]


doc = v4_document()
every = {t['task_id'] for t in doc['tasks']}
assert mix.classify(doc, [], every, NOW, POLICY) == dict.fromkeys(['task-q1', 'task-q3', 'task-q4', 'task-q2'], 'unseen')

# task-q1 rated today: later. Its siblings on D1 stay unseen (per task, not per direction).
events = rated('task-q1', 'D1', NOW - timedelta(minutes=5))
today = mix.classify(doc, events, every, NOW, POLICY)
assert today == {'task-q1': 'later', 'task-q3': 'unseen', 'task-q4': 'unseen', 'task-q2': 'unseen'}, today

# A reveal without a rating today: later today, due on a later study day.
events += [{'id': 'reveal-q3', 'kind': 'reveal', 'revision': 'v4a', 'at': NOW - timedelta(minutes=2),
            'payload': {'task_id': 'task-q3', 'direction_id': 'D1', 'attempted': True, 'policy': POLICY}}]
assert mix.classify(doc, events, every, NOW, POLICY)['task-q3'] == 'later'
later = NOW + timedelta(days=60)
assert study_day(later, POLICY) != study_day(NOW, POLICY)
after = mix.classify(doc, events, every, later, POLICY)
assert after == {'task-q1': 'due', 'task-q3': 'due', 'task-q4': 'unseen', 'task-q2': 'unseen'}, after

# Unavailable tasks are not counted; selection keeps the document's task order.
assert 'task-q4' not in mix.classify(doc, events, every - {'task-q4'}, later, POLICY)
tiers = dict.fromkeys(every, 'Core')
picked = mix.select(doc, after, tiers, ['Core'], unseen=True, ignore_schedule=False)
assert [t['task_id'] for t in picked] == ['task-q1', 'task-q3', 'task-q4', 'task-q2']
assert [t['task_id'] for t in mix.select(doc, after, tiers, ['Core'], unseen=False, ignore_schedule=False)] == ['task-q1', 'task-q3']
assert mix.select(doc, after, tiers, ['Essential'], unseen=True, ignore_schedule=True) == []
assert mix.counts(after, tiers)['Core'] == {'unseen': 2, 'due': 2, 'later': 0}

print('root mix v4: ok')
