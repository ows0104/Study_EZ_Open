"""An admin split is atomic, reversible and survives identical runner rebuilds."""
import copy
import datetime
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix='studyez-card-split-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
    STUDYEZ_LOCAL_STORAGE_DIR=str(TMP / 'storage'), RUNNER_TOKEN='runner-token')

from fastapi.testclient import TestClient
from app import bank_edits
from app.bank_validation.schema import without_retired
from app.bank_validation.validate import validate_bank
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Asset, BankState, BankStateArchive, Lecture, QuizBank
from tests.bank_fixtures import example_bank


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        db.add(Lecture(subject='test', run_id='demo', uid='split-test',
            date=datetime.date(2026, 10, 16), slot=1, slot_end=1, start_time='09:00',
            title='Split test', professors=[], author='', version=1))
        db.add(Asset(id='notes', subject='test', run_id='demo', kind='notes_current',
            filename='notes.pdf', object_key='notes.pdf', content_type='application/pdf'))
        db.commit()
    client = TestClient(app)
    admin = '/api/admin/lectures/test/demo'
    headers = {'Authorization': 'Bearer local-test-token'}
    response = client.put(admin + '/bank-response', headers=headers,
        json={'raw': 'test ' * 60 + 'STUDYEZ_BANK_COMPLETE'}).json()
    bank = without_retired(example_bank())
    bank['build_meta']['schema_version'] = '3.1'
    checked = validate_bank(bank, ['S1'])
    assert checked['pass'], checked
    uploaded = client.put(admin + '/bank', headers={'Authorization': 'Bearer runner-token'},
        json={'respondedAt': response['respondedAt'], 'bank': bank, 'validation': checked})
    assert uploaded.status_code == 200, uploaded.text
    with SessionLocal() as db:
        row = db.get(QuizBank, ('test', 'demo'))
        original = copy.deepcopy(row.bank)
        original_validation = copy.deepcopy(row.validation)
        build_id = row.build_id
        state = {'history': [{'question_id': 'Q1', 'timestamp': 1, 'undo': {'old': True}}],
                 'mastery': {'C1': 0.7}, 'served': {'question_id': 'Q1', 'token': 'old'}}
        db.add(BankState(user_id='split-student', subject='test', run_id='demo',
                        build_id=build_id, state=state))
        db.commit()
    target = original['questions'][0]
    anchor = {**target, 'question': 'First independent fact?'}
    child = {**target, 'question_id': 'Q1-F01', 'question': 'Second independent fact?'}
    route = admin + '/bank/cards/Q1'
    def put(action='split', expected=target, build=build_id, **extra):
        body = {'buildId': build, 'expectedQuestion': expected, 'action': action,
                'questions': [anchor, child], 'reason': 'Independent recall targets', **extra}
        return client.put(route, headers=headers, json=body)
    assert put(build='stale').status_code == 409
    assert put(expected={**target, 'question': 'stale'}).status_code == 409
    for replacements in ([anchor, anchor], [child, {**child, 'question_id': 'Q1-F02'}],
                         [anchor, {**child, 'question_id': 'Q2'}],
                         [anchor, {**child, 'concept_id': 'other'}],
                         [anchor, {**child, 'prerequisites': ['missing']}],
                         [anchor, {**child, 'question': child['answer']}]):
        rejected = put(questions=replacements)
        assert rejected.status_code == 422, rejected.text
        with SessionLocal() as db:
            assert db.get(QuizBank, ('test', 'demo')).bank == original
    applied = put()
    assert applied.status_code == 200, applied.text
    with SessionLocal() as db:
        row = db.get(QuizBank, ('test', 'demo'))
        split_bank, split_validation = copy.deepcopy(row.bank), copy.deepcopy(row.validation)
        assert row.build_id == build_id and row.validation['pass']
        assert [q['question_id'] for q in row.bank['questions']] == ['Q1', 'Q1-F01', 'Q2', 'Q3']
        assert row.bank['questions'][2:] == original['questions'][1:]
        assert row.validation['edits']['Q1']['original'] == target
        saved = db.get(BankState, ('split-student', 'test', 'demo')).state
        assert saved['served'] is None and saved['dimensions'] == {}
        assert saved['history'] == [], 'Changed split fragments cannot inherit the original review'
        assert any(a.state == state for a in db.query(BankStateArchive).filter_by(user_id='split-student'))
    assert put(expected=anchor).status_code == 422
    # A later child edit wins independently of JSON dictionary key order.
    child_edit = {**child, 'question': 'Updated second independent fact?'}
    edits = {'Q1-F01': {'action': 'edit', 'original': child, 'question': child_edit},
             **split_validation['edits']}
    edited_bank, edited_validation = bank_edits.with_edits(split_bank, split_validation, edits, ['S1'])
    assert edited_validation['pass']
    assert next(q for q in edited_bank['questions'] if q['question_id'] == 'Q1-F01') == child_edit
    rebuilt, reapplied = bank_edits.reapply(original, original_validation, edited_validation, ['S1'])
    assert reapplied['pass'] and len(rebuilt['questions']) == 4
    assert next(q for q in rebuilt['questions'] if q['question_id'] == 'Q1-F01') == child_edit
    changed = copy.deepcopy(original)
    changed['questions'][0]['question'] = 'New runner source fact?'
    refreshed, _ = bank_edits.reapply(changed, original_validation, split_validation, ['S1'])
    assert len(refreshed['questions']) == 3
    deleted = copy.deepcopy(edits)
    deleted['Q1']['action'] = 'delete'
    removed, _ = bank_edits.with_edits(edited_bank, edited_validation, deleted, ['S1'])
    assert not {'Q1', 'Q1-F01'} & {q['question_id'] for q in removed['questions']}
    restored = put(action='reset', expected=anchor)
    assert restored.status_code == 200, restored.text
    with SessionLocal() as db:
        row = db.get(QuizBank, ('test', 'demo'))
        assert row.build_id == build_id and row.validation['pass']
        assert {q['question_id']: q for q in row.bank['questions']} == {q['question_id']: q for q in original['questions']}
        assert row.bank['retrieval_plan'] == original['retrieval_plan']
        assert not row.validation['edits']
    print('PASS split collision/staleness/invalid atomicity, history preservation, reapply, child edit/delete and reset')


if __name__ == '__main__':
    main()
