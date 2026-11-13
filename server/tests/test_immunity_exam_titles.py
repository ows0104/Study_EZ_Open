"""2026-11-13: named 1·2차 exam cells link 감염과 면역 lectures into a study plan (isolated SQLite)."""
import json
import os
from datetime import datetime
from pathlib import Path
import sys
import tempfile

TMP = Path(tempfile.mkdtemp(prefix='studyez-exam-titles-'))
ROOT = Path(__file__).resolve().parents[2]
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}")
sys.path.insert(0, str(ROOT / 'scripts'))

from app.auth import CurrentUser
from app.cli import seed_timetable
from app.database import Base, SessionLocal, engine
from app.models import TimetableEvent
from app.routes.study_plan import build_study_plan
from app.study_engine.planning import KOREA
from immunity_exam_titles import SOURCE, columns, pairs, update_database

NOW = int(datetime(2026, 11, 13, 10, tzinfo=KOREA).timestamp() * 1000)
USER = CurrentUser(id='student', email='student@example.com', is_admin=False, apps={})


def plan():
    with SessionLocal() as db:
        return build_study_plan(90, None, None, USER, db, NOW)


def stored():
    with SessionLocal() as db:
        return {p['after']['id']: {k: getattr(db.get(TimetableEvent, p['after']['id']), k)
                                   for k in ('title', 'course', 'course_key')} for p in pairs()}


def main():
    Base.metadata.create_all(engine)
    changed = pairs()
    assert len(changed) == 2
    before = {p['before']['id']: p['before'] for p in changed}
    old = TMP / 'before.json'
    old.write_text(json.dumps([before.get(r['id'], r) for r in json.loads(SOURCE.read_text(encoding='utf-8'))],
                              ensure_ascii=False), encoding='utf-8')
    seed_timetable(old)
    first = plan()
    assert first['plans'] == [] and first['unmatchedExams'].count('시험') == 3
    print('PASS before: bare 「시험」 leaves no plan (the 「–」 card)')

    dry = update_database(engine)
    assert [r['changed'] for r in dry['rows']] == [True, True] and stored() == {i: columns('시험') for i in before}
    print('PASS dry run writes nothing')

    update_database(engine, apply=True)
    result = plan()
    titles = [p['title'] for p in result['plans']]
    assert titles == ['감염과 면역 1차 시험', '감염과 면역 2차 시험'], titles
    assert all(p['lectureCount'] > 0 for p in result['plans']) and result['unmatchedExams'] == ['시험']
    print('PASS apply: 1차·2차 plans with lectures, 12/11 left as is')

    assert not any(r['changed'] for r in update_database(engine, apply=True)['rows'])
    print('PASS repeated apply is harmless')

    applied = stored()
    seed_timetable(SOURCE)
    assert stored() == applied
    print('PASS reseeding the current JSON gives the same columns')

    update_database(engine, apply=True, reverse=True)
    assert stored() == {i: columns('시험') for i in before} and plan()['plans'] == []
    print('PASS reverse restores 「시험」')

    with engine.begin() as conn:
        conn.execute(TimetableEvent.__table__.update().where(TimetableEvent.id == changed[0]['after']['id'])
                     .values(title='다른 시험'))
    try:
        update_database(engine, apply=True)
    except AssertionError:
        print('PASS unexpected title stops the update')
    else:
        raise AssertionError('unexpected title was overwritten')


if __name__ == '__main__':
    main()
