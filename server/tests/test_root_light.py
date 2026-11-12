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
from sqlalchemy import event, func
from app.database import engine
from app.models.root_learning import RootEvent
from app.lecture_mastery import lecture_overviews
from app.auth import CurrentUser
from app.root_learning import light, planning, state
from app.root_learning.score import lecture_score
from studyez_contracts.learning_links import question_hash
from studyez_contracts.roots import validate_document, document_hash, task_fingerprints

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/root_generation_v2_import.json').read_text(encoding='utf-8'))


def v4_document(revision, shape=None):
    doc = copy.deepcopy(FIXTURE['result']['document'])
    doc.update(generation_policy='root-generation/4', revision=revision)
    if shape:
        shape(doc)
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

# 3. The cache reads the stored light copy once per revision (never the original); a new revision makes a new entry.
light.clear()
publish(client, user, v4_document('C1'))
reads, originals = [], []
listener = lambda conn, cur, stmt, params, ctx, many: reads.append(stmt) if 'root_content.light' in stmt else None
whole = lambda conn, cur, stmt, params, ctx, many: originals.append(stmt) if 'root_content.document' in stmt else None
event.listen(engine, 'before_cursor_execute', listener)
event.listen(engine, 'before_cursor_execute', whole)
try:
    with SessionLocal() as db:
        first = light.current_rows(db, [('test', 'demo')])
    with SessionLocal() as db:
        again = light.current_rows(db, [('test', 'demo'), ('test', 'missing')])
    assert len(reads) == 1, reads                                                       # second call: digest only
    assert first[('test', 'demo')].document is again[('test', 'demo')].document and set(again) == {('test', 'demo')}
    publish(client, user, v4_document('C2'))                                            # admin publish checks the original
    reads.clear(); originals.clear()
    with SessionLocal() as db:
        newer = light.current_rows(db, [('test', 'demo')])
    assert newer[('test', 'demo')].revision == 'C2' and len(reads) == 1
    assert originals == [], originals                                                   # the 6–12 MB original: never
finally:
    event.remove(engine, 'before_cursor_execute', listener)
    event.remove(engine, 'before_cursor_execute', whole)

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
# 6. Startup warm-up (2026-11-12): the instance builds every enabled lecture's copy before taking requests,
#    so the first list request reads no original document.
import threading
from app import main as app_main
reads.clear()
event.listen(engine, 'before_cursor_execute', listener)
try:
    light.clear()
    with SessionLocal() as db:
        assert light.warm(db)[0] == 1
    assert len(reads) == 1
    reads.clear()
    assert client.get('/api/root-learning').json()['lectures'][0]['runId'] == 'demo' and reads == []
    light.clear()
    app_main.warm_main_quiz()                                                          # the lifespan hook itself
    assert len(reads) == 1 and len(light._cache) == 1
    # 7. Concurrent cold requests read the original once, not once each (the 512 MiB crashes).
    light.clear(); reads.clear()
    gate, got = threading.Barrier(4), []
    def cold():
        gate.wait()
        with SessionLocal() as db:
            got.append(set(light.current_rows(db, [('test', 'demo')])))
    workers = [threading.Thread(target=cold) for _ in range(4)]
    [w.start() for w in workers]; [w.join() for w in workers]
    assert got == [{('test', 'demo')}] * 4, got                                         # every request answered
    assert len(reads) == 1, len(reads)
finally:
    event.remove(engine, 'before_cursor_execute', listener)
# A lecture whose copy fails is skipped and logged; the rest are still built.
real_from_stored = light.from_stored
light.from_stored = lambda value: (_ for _ in ()).throw(ValueError('broken copy'))
try:
    light.clear()
    with SessionLocal() as db:
        assert light.warm(db)[0] == 0
finally:
    light.from_stored = real_from_stored
with SessionLocal() as db:
    assert light.warm(db)[0] == 1

# 8. Storage (2026-11-12): a new revision stores its light copy and its images by sha256. Every learner path
#    reads the light copy only; the shown question gets its bytes back, equal to the original question.
import base64, hashlib, struct, zlib
from sqlalchemy import select as sql_select
from app import bank_personal, cli
from app.models.root_learning import RootContent, RootImage
from app.routes import root_learning as routes


def png(width, color):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b'\x00' + color * width
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


RED, BLUE = png(2, b'\xff\x00\x00'), png(3, b'\x00\x00\xff')


def pictures(doc):
    source = doc['review']['sources'][0]
    source['page_count'] = 3
    def stim(body, width):
        return {'source_id': source['source_id'], 'source_sha256': source['sha256'], 'page': 1, 'crop': [0, 0, 1, 1],
                'sha256': hashlib.sha256(body).hexdigest(), 'width': width, 'height': 1,
                'png_base64': base64.b64encode(body).decode()}
    q1, q2 = doc['bank_snapshot']['questions'][:2]
    q1['stimuli'] = [stim(RED, 2)]
    q2['stimuli'] = [stim(RED, 2), stim(BLUE, 3)]                                       # RED twice: one image row


light.clear()
publish(client, user, v4_document('P1', pictures))
with SessionLocal() as db:
    stored_row = db.get(RootContent, ('test', 'demo', 'P1'))
    original = copy.deepcopy(stored_row.document)
    assert stored_row.light == light.stored(original)                                  # filled on insert
    assert all('png_base64' not in s for q in stored_row.light['document']['bank_snapshot']['questions']
               for s in q.get('stimuli', []))
    assert stored_row.light['task_fingerprints'] == task_fingerprints(original)        # from the original (with bytes)
    images = dict(db.execute(sql_select(RootImage.sha256, RootImage.png_base64)).all())
assert images == light.images_of(original) and len(images) == 2
by_id = {q['question_id']: q for q in original['bank_snapshot']['questions']}

# Solving end to end reads no original document.
originals.clear()
event.listen(engine, 'before_cursor_execute', whole)
try:
    sid = start(client, 'p-start')
    shown = view(client, sid)['task']
    assert client.get('/api/root-learning/sessions/' + sid + '/prepare').status_code == 200
    revealed = action(client, sid, 'p-r1', 'reveal', attempted=True, stimulusHashes=[i['sha256'] for i in shown['question']['stimuli']])
    assert revealed.status_code == 200, revealed.text
    assert action(client, sid, 'p-g1', 'rate', grade='independent').status_code == 200
    personal = client.get(BASE + '/questions/Q2/personal').json()
    assert client.get(BASE).status_code == 200
    assert originals == [], originals
finally:
    event.remove(engine, 'before_cursor_execute', whole)
want = by_id[shown['question']['question_id']]
assert [i['url'] for i in shown['question']['stimuli']] == ['data:image/png;base64,' + s['png_base64'] for s in want['stimuli']]
# Personal edits and reports compare the whole question: the same revision token as the original question.
assert personal['revision'] == bank_personal.revision(by_id['Q2'])
with SessionLocal() as db:
    doc = light.revision_row(db, 'test', 'demo', 'P1')
    assert routes.snapshot_question(db, doc, 'Q2') == by_id['Q2']
    front = routes.learner_front(doc, dict(by_id['Q2']), db)
    assert [i['sha256'] for i in front['stimuli']] == [s['sha256'] for s in by_id['Q2']['stimuli']]
    # The rate event carries the original's fingerprint, not one computed from the light copy.
    rated = db.scalars(sql_select(RootEvent).where(RootEvent.request_id == 'p-g1')).one()
    assert rated.payload['question_sha256'] == task_fingerprints(original)[rated.payload['task_id']]
    # Nothing a request did changed the shared cached copy.
    assert dict(doc.document) == light.stored(original)['document']

# A row stored before this change (no light copy, no image rows) still works from the original, and the
# backfill command fills it exactly as an insert would. A second run has nothing to do.
with SessionLocal() as db:
    db.get(RootContent, ('test', 'demo', 'P1')).light = None
    db.query(RootImage).delete()
    db.commit()
light.clear()
with SessionLocal() as db:
    doc = light.revision_row(db, 'test', 'demo', 'P1')
    assert routes.snapshot_question(db, doc, 'Q2') == by_id['Q2']                      # bytes from the original
cli.main_quiz_light(apply=False)
with SessionLocal() as db:
    assert db.get(RootContent, ('test', 'demo', 'P1')).light is None                   # dry run changes nothing
cli.main_quiz_light(apply=True)
with SessionLocal() as db:
    refilled = db.get(RootContent, ('test', 'demo', 'P1'))
    assert refilled.document == original, 'original changed'                         # original untouched
    assert refilled.light == light.stored(original), (refilled.light is None, type(refilled.light), set(refilled.light or {}), refilled.light and refilled.light['task_fingerprints'] == light.stored(original)['task_fingerprints'])
    assert dict(db.execute(sql_select(RootImage.sha256, RootImage.png_base64)).all()) == images
    assert db.scalar(sql_select(func.count()).select_from(RootContent).where(RootContent.light.is_(None))) == 0

print('PASS: stored light copy and images filled on insert; solving reads no original; shown question and personal '
      'revision equal the original; fingerprints from the original; unfilled rows fall back; backfill fills exactly; '
      'startup warm-up builds every enabled copy; concurrent cold requests read once; '
      'light documents drop only image bytes and keep original fingerprints; learner state equal; '
      'fingerprints only for earlier-revision events; one document read per revision; a failing lecture is skipped')
