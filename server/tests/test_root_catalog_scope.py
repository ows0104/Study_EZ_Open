"""The lecture list asks only for its block's lectures (docs/changes/2026-11-24-lecture-list-block-scope).

- `lecture=과목/runId` limits the catalog to those open lectures; lectures not asked for are never computed.
- Unknown or closed keys drop out quietly; without `lecture` the catalog is every open lecture, as before.
- A key splits at its last `/`.
"""
from tests.root_support import setup, publish
client, user, SessionLocal = setup()
from app.routes import root_learning

publish(client, user)
user('a')

computed = []
real = root_learning.overview_data
root_learning.overview_data = lambda db, row, u, when: computed.append((row.subject, row.run_id)) or real(db, row, u, when)
try:
    # R2: no argument → every open lecture, same as before.
    every = client.get('/api/root-learning')
    assert every.status_code == 200, every.text
    assert [(l['subject'], l['runId']) for l in every.json()['lectures']] == [('test', 'demo')]
    assert computed == [('test', 'demo')]

    # R1: asked → that lecture, with the same summary as the unscoped list.
    computed.clear()
    asked = client.get('/api/root-learning', params={'lecture': ['test/demo', 'test/missing']})
    assert asked.status_code == 200, asked.text
    assert asked.json()['lectures'] == every.json()['lectures']
    assert computed == [('test', 'demo')]

    # R1: a block without this lecture → nothing computed, empty list (not every lecture).
    computed.clear()
    other = client.get('/api/root-learning', params={'lecture': ['other/261124_01']})
    assert other.status_code == 200 and other.json()['lectures'] == [], other.text
    assert computed == []

    # Malformed values only → empty, not "everything".
    computed.clear()
    bad = client.get('/api/root-learning', params={'lecture': ['nodelimiter', '/x', 'x/']})
    assert bad.status_code == 200 and bad.json()['lectures'] == [] and computed == []
finally:
    root_learning.overview_data = real

# R3: split at the last `/`.
assert root_learning.wanted_lectures(['감염과 면역/261105_05', 'a/b/c', 'bad', 'x/']) == {
    ('감염과 면역', '261105_05'), ('a/b', 'c')}
print('ok')
