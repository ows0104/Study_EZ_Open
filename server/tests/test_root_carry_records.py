"""A replacement revision continues the history of several earlier revisions (docs/changes/2026-11-15-replace-carry-records).

v4a (studied) → v4b (published without links: the 2026-11-15 replacements; studied a little) → v4c links both.
Ratings carry by question fingerprint through the links (R1–R3), and so do 「내 중요도」 and 「이 문제 제외」 (R4),
but never for a question whose content changed.
"""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, publish, NOW, POLICY
client, user, SessionLocal = setup()
from app.models.root_learning import RootEvent
from app.root_learning import content, light
from app.root_learning.state import personal_tiers, replay_tasks
from app.routes.root_generation import carry_sources
from studyez_contracts.learning_links import question_hash
from studyez_contracts.learning_links.validate import LinkValidationError as ValidationError
from studyez_contracts.roots import validate_document, document_hash, task_fingerprints

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def v4_document(revision):
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
    return rehash(doc)


def rehash(doc):
    bank = doc['bank_snapshot']
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return validate_document(doc)


def add(revision, request, kind, payload, at):
    with SessionLocal() as db:
        db.add(RootEvent(user_id='a', request_id=request, session_id='', subject='test', run_id='demo', revision=revision,
                         kind=kind, payload=payload, result={}, created_at=at))
        db.commit()


def rate(doc, revision, task_id, direction_id, at, grade='independent'):
    sha = task_fingerprints(doc)[task_id]
    base = {'task_id': task_id, 'direction_id': direction_id, 'question_sha256': sha, 'policy': POLICY}
    add(revision, f'reveal-{revision}-{task_id}', 'reveal', {**base, 'attempted': True}, at)
    add(revision, f'rate-{revision}-{task_id}', 'rate', {**base, 'grade': grade, 'helped': False, 'exam_date': '2026-11-07'},
        at + timedelta(seconds=1))


def tier(revision, question_id, chosen, at, seq):
    add(revision, f'tier-{revision}-{question_id}', 'tier',
        {'question_id': question_id, 'tier': chosen, 'originalTier': 'Core', 'seq': seq}, at)


v4a = v4_document('v4a')
publish(client, user, v4a)
t0 = NOW - timedelta(days=3)
rate(v4a, 'v4a', 'task-q1', 'D1', t0)
tier('v4a', 'Q2', 'Essential', t0, 1)
tier('v4a', 'Q4', 'Optional', t0, 2)
add('v4a', 'exclude-v4a-Q3', 'exclude', {'task_id': 'task-q3', 'direction_id': 'D1', 'question_id': 'Q3',
                                          'question_sha256': task_fingerprints(v4a)['task-q3']}, t0)

v4b = copy.deepcopy(v4a); v4b['revision'] = 'v4b'
publish(client, user, validate_document(v4b))      # the replacement that linked nothing
rate(v4b, 'v4b', 'task-q2', 'D2', NOW - timedelta(days=1))

# R2: the request packet lists every reviewed /4 revision, oldest first, with (direction, fingerprint) per task.
with SessionLocal() as db:
    sources = carry_sources(db, 'test', 'demo')
assert [s['revision'] for s in sources] == ['v4a', 'v4b'], sources
assert sources[0]['tasks'][0] == {'direction_id': 'D1', 'fingerprint': task_fingerprints(v4a)['task-q1']}

# The links the generator writes (tests/quizbank/test_connection_replace.py): per (revision, direction). Q4 is reworded in v4c.
v4c = v4_document('v4c')
next(q for q in v4c['bank_snapshot']['questions'] if q['question_id'] == 'Q4')['answer'] = 'Reworded part 4'
v4c = rehash(v4c)
links = [{'revision': r, 'from_direction': d, 'to_direction': d, 'reason': 'same questions'} for r in ('v4a', 'v4b') for d in ('D1', 'D2')]
v4c['equivalences'] = links

# R3: one new direction may continue several revisions; one revision still links a direction once.
validate_document(v4c)
twice = copy.deepcopy(v4c); twice['equivalences'].append({**links[0]})
try:
    validate_document(twice); raise AssertionError('duplicate (revision, direction) link accepted')
except ValidationError:
    pass
publish(client, user, v4c)

with SessionLocal() as db:
    events = content.events_for(db, 'test', 'demo', 'a')
    light.clear()
    row = light.revision_row(db, 'test', 'demo', 'v4c')
    carried = row.document.carried_questions
    _, directions, tasks = replay_tasks(row.document, events, NOW, POLICY)
    tiers = personal_tiers(row.document, events)
    stored_tiers = content.tiers_for(db, row, 'a')
    excluded = content.excluded_ids(events, 'v4c', carried)
# Ratings: task-q1 from v4a and task-q2 from v4b both continue on v4c.
assert tasks['task-q1']['rating'] == 'independent' and tasks['task-q2']['rating'] == 'independent', tasks
assert 'task-q4' not in tasks
# R4: unchanged questions carry choices, the reworded Q4 does not; ID alone never carries.
assert carried[('v4a', 'Q2')] == 'Q2' and ('v4a', 'Q4') not in carried, carried
assert tiers == {'Q2': {'tier': 'Essential', 'originalTier': 'Core'}} == stored_tiers, (tiers, stored_tiers)
assert excluded == {'Q3'}
assert personal_tiers(copy.deepcopy(dict(row.document)), events) == {}   # a plain document has no carry table
# A later choice on the new revision wins over the carried one.
tier('v4c', 'Q2', None, NOW, 3)
with SessionLocal() as db:
    assert personal_tiers(row.document, content.events_for(db, 'test', 'demo', 'a')) == {}
print('PASS: replacement links several earlier revisions; ratings, 내 중요도 and 제외 carry by question fingerprint only')
