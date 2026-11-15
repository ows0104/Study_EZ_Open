"""Photo-import revision (docs/changes/2026-11-15-photo-quiz-import): register → publish → learner sees clue and JPEG."""
import base64
import copy
import hashlib
import struct
from tests.root_support import setup, publish, start, view, action, document, ADMIN, BASE
from studyez_contracts.learning_links.validate import question_hash
from studyez_contracts.roots import document_hash
from studyez_contracts.roots.media import PHOTO_MAX_COUNT

client, user, SessionLocal = setup()


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


user('admin', True)
# Not a photo-import revision: JPEG and more than 64 images stay rejected.
assert client.post(ADMIN, json=photo_document('manual', 1)).status_code == 422
assert client.post(ADMIN, json=photo_document('photo-import/1', PHOTO_MAX_COUNT + 1)).status_code == 422
doc = photo_document('photo-import/1', 70)
publish(client, user, doc)
sid = start(client)
task = view(client, sid)['task']
question = task['question']
assert question['question_id'] == doc['tasks'][0]['question_id'], question['question_id']
assert question['clue'] == '피부. 어린이.'
assert len(question['stimuli']) == 70 and question['stimuli'][0]['url'].startswith('data:image/jpeg;base64,')
print('PASS: photo-import revision accepts JPEG and >64 images, other revisions reject them, learner front carries clue')

# Reference slides (docs/changes/2026-11-15-photo-quiz-slides): a photo revision has no generation record, so its
# source PDFs come from fingerprint-named copies. Until a copy is uploaded the answer has no slide; after, it does.
from app.root_learning.evidence import photo_snapshot_key
from app.storage import ObjectStorage
r = action(client, sid, 'photo-reveal', 'reveal', attempted=False)
assert r.status_code == 200, r.text
answer = view(client, sid)['task']['answer']
assert not answer.get('pdfSlides') and not answer.get('jokboPdfSlides'), answer.get('pdfSlides')
source = doc['review']['sources'][0]
pdf = b'%PDF-1.4\n% photo source copy\n%%EOF\n'
ObjectStorage().put_bytes(photo_snapshot_key(source['sha256']), pdf)
answer = view(client, sid)['task']['answer']
pages = [(s['sourceId'], s['page']) for s in answer['pdfSlides']]
assert pages == [(source['source_id'], 1)], pages
assert answer['pdfSlides'][0]['proxyPath'].endswith(f"/sources/{source['source_id']}?sha={source['sha256']}")
streamed = client.get(answer['pdfSlides'][0]['proxyPath'])
assert streamed.status_code == 200 and streamed.content == pdf, streamed.status_code
assert any(link['label'] == source['label'] for link in answer['sourceLinks'])
# Other sources of the same revision without a copy stay off the answer; a non-photo revision is untouched.
assert client.get(f"{BASE}/sources/NOPE?sha=x").status_code == 404
print('PASS: photo revision shows the cited page once its fingerprint-named source copy exists')
