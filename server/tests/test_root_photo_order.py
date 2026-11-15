"""Photo revisions: 「순서대로/랜덤」 at the start (docs/changes/2026-11-15-photo-quiz-shuffle).

A photo-import revision without prerequisites offers the choice; random serves a fixed shuffle per user·revision·day,
switching on resume reorders only the unsolved rest, and an old client (no order) keeps today's order. Other revisions
ignore the choice and keep the plan order."""
import copy
from tests.root_support import setup, publish, start, view, action, document, ADMIN, BASE
from studyez_contracts.learning_links.validate import question_hash
from studyez_contracts.roots import document_hash

client, user, SessionLocal = setup()
ENTRY = '/api/main-quiz/lectures/test/demo/entry'


def photo_document():
    doc = copy.deepcopy(document())
    doc['revision'] = 'photo-order'
    review, bank = doc['review'], doc['bank_snapshot']
    review['provenance']['method'] = 'photo-import/1'
    doc['prerequisites'] = []
    doc['exam_date'] = None   # 시험일이 없으면 오늘 계획이 준비된 새 목표 전부다
    for q in bank['questions']:
        q['prerequisites'] = []
    review['bank_sha256'] = document_hash(bank)
    by_id = {q['question_id']: q for q in bank['questions']}
    for m in review['mappings']:
        m['question_sha256'] = question_hash(by_id[m['question_id']], bank)
    return doc


def overview():
    r = client.get(ENTRY); assert r.status_code == 200, r.text
    return r.json()['overview']


def tasks_of(sid):
    from app.models.root_learning import RootSession
    with SessionLocal() as db:
        session = db.get(RootSession, sid)
        return [t['task_id'] for t in session.tasks], dict(session.state)


def begin(request, **order):
    r = client.post(BASE + '/sessions', json={'requestId': request, **order}); assert r.status_code == 200, r.text
    return r.json()['sessionId']


# 1. An ordinary revision (it has prerequisites): no choice, random is ignored.
publish(client, user)
user('plain')
assert overview()['orderChoice'] is False
plain = tasks_of(begin('plain-random', order='random'))
assert 'order' not in plain[1], plain[1]
print('PASS: an ordinary revision offers no order choice and ignores random')

# 2. Photo revision: the choice is offered; ordered keeps the document order.
doc = photo_document()
publish(client, user, doc)
order = [t['task_id'] for t in doc['tasks']]
user('ordered')
info = overview()
assert info['orderChoice'] is True and info['order'] is None, info
ordered, state = tasks_of(begin('o-start', order='ordered'))
assert ordered == order and state.get('order') is None, ordered
print('PASS: photo revision offers the choice; ordered serves the document order')

# 3. Random: a permutation fixed by user·revision·day; starting again the same day gives the same session.
from app.root_learning import planning
from app.routes.root_learning import shuffle_seed
user('random')
sid = begin('r-start', order='random')
shuffled, state = tasks_of(sid)
assert sorted(shuffled) == sorted(order) and state['order'] == 'random'
seed = shuffle_seed('random', doc['revision'], view(client, sid)['day'])
assert shuffled == [t['task_id'] for t in planning.shuffled([{'task_id': t} for t in order], seed)]
assert overview()['order'] == 'random'
assert begin('r-again', order='random') == sid
print('PASS: random serves a fixed shuffle and resumes the same session')

# 4. Resume with another choice reorders only the rest; an old client (no order) leaves it as it is.
first = view(client, sid)['task']['id']
assert action(client, sid, 'r-reveal', 'reveal').status_code == 200
assert begin('r-ordered', order='ordered') == sid
now, state = tasks_of(sid)
assert now[0] == first and now[1:] == [t for t in order if t != first] and state['order'] == 'ordered', now
assert begin('r-old') == sid and tasks_of(sid)[0] == now
assert begin('r-random-again', order='random') == sid
again = tasks_of(sid)[0]
assert again[0] == first and sorted(again[1:]) == sorted(now[1:])
print('PASS: switching on resume keeps the opened task and reorders the rest; no order keeps today\'s order')
