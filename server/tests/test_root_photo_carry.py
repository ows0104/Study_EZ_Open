"""Photo revision r2 → r3 (docs/changes/2026-11-16-photo-quiz-r3): unchanged questions carry history, edited ones restart.

`scripts/photo_quiz_import.carry_links` links a direction only when its `direction_hash` (question, relation,
answer scope, sources) is unchanged; registration re-checks the same hash. Learning on the earlier revision then
counts on the new one only for those directions."""
import base64
import copy
import hashlib
import struct
import importlib.util
from pathlib import Path

from tests.root_support import setup, publish, start, view, action, document
from studyez_contracts.learning_links.validate import question_hash
from studyez_contracts.roots import document_hash

spec = importlib.util.spec_from_file_location('photo_quiz_import', Path(__file__).resolve().parents[2] / 'scripts/photo_quiz_import.py')
importer = importlib.util.module_from_spec(spec); spec.loader.exec_module(importer)

client, user, SessionLocal = setup()


# Same synthetic photo revision as test_root_photo_import (that module runs on import).
def jpeg(width, height, salt):
    app0 = b'\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, height, width, 1) + b'\x01\x11\x00'
    sos = b'\xff\xda' + struct.pack('>HB', 8, 1) + b'\x01\x00\x00\x3f\x00'
    return b'\xff\xd8' + app0 + sof + sos + bytes([salt % 250, salt // 250]) + b'\xff\xd9'


def photo_document(method, count):
    doc = copy.deepcopy(document())
    doc['revision'] = 'photo-' + method.replace('/', '-')
    review, bank = doc['review'], doc['bank_snapshot']
    source = review['sources'][0]
    source['page_count'] = source.get('page_count') or 10
    review['provenance']['method'] = method
    first = next(q for q in bank['questions'] if q['question_id'] == doc['tasks'][0]['question_id'])
    first['clue'] = '피부. 어린이.'
    stimuli = []
    for i in range(count):
        body = jpeg(3, 2, i)
        stimuli.append({'source_id': source['source_id'], 'source_sha256': source['sha256'], 'page': 1,
                        'crop': [0, 0, 1, 1], 'sha256': hashlib.sha256(body).hexdigest(), 'width': 3, 'height': 2,
                        'png_base64': base64.b64encode(body).decode()})
    first['stimuli'] = stimuli
    review['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in review['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return doc


old = photo_document('photo-import/1', 1)
old['revision'] = 'photo-r2'
new = copy.deepcopy(old)
new['revision'] = 'photo-r3'
bank = new['bank_snapshot']
first_task, second_task = new['tasks'][0], new['tasks'][1]
edited = next(q for q in bank['questions'] if q['question_id'] == first_task['question_id'])
edited['clue'] = '피부. 가운데가 배꼽처럼 들어간 구진.'          # a hint rewrite is a content change
new['review']['bank_sha256'] = document_hash(bank)
by_id = {q['question_id']: q for q in bank['questions']}
for m in new['review']['mappings']:
    m['question_sha256'] = question_hash(by_id[m['question_id']], bank)

new['equivalences'] = importer.carry_links(new, old)
linked = {e['to_direction'] for e in new['equivalences']}
assert first_task['direction_id'] not in linked, 'edited question must not carry'
assert second_task['direction_id'] in linked, 'unchanged question carries'
assert all(e['from_direction'] == e['to_direction'] and e['revision'] == 'photo-r2' for e in new['equivalences'])
print(f'PASS: carry_links links {len(linked)} unchanged directions and skips the edited one')

publish(client, user, old)
sid = start(client)
studied = []
for i in range(2):
    task = view(client, sid)['task']
    studied.append(task['question']['question_id'])
    hashes = [s['sha256'] for s in task['question'].get('stimuli') or []]
    assert action(client, sid, f'rv{i}', 'reveal', attempted=True, **({'stimulusHashes': hashes} if hashes else {})).status_code == 200
    assert action(client, sid, f'rt{i}', 'rate', grade='independent').status_code == 200
assert set(studied) == {first_task['question_id'], second_task['question_id']}, studied

publish(client, user, new)                                       # registration re-checks every link's direction_hash
summary = client.get('/api/root-learning/lectures/test/demo').json()['summary']
assert summary['learned'] == 1, summary['learned']
print('PASS: after r3 is published only the unchanged question keeps its learning history')

broken = copy.deepcopy(new)
broken['revision'] = 'photo-r3b'
broken['equivalences'].append({'revision': 'photo-r2', 'from_direction': first_task['direction_id'],
                               'to_direction': first_task['direction_id'], 'reason': 'ID만 같다'})
user('admin', True)
r = client.post('/api/admin/root-learning/lectures/test/demo', json=broken)
assert r.status_code == 422, (r.status_code, r.text[:200])
print('PASS: a link by ID alone to an edited question is refused at registration')
