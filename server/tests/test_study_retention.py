"""Content identity, mastery recovery, deduplication, and repeated replacement."""
import copy
import os
import tempfile
from pathlib import Path
from datetime import UTC, date, datetime

TMP = Path(tempfile.mkdtemp(prefix='studyez-retention-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f'sqlite:///{(TMP / "test.db").as_posix()}',
                  RUNNER_TOKEN='test-only')
from sqlalchemy import select
from app.database import Base, engine, SessionLocal
from app.models import Lecture, QuizBank, BankState, BankStateArchive, BankVersion
from app.bank_retention import replace_bank, save_version, archive_row, transition
from app.study_retention import migrate, question_map, fingerprint, manifest, event_identity
from app.study_engine.engine import empty_state, record_review
from tests.bank_fixtures import example_bank
from app.routes.usage import _bank_activity


def main():
    old = example_bank()
    t = 1_790_000_000_000
    state = record_review(old, empty_state(), 'Q1', 'Good', t)
    state = record_review(old, state, 'Q2', 'Again', t + 1000)
    before = copy.deepcopy(state)
    new = copy.deepcopy(old)
    new['questions'][0].update(question_id='renamed', concept_id='new-concept')
    new['questions'][1]['answer'] = 'changed answer'
    new['questions'][2]['prerequisites'] = ['renamed']
    recovered = migrate(new, [('old', old, state)])
    assert len(recovered['history']) == 1
    assert recovered['history'][0]['question_id'] == 'renamed'
    assert recovered['history'][0]['timestamp'] == t
    assert recovered['dimensions']['new-concept:direct'] == state['dimensions']['C1:direct']
    assert state == before
    assert 'C1:reverse' not in recovered['dimensions']
    assert recovered['served'] is None and recovered['session'] is None
    assert 'undo' not in recovered['history'][0]
    twice = migrate(new, [('old', old, state), ('new', new, recovered)])
    assert len(twice['history']) == 1
    assert twice['history'][0]['origin_event_id'] == recovered['history'][0]['origin_event_id']
    assert twice['dimensions'] == recovered['dimensions']
    assert question_map(None, new) == {}
    assert question_map(None, new, manifest(old))['Q1'] == 'renamed'
    collision = copy.deepcopy(old)
    collision['questions'][0]['question'] = 'different prompt with the same ID'
    assert 'Q1' not in question_map(old, collision)
    spacing = copy.deepcopy(old['questions'][0])
    spacing['question'] = '  ' + spacing['question'].replace(' ', '\n') + ' '
    assert fingerprint(spacing) == fingerprint(old['questions'][0])
    for field, change in [('format', 'mcq'), ('correct_option_ids', ['different'])]:
        q = copy.deepcopy(old['questions'][0])
        q[field] = change
        assert fingerprint(q) != fingerprint(old['questions'][0]), field
    visual = {**old['questions'][0], 'question': '그림의 표시된 구조는?'}
    assert fingerprint(visual) != fingerprint({**visual, 'source_refs': [{'source_id': 'S2', 'locator': 'different image'}]})
    assert fingerprint(old['questions'][0]) == fingerprint({**old['questions'][0], 'source_refs': []})
    # A changed question sharing a dimension must not contribute to its mastery.
    same = copy.deepcopy(old)
    same['questions'][1]['retrieval_direction'] = 'direct'
    combined = record_review(same, empty_state(), 'Q1', 'Good', t)
    combined = record_review(same, combined, 'Q2', 'Easy', t + 1000)
    changed = copy.deepcopy(same)
    changed['questions'][1]['answer'] = 'changed'
    partial = migrate(changed, [('old', same, combined)])
    assert partial['dimensions']['C1:direct']['reviews'] == 1
    assert partial['dimensions']['C1:direct']['mastery'] == state['dimensions']['C1:direct']['mastery']
    print('PASS content identity, renamed IDs, changed answers/images/options, partial dimensions, deduplication')

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject='test', run_id='r', uid='r#test', date=date(2026, 10, 19), slot=1,
                       slot_end=1, start_time='09:00', title='test', professors=[], author='', version=1))
        bank = QuizBank(subject='test', run_id='r', build_id='b1', bank=old, validation={})
        row = BankState(user_id='student', subject='test', run_id='r', build_id='b1', state=state)
        db.add_all([bank, row])
        db.commit()
        replace_bank(db, bank, copy.deepcopy(old), 'b2')
        db.commit()
        assert row.build_id == 'b2' and len(row.state['history']) == 2
        first = copy.deepcopy(row.state)
        replace_bank(db, bank, copy.deepcopy(old), 'b3')
        db.commit()
        assert len(row.state['history']) == 2
        assert row.state['dimensions'] == first['dimensions']
        assert sum(len(reviews) for _, _, _, reviews in _bank_activity(db, 'student')) == 2
        builds = set(db.scalars(select(BankStateArchive.build_id)))
        assert {'b1', 'b2'} <= builds
        assert len(list(db.scalars(select(BankVersion)))) == 3
        # Same-build metadata publication preserves a pending session and mastery.
        row.state = {**row.state, 'served': {'token': 'pending', 'question_id': 'Q1'}}
        db.commit()
        unchanged = copy.deepcopy(row.state)
        metadata = copy.deepcopy(old)
        metadata['questions'][0]['tier'] = 'Important'
        replace_bank(db, bank, metadata, 'b3')
        assert row.state == unchanged
        db.commit()
        # Cancellation markers prevent an archived origin from being resurrected.
        archive_row(db, row)
        cancelled = [event_identity(row.build_id, e) for e in row.state['history']]
        row.state = {**row.state, 'history': [], 'items': {}, 'dimensions': {}, 'review_tombstones': cancelled}
        row.previous = None
        db.commit()
        bank.build_id = 'b4'
        save_version(db, 'test', 'r', 'b4', metadata)
        transition(db, row, bank)
        assert row.build_id == 'b4'
        assert row.state['history'] == [] and not row.state['dimensions']
        assert sum(len(reviews) for _, _, _, reviews in _bank_activity(db, 'student')) == 0
        db.rollback()
    print('PASS transactional archives, three replacements, same-build metadata, existing mastery')


if __name__ == '__main__':
    main()
