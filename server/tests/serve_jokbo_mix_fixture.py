"""Owned local browser fixture for 족보 모아풀기(docs/changes/2026-11-18-jokbo-mix): a fresh isolated database and
local storage with three synthetic jokbo cells of different sizes.

- evA: same professor 6 items (2025) + other professor 2 items (2020)
- evB: same professor 2 items (2024) + other professor 1 item (2019)
- evC: other professor only, 1 item (2018) — 「같은 교수만」 cannot apply
"""
import os
import tempfile
from datetime import date
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='jokbo-mix-', dir=Path(__file__).resolve().parents[1] / 'local_test_data'
                            if (Path(__file__).resolve().parents[1] / 'local_test_data').exists() else None))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
                  RUNNER_TOKEN='runner-token', STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'))

from fastapi import Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app.auth import APP_POLICY, ROLE_ADMIN, CurrentUser, get_current_user  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import TimetableEvent  # noqa: E402

RUNNER = {'Authorization': 'Bearer runner-token'}


def item(prefix, i, year):
    return {'id': f'{prefix}{i}', 'year': year, 'yearLabel': str(year), 'number': i, 'stem': f'{prefix.upper()} question {i}?',
            'choices': ['first', 'second', 'third'], 'answers': [1], 'answerMode': 'one_of', 'answerStatus': 'key',
            'verification': 'verified', 'explanation': None}


def doc(event_id, number, title, same, other, same_year, other_year, prefix):
    items = [item(prefix, i, same_year) for i in range(1, same + 1)] + \
            [item(prefix, i, other_year) for i in range(same + 1, same + other + 1)]
    sections = []
    if same:
        sections.append({'kind': 'same', 'professors': ['갑'], 'years': [str(same_year)], 'itemIds': [x['id'] for x in items[:same]]})
    sections.append({'kind': 'other', 'professors': ['을'], 'years': [str(other_year)], 'itemIds': [x['id'] for x in items[same:]]})
    return {'schema': 'jokbo-solve/1',
            'lecture': {'eventId': event_id, 'runId': None, 'number': number, 'title': title,
                        'currentProfessors': ['갑'], 'professorSource': 'timetable'},
            'sections': sections, 'items': items}


CELLS = [('evA', '1', '감염학) Lecture A', 6, 2, 2025, 2020, 'a'),
         ('evB', '2', '감염학) Lecture B', 2, 1, 2024, 2019, 'b'),
         ('evC', '3', '감염학) Lecture C', 0, 1, 2025, 2018, 'c')]

Base.metadata.create_all(engine)
with SessionLocal() as db:
    for i, (event_id, *_rest) in enumerate(CELLS):
        db.add(TimetableEvent(id=event_id, date=date(2026, 11, 9 + i), start_time='09:00', end_time='09:50',
                              title=_rest[1], category='lecture', course='감염과 면역'))
    db.commit()
client = TestClient(app)
for event_id, number, title, same, other, sy, oy, prefix in CELLS:
    r = client.put(f'/api/admin/jokbo/events/{event_id}?audience=all', json=doc(event_id, number, title, same, other, sy, oy, prefix),
                   headers=RUNNER)
    assert r.status_code == 200, r.text


def test_user(request: Request):
    uid = request.headers.get('X-Root-Test-User', 'a')
    return CurrentUser(id=uid, email=f'{uid}@example.com', is_admin=False, apps=dict.fromkeys(APP_POLICY, ROLE_ADMIN))


app.dependency_overrides[get_current_user] = test_user
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=int(os.environ.get('JOKBO_MIX_PORT', '8033')), log_level='warning')
