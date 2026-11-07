"""Read back this named administrator pilot without creating learner events."""
import base64
import hashlib
import importlib.util
import json
import urllib.request
from pathlib import Path

path = Path(__file__).with_name('publication.py')
spec = importlib.util.spec_from_file_location('named_publication', path)
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
receipt = p.read(p.OUT / 'publication-receipt.json')
assert receipt['publishedVerified']
packet, result = p.read(p.OUT / 'packet.json'), p.read(p.OUT / 'result.json')
before = p.read(p.OUT / 'publication-preflight.json')
with urllib.request.urlopen('https://studyez-api-97999573571.asia-northeast3.run.app/api/health', timeout=30) as response:
    health = json.load(response)
assert health['revision'] == receipt['apiRevision'] and health['environment'] == 'production'
with p.SessionLocal() as db:
    actual = p.inspect(db, packet)
    assert actual['bank'] == before['bank'] and actual['bankStates'] == before['bankStates']
    assert actual['rootSessions'] == before['rootSessions']
    assert all(actual['rootEvents'].get(k) == v for k, v in before['rootEvents'].items())
    assert len(actual['rootEvents']) == len(before['rootEvents']) + 1
    assert actual['control'] == {'revision': packet['revision'], 'enabled': True, 'allowedUsers': ['runner']}
    row = db.get(p.RootContent, (packet['subject'], packet['runId'], packet['revision']))
    assert row.document == result['document'] and row.reviewed
    questions = row.document['bank_snapshot']['questions']
    visuals = [q for q in questions if q.get('stimuli')]
    images = [s for q in visuals for s in q['stimuli']]
    assert len(questions) == 91 and len(visuals) == 15 and len(images) == 19
    for stimulus in images:
        assert hashlib.sha256(base64.b64decode(stimulus['png_base64'])).hexdigest() == stimulus['sha256']
    from app.routes.root_learning import revealed_answer
    answer = revealed_answer(db, row, visuals[0])
    assert 'reviewNotes' in answer and 'reviewIssues' in answer
    assert len(answer['sourceLinks']) == len(packet['sources'])
    for link, source in zip(answer['sourceLinks'], packet['sources']):
        with urllib.request.urlopen(link['url'], timeout=45) as response:
            body = response.read()
        assert hashlib.sha256(body).hexdigest() == source['sha256'] and len(body) == source['sizeBytes']
value = {'verified': True, 'apiRevision': health['revision'], 'questions': len(questions),
         'visualQuestions': len(visuals), 'stimuli': len(images), 'tasks': len(row.document['tasks']),
         'bankUnchanged': True, 'humanSessionsUnchanged': True, 'humanEventsUnchanged': True,
         'privatePilot': True, 'actualPresignedPdfReadback': True, 'reviewNotesAvailable': True,
         'learnerWrites': 0}
(p.OUT / 'publication-readback.json').write_text(json.dumps(value, indent=2), encoding='utf-8')
print(json.dumps(value))
