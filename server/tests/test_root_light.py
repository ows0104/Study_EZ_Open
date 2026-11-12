"""Light Main-Quiz documents for learning rates and the lecture list (docs/changes/2026-11-12-review-bar-ux).

- Fingerprints are computed only when an earlier revision's event must be carried, and a light document carries
  the fingerprints of the original (with image bytes), so carry-over is unchanged.
- A light document drops only `png_base64`; every learner-state result equals the original's.
- The per-revision cache reads the full document once; a new revision makes a new entry.
- One lecture whose overview fails no longer turns the whole list into a 500.
"""
import copy
import json
from datetime import timedelta
from pathlib import Path
from tests.root_support import setup, publish, start, view, action, POLICY, NOW, BASE, ADMIN
client, user, SessionLocal = setup()
from sqlalchemy import event
from app.database import engine
from app.lecture_mastery import lecture_overviews
from app.auth import CurrentUser
from app.root_learning import light, planning, state
from app.root_learning.score import lecture_score
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash, task_fingerprints

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def v4_document(revision):
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision=revision)
    bank = doc['bank_snapshot']
    doc['review']['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in doc['review']['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return validate_document(doc)


def with_image(doc):
    """Images are renderer-owned; give one question a stimulus with bytes, as published documents have."""
    doc = copy.deepcopy(doc)
    doc['bank_snapshot']['questions'][0]['stimuli'] = [
        {'source_id': 'S1', 'page': 3, 'sha256': 'a' * 64, 'source_sha256': 'b' * 64, 'width': 10, 'height': 10,
         'crop': [0, 0, 1, 1], 'png_base64': 'iVBORw0KGgo' * 40000}]
    return doc


# 1. lighten keeps everything but the image bytes, and the original's fingerprints.
full = with_image(v4_document('L1'))
small = light.lighten(full)
stim = small['bank_snapshot']['questions'][0]['stimuli'][0]
assert 'png_base64' not in stim and stim['sha256'] == 'a' * 64 and stim['crop'] == [0, 0, 1, 1]
assert 'png_base64' in full['bank_snapshot']['questions'][0]['stimuli'][0]          # original untouched
assert small.task_fingerprints == task_fingerprints(full) != task_fingerprints(dict(small))
assert {k: v for k, v in small.items() if k != 'bank_snapshot'} == {k: v for k, v in full.items() if k != 'bank_snapshot'}
assert len(json.dumps(small)) < len(json.dumps(full)) / 2

# 2. Learner-state results equal the original's, including carry-over from an earlier revision by fingerprint.
task = full['tasks'][0]
old = full['revision'] + '-old'
prints = task_fingerprints(full)
events = [
    {'id': 'r0', 'kind': 'reveal', 'revision': old, 'at': NOW - timedelta(days=2),
     'payload': {'task_id': 'gone', 'direction_id': task['direction_id'], 'attempted': True, 'policy': POLICY,
                 'question_sha256': prints[task['task_id']]}},
    {'id': 'g0', 'kind': 'rate', 'revision': old, 'at': NOW - timedelta(days=2) + timedelta(seconds=1),
     'payload': {'task_id': 'gone', 'direction_id': task['direction_id'], 'grade': 'independent', 'helped': False,
                 'policy': POLICY, 'exam_date': '2026-11-07', 'question_sha256': prints[task['task_id']]}}]
linked = copy.deepcopy(full)
linked['equivalences'] = [{'revision': old, 'from_direction': task['direction_id'], 'to_direction': task['direction_id'],
                           'reason': 'same'}]
linked_small = light.lighten(linked)
available = {t['task_id'] for t in linked['tasks']}
_, _, carried = state.replay_tasks(linked, events, NOW, POLICY)
assert carried[task['task_id']]['rating'] == 'independent'                            # history carried
for fn in (lambda d: state.replay_tasks(d, events, NOW, POLICY),
           lambda d: state.summary(d, events, available, NOW, POLICY),
           lambda d: state.question_progress(d, events, available, NOW, POLICY),
           lambda d: lecture_score(d, events, POLICY, NOW),
           lambda d: planning.plan(d, events, available, NOW, POLICY)):
    assert fn(linked) == fn(linked_small)
# Without an earlier revision's event, fingerprints are never computed.
calls = []
import studyez_contracts.roots as roots_pkg
state_fp = roots_pkg.task_fingerprints
roots_pkg.task_fingerprints = lambda d: calls.append(1) or state_fp(d)
try:
    state.replay_tasks(full, [e | {'revision': full['revision'], 'payload': {**e['payload'], 'task_id': task['task_id']}}
                              for e in events], NOW, POLICY)
    assert calls == []
    state.replay_tasks(linked, events, NOW, POLICY)
    assert calls == [1]                                                                 # once per replay, lazily
finally:
    roots_pkg.task_fingerprints = state_fp

# 3. The cache reads the full document once per revision; a new revision makes a new entry.
light.clear()
publish(client, user, v4_document('C1'))
reads = []
listener = lambda conn, cur, stmt, params, ctx, many: reads.append(stmt) if 'root_content.document' in stmt else None
event.listen(engine, 'before_cursor_execute', listener)
try:
    with SessionLocal() as db:
        first = light.current_rows(db, [('test', 'demo')])
    with SessionLocal() as db:
        again = light.current_rows(db, [('test', 'demo'), ('test', 'missing')])
    assert len(reads) == 1, reads                                                       # second call: digest only
    assert first[('test', 'demo')].document is again[('test', 'demo')].document and set(again) == {('test', 'demo')}
    publish(client, user, v4_document('C2'))
    reads.clear()
    with SessionLocal() as db:
        newer = light.current_rows(db, [('test', 'demo')])
    assert newer[('test', 'demo')].revision == 'C2' and len(reads) == 1
finally:
    event.remove(engine, 'before_cursor_execute', listener)

# 4. Calendar learning rate and the lecture list use the light rows and still answer.
sid = start(client)
assert action(client, sid, 'r1', 'reveal', attempted=True).status_code == 200
assert action(client, sid, 'g1', 'rate', grade='independent').status_code == 200
listing = client.get('/api/root-learning')
assert listing.status_code == 200 and [l['runId'] for l in listing.json()['lectures']] == ['demo']
with SessionLocal() as db:
    rates = lecture_overviews(db, CurrentUser(id='a', email='a@example.com', is_admin=False), [('test', 'demo')], at=NOW)
assert rates[('test', 'demo')]['mastery'] is not None
assert listing.json()['lectures'][0]['summary']['score'] == rates[('test', 'demo')]['mastery']['score']

# 5. One lecture's failing overview leaves it out of the list instead of failing the list.
real_plan = planning.plan
planning.plan = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('Prepared prerequisite became unavailable'))
try:
    broken = client.get('/api/root-learning')
    assert broken.status_code == 200 and broken.json()['lectures'] == [], broken.text
finally:
    planning.plan = real_plan
assert client.get('/api/root-learning').json()['lectures'][0]['runId'] == 'demo'
print('PASS: light documents drop only image bytes and keep original fingerprints; learner state equal; '
      'fingerprints only for earlier-revision events; one document read per revision; a failing lecture is skipped')
