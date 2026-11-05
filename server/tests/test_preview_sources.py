"""Isolated professor provenance, backwards compatibility and conversation retention."""
import os
from pathlib import Path
import tempfile
from datetime import date
from copy import deepcopy
import hashlib
from unittest.mock import patch

TMP = Path(tempfile.mkdtemp(prefix='studyez-preview-sources-'))
os.environ.update(ENVIRONMENT='local-test', DATABASE_URL=f"sqlite:///{(TMP / 'test.db').as_posix()}",
                  STORAGE_LOCAL_DIR=str(TMP / 'storage'), RUNNER_TOKEN='test-runner')

from sqlalchemy import inspect, text
from pydantic import ValidationError
from app.database import Base, engine, SessionLocal
from app.cli import ensure_columns
from app.auth import CurrentUser
from app.models import Asset, Lecture, Preview, TimetableEvent
from app.preview_sources import public_source, bind_new_preview
from app.routes.admin import (LectureIn, upsert_lectures, list_previews, FileIn, presign_uploads,
                              complete_uploads, put_pre_items, PreItemsIn)
from fastapi import HTTPException
from app.routes.timetable import read_timetable
from app.routes.lectures import read_lecture
from studyez_contracts.preview_sources import fingerprint


def metadata():
    value = dict(version=1, year=2026, currentProfessors=['김범준'], currentSource='timetable',
                 date='2026-11-05', startTime='09:00', baselineYear=2025,
                 baselineProfessors=['방예지'], baselineFilename='[251105_01]포도알균(방예지).pdf',
                 changed=True, newProfessor=False, status='ok', reason='동일 교수 최신 보유 필기',
                 coverage=dict(available=[2025, 2023, 2022, 2021], missing=[2024], incomplete=[], failed=[]),
                 selected=dict(year=2023, filename='[231101_01]포도알균(김범준).pdf', professors=['김범준'],
                               sha256='a'*64, sizeBytes=10, match='same'))
    value['fingerprint'] = fingerprint(value)
    return value


def main():
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE lecture DROP COLUMN preview_source'))
    ensure_columns()
    ensure_columns()
    assert 'preview_source' in {c['name'] for c in inspect(engine).get_columns('lecture')}
    print('PASS additive nullable migration and idempotency in isolated SQLite')
    runner = CurrentUser('runner', 'runner@example.test', True)
    student = CurrentUser('student', 'student@example.test', False)
    raw = dict(subject='감염과 면역', runId='261105_01', uid='261105_01#포도알균#김범준',
               date='2026-11-05', slot=1, startTime='09:00', title='포도알균', professors=['김범준'])
    with SessionLocal() as db:
        event = TimetableEvent(id='event-1', date=date(2026, 11, 5), start_time='09:00', end_time='10:00',
                               title='감염과 면역 1', details='포도알균', professor='김범준',
                               category='lecture', course='감염과 면역', course_key='감염과면역', slot=1)
        db.add(event)
        db.commit()
        upsert_lectures([LectureIn(**raw)], runner, db)
        lecture = db.get(Lecture, ('감염과 면역', '261105_01'))
        assert lecture.preview_source is None
        assert public_source(lecture) is None
        # Simulate the existing conversation and original 2025 attachment.
        db.add(Preview(subject=lecture.subject, run_id=lecture.run_id, provider='chatgpt',
                       share_url='https://chatgpt.com/share/old-conversation'))
        db.add(Asset(id='asset-old', subject=lecture.subject, run_id=lecture.run_id, kind='notes_prev',
                     filename=metadata()['baselineFilename'], object_key='private/old.pdf', size_bytes=20))
        db.commit()
        upsert_lectures([LectureIn(**raw, previewSource=metadata())], runner, db)
        value = public_source(lecture, event)
        assert value['changed'] is True and value['selected']['year'] == 2023
        assert value['conversationNeedsReview'] is True
        assert '_previewBinding' not in value and 'private/' not in str(value)
        assets = db.query(Asset).all()
        assert public_source(lecture, event, assets)['attachmentNeedsReview'] is True
        print('PASS prior attachment/conversation preserved and flagged on changed notes')
        previous = deepcopy(lecture.preview_source)
        upsert_lectures([LectureIn(**raw)], runner, db)
        assert lecture.preview_source == previous
        assert db.get(Preview, (lecture.subject, lecture.run_id)).share_url.endswith('old-conversation')
        print('PASS older runner omitting metadata cannot erase it or existing links')
        timetable = read_timetable(None, None, False, False, student, db)
        assert timetable['events'][0]['lectures'][0]['previewSource']['changed'] is True
        assert timetable['events'][0]['lectures'][0]['previewSource']['selected']['year'] == 2023
        detail = read_lecture(lecture.subject, lecture.run_id, student, db)
        assert detail['previewSource']['attachmentNeedsReview'] is True
        assert '_previewBinding' not in str(detail['previewSource'])
        print('PASS metadata-only calendar and student detail expose path-free provenance')
        try:
            put_pre_items(lecture.subject, lecture.run_id, PreItemsIn(items=[]), runner, db)
            raise AssertionError('old conversation accepted for new source')
        except HTTPException as error:
            assert error.status_code == 409
        class Storage:
            def __init__(self):
                self.objects = {'private/old.pdf': b'o' * 20}
            def presign_upload(self, key, **kwargs):
                return 'https://example.test/' + key
            def head(self, key):
                return {'ContentLength': len(self.objects[key])} if key in self.objects else None
            def open_stream(self, key):
                return (iter([self.objects[key]]), len(self.objects[key])) if key in self.objects else None
            def delete(self, key):
                raise AssertionError('existing preview notes must not be deleted')
        storage = Storage()
        file = FileIn(kind='notes_prev', filename=metadata()['selected']['filename'], sizeBytes=10,
                      contentType='application/pdf')
        with patch('app.routes.admin.storage_or_503', return_value=storage):
            signed = presign_uploads(lecture.subject, lecture.run_id, [file], runner, db)
            new_key = signed['files'][0]['objectKey']
            assert 'a' * 64 in new_key and new_key != 'private/old.pdf'
            storage.objects[new_key] = b'n' * 10
            complete_uploads(lecture.subject, lecture.run_id, [file], runner, db)
        archive = lecture.preview_source['_previousAttachments']
        assert archive[0]['objectKey'] == 'private/old.pdf'
        assert archive[0]['sha256'] == hashlib.sha256(b'o' * 20).hexdigest()
        assert storage.objects['private/old.pdf'] == b'o' * 20
        assert db.query(Asset).count() == 1
        assert not public_source(lecture, event, db.query(Asset).all())['attachmentNeedsReview']
        upsert_lectures([LectureIn(**raw, previewSource=metadata())], runner, db)
        assert lecture.preview_source['_previousAttachments'] == archive
        print('PASS new immutable source key, old PDF/hash/restore metadata retained across sweeps')
        before = deepcopy(lecture.preview_source)
        event.professor = '방예지'
        value = public_source(lecture, event)
        assert value['changed'] is None and value['newProfessor'] is None
        assert value['status'] == 'needs_review'
        assert lecture.preview_source == before
        event.professor = '김범준'
        print('PASS changed timetable invalidates stale labels without overwriting evidence')
        response = list_previews(runner, db)
        assert response['previewSourceVersion'] == 1
        rows = response['previews']
        assert rows[0]['sourceFilename'] == metadata()['baselineFilename']
        bind_new_preview(lecture)
        db.commit()
        assert not public_source(lecture, event)['conversationNeedsReview']
        rows = list_previews(runner, db)['previews']
        assert rows[0]['sourceFilename'] == metadata()['selected']['filename']
        print('PASS explicit new conversation binding exports source identity to runner')
    try:
        bad = metadata()
        bad['selected']['filename'] = 'C:/private/source.pdf'
        LectureIn(**raw, previewSource=bad)
        raise AssertionError('private path accepted')
    except ValidationError:
        pass
    try:
        bad = metadata()
        bad['currentProfessors'] = ['방예지']
        bad['selected']['match'] = 'different'
        LectureIn(**raw, previewSource=bad)
        raise AssertionError('different target accepted')
    except ValidationError:
        pass
    print('PASS malformed/private provenance rejected at ingest')


if __name__ == '__main__':
    main()
