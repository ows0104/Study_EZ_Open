"""Isolated roundtrip, retention, stale-input rollback and reseed verification."""
import json
import os
from pathlib import Path
import sys
import tempfile

TMP = Path(tempfile.mkdtemp(prefix='studyez-timetable-'))
ROOT = Path(__file__).resolve().parents[2]
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}")
sys.path.insert(0, str(ROOT / 'scripts'))

from app.database import Base, engine, SessionLocal
from app.cli import seed_timetable
from app.models import Lecture, TimetableEvent
from sqlalchemy import Column, Table, Text, select, update
from immunity_timetable_update import inputs, update_database, values


def main():
    Base.metadata.create_all(engine)
    protected = Table('retention_test', Base.metadata, Column('subject', Text), Column('run_id', Text),
                      Column('link', Text), Column('bank', Text), Column('history', Text))
    protected.create(engine)
    rows, patch, identities = inputs()
    old = {r['id']: r for r in rows}
    old.update({p['before']['id']: p['before'] for p in patch})
    with engine.begin() as conn:
        conn.execute(TimetableEvent.__table__.insert(), [dict(id=r['id'], **values(r)) for r in old.values()])
        conn.execute(protected.insert(), dict(subject='감염과 면역', run_id='261105_05',
                                            link='https://example.test/existing', bank='original questions', history='learned'))
    with SessionLocal() as db:
        for event_id, run_id in identities.items():
            raw = old[event_id]
            db.add(Lecture(subject='감염과 면역', run_id=run_id, uid=run_id+'#existing',
                           date=values(raw)['date'], slot=values(raw)['slot'], slot_end=values(raw)['slot'],
                           start_time=raw['startTime'], title=raw['details'].split('\n')[0], professors=[],
                           timetable_event_id=event_id, match_confirmed=False))
        db.commit()
    first = update_database(engine, apply=True)
    assert first['changed_events'] == 16 and len(first['confirmed_links']) == 12
    assert first['preservation_verified'] and first['protected']['retention_test']['rows'] == 1
    print('PASS apply: 16 events, 12 existing identities, protected link/bank/history unchanged')
    again = update_database(engine, apply=True)
    assert not again['applied'] and again['changed_events'] == 0
    print('PASS repeated apply is harmless')
    with SessionLocal() as db:
        before_links = [(l.run_id, l.timetable_event_id) for l in db.scalars(select(Lecture))]
    seed_timetable(ROOT / 'data/timetable/2026_본1_2학기_시간표.json')
    with SessionLocal() as db:
        after_links = [(l.run_id, l.timetable_event_id) for l in db.scalars(select(Lecture))]
    assert before_links == after_links
    print('PASS normal reseed preserves moved lecture links')
    receipt = TMP / 'receipt.json'
    receipt.write_text(json.dumps(first), encoding='utf-8')
    reversed_result = update_database(engine, apply=True, reverse=True, previous_receipt=receipt)
    assert reversed_result['changed_events'] == 16
    with SessionLocal() as db:
        assert all(not l.match_confirmed for l in db.scalars(select(Lecture)))
    print('PASS conditional rollback restores timetable and confirmation flags')
    with engine.begin() as conn:
        conn.execute(update(TimetableEvent).where(TimetableEvent.id == rows[0]['id']).values(details='unreviewed'))
    try:
        update_database(engine, apply=True)
        raise RuntimeError('Stale source was accepted')
    except AssertionError as exc:
        assert 'reviewed versions' in str(exc)
    print('PASS unexpected data is rejected before writes')
    with engine.begin() as conn:
        conn.execute(update(TimetableEvent).where(TimetableEvent.id == rows[0]['id']).values(**values(old[rows[0]['id']])))
        conn.execute(update(Lecture).where(Lecture.run_id == '261105_05').values(run_id='unexpected'))
    try:
        update_database(engine, apply=True)
        raise RuntimeError('Unreviewed moved lecture was accepted')
    except AssertionError as exc:
        assert 'Unreviewed moved lecture' in str(exc)
    with engine.connect() as conn:
        event_id = patch[1]['before']['id']
        actual = conn.execute(select(TimetableEvent.__table__).where(TimetableEvent.id == event_id)).mappings().one()
        assert all(actual[k] == v for k, v in values(old[event_id]).items())
    print('PASS failure after event writes rolls back all timetable changes')
    print('All 6 preservation/rollback scenarios passed.')


if __name__ == '__main__':
    main()
