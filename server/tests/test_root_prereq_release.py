"""복습에서 선행 목표 풀어 주기(docs/changes/2026-11-15-tree-edge-goals spec R2).

선행 목표(T1, 존재 목표)를 배웠더라도 평가가 independent가 아니면, 세부 목표(T2)가 계획에 오를 때 T1을 앞에 끌어온다.
모두 independent면 풀어 준다. 오늘 이미 푼 T1은 다시 끌어오지 않는다. 중요도 필터(focus) 밖의 T1도 끌어온다.
"""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, POLICY, NOW
setup()
from app.root_learning.planning import plan
from studyez_contracts.roots import validate_document, document_hash
from studyez_contracts.learning_links import question_hash

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def two_goal_document(prerequisite=True):
    """T1(D1: Q1·Q3·Q4) → T2(D2: Q2). 계획만 보므로 선행 간선은 검증 뒤에 붙인다."""
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision='v4a', exam_date=None)
    bank = doc['bank_snapshot']
    for i in (3, 4):
        q = copy.deepcopy(bank['questions'][0])
        q.update(question_id=f'Q{i}', question=f'Synthetic part {i} of goal 1?', answer=f'Secret part {i}', answer_units=[f'Secret part {i}'])
        bank['questions'].append(q)
        m = copy.deepcopy(doc['review']['mappings'][0]); m['question_id'] = f'Q{i}'
        doc['review']['mappings'].append(m)
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    doc['tasks'] = [{'task_id': 'task-q1', 'question_id': 'Q1', 'direction_id': 'D1'},
                    {'task_id': 'task-q3', 'question_id': 'Q3', 'direction_id': 'D1'},
                    {'task_id': 'task-q4', 'question_id': 'Q4', 'direction_id': 'D1'},
                    {'task_id': 'task-q2', 'question_id': 'Q2', 'direction_id': 'D2'}]
    doc = validate_document(doc)
    goal = doc['review']['targets'][0]
    first, second = copy.deepcopy(goal), copy.deepcopy(goal)
    first.update(target_id='T1', directions=[d for d in goal['directions'] if d['direction_id'] == 'D1'])
    second.update(target_id='T2', directions=[d for d in goal['directions'] if d['direction_id'] == 'D2'])
    doc['review']['targets'] = [first, second]
    doc['adopted_target_ids'] = ['T1', 'T2']
    doc['prerequisites'] = [{'before_target': 'T1', 'after_target': 'T2', 'relation_id': 'R1'}] if prerequisite else []
    return doc


def rated(task_id, direction_id, at, grade):
    return [{'id': 'reveal-' + task_id + str(at), 'kind': 'reveal', 'revision': 'v4a', 'at': at,
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'attempted': True, 'policy': POLICY}},
            {'id': 'rate-' + task_id + str(at), 'kind': 'rate', 'revision': 'v4a', 'at': at + timedelta(seconds=1),
             'payload': {'task_id': task_id, 'direction_id': direction_id, 'grade': grade, 'helped': False,
                         'policy': POLICY, 'exam_date': None}}]


EXISTENCE = ['task-q1', 'task-q3', 'task-q4']


def studied(*grades, at=NOW):
    events = []
    for i, (task_id, grade) in enumerate(zip(EXISTENCE, grades)):
        events += rated(task_id, 'D1', at + timedelta(seconds=10 * i), grade)
    return events


def ids(result):
    return [(t['task_id'], t['reason']) for t in result['tasks']]


doc = two_goal_document()
every = {t['task_id'] for t in doc['tasks']}
later = NOW + timedelta(days=1, minutes=5)
focus = {'task-q2'}  # 오늘 학습 중요도 필터: 세부 목표만 남았다

# 1. 존재 목표를 틀렸다(missed가 하나라도): 필터 밖이어도 세부 앞에 끌어온다.
pulled = ids(plan(doc, studied('independent', 'missed', 'independent'), every, later, POLICY, focus=focus))
assert pulled[-1] == ('task-q2', '새 목표'), pulled
assert {t for t, _ in pulled[:-1]} == set(EXISTENCE) and all(r == '명시적 선행 연결' for _, r in pulled[:-1]), pulled

# 2. partial도 끌어온다.
pulled = ids(plan(doc, studied('partial', 'independent', 'independent'), every, later, POLICY, focus=focus))
assert [t for t, _ in pulled] == EXISTENCE + ['task-q2'], pulled

# 3. 모두 쉽게 맞혔다: 풀어 준다(세부만).
released = ids(plan(doc, studied('independent', 'independent', 'independent'), every, later, POLICY, focus=focus))
assert released == [('task-q2', '새 목표')], released

# 4. 오늘 이미 푼 존재 목표는 틀렸어도 다시 끌어오지 않는다.
today = ids(plan(doc, studied('missed', 'missed', 'missed', at=later - timedelta(minutes=3)), every, later, POLICY, focus=focus))
assert today == [('task-q2', '새 목표')], today

# 5. 안 배운 선행은 지금처럼 끌어온다.
fresh = ids(plan(doc, [], every, later, POLICY, focus=focus))
assert [t for t, _ in fresh] == EXISTENCE + ['task-q2'], fresh

# 6. 선행 연결이 없는 판은 이전과 같다: 존재 목표를 틀렸어도 필터 밖이면 오지 않는다.
plain = two_goal_document(prerequisite=False)
assert ids(plan(plain, studied('missed', 'missed', 'missed'), every, later, POLICY, focus=focus)) == [('task-q2', '새 목표')]

print('PASS: 선행 목표는 쉽게 맞혔을 때만 복습에서 풀어 주고, 틀렸으면 필터 밖이어도 세부 앞에 끌어온다; 오늘 푼 것은 다시 끌어오지 않는다')
