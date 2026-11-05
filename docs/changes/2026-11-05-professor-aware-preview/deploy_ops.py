"""One-time approved rollout. Private snapshots/receipts remain under runs, never Git."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'server'))
OUT = ROOT / 'runs/_development/2026-11-05-professor-aware-preview'
SUBJECT = '감염과 면역'
PROTECTED = ('preview', 'user_preview', 'user_review', 'pre_item', 'main_item', 'quiz_bank',
             'bank_state', 'quiz_attempt', 'main_attempt', 'learning_attempt', 'card_edit')
IMMUTABLE = ('subject', 'run_id', 'uid', 'date', 'slot', 'slot_end', 'start_time', 'title',
             'professors', 'author', 'version', 'timetable_event_id', 'match_confirmed')


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def canonical(value):
    return unicodedata.normalize('NFC', value)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def prepare():
    from studyez_contracts.preview_sources import fingerprint, professor_names, validate
    preflight = read('preflight.json')
    existing = {r['run_id']: r for r in preflight['lectures']}
    result = []
    for local in read('plan-local.json'):
        rid = local['runId']
        if rid not in existing:
            raise ValueError('Unreviewed new lecture identity: ' + rid)
        old = existing[rid]
        source = deepcopy(local['payload']['previewSource'])
        assert source['currentProfessors'] == professor_names(old['professors']), rid
        assert source['date'] == old['date'] and source['startTime'] == old['start_time'], rid
        source = validate(source)
        files = [f for f in local['files'] if f['kind'] == 'notes_prev']
        result.append(dict(runId=rid, before={k: old[k] for k in IMMUTABLE}, source=source, files=files))
    # The canonical lecture predates the two locally parsed filename variants.
    # Keep all three existing IDs; the canonical one gets the same unresolved-source warning.
    if '261102_05' in existing and '261102_05' not in {r['runId'] for r in result}:
        template = next(r for r in result if r['runId'] == '261102_05-464e')
        old = existing['261102_05']
        source = deepcopy(template['source'])
        source.update(currentProfessors=professor_names(old['professors']), changed=None,
                      newProfessor=None, status='needs_review',
                      reason='올해 필기 간 담당 표기 충돌 · 기존 작년 자료 사용')
        if source['selected']:
            source['selected']['match'] = 'same'
        source['fingerprint'] = fingerprint({k: v for k, v in source.items() if k != 'fingerprint'})
        result.append(dict(runId=old['run_id'], before={k: old[k] for k in IMMUTABLE},
                           source=validate(source), files=template['files']))
    assert {r['runId'] for r in result} == set(existing)
    save('approved-operations.json', result)
    print(json.dumps(dict(operations=len(result), existingIdsOnly=True)))


def pause(resume=False):
    from runner import desktop_control as control
    runs = ROOT / 'runs'
    receipt = OUT / 'pause.json'
    with control.locked(runs):
        current = control.read(runs)
        if resume:
            original = read('pause.json')
            if current == original['pausedState']:
                control.write(runs, original['before'])
                save('resumed.json', dict(restored=True, paused=original['before'].get('paused', False)))
                print('Restored original runner pause state')
            else:
                save('resumed.json', dict(restored=False, reason='Control choices changed during deployment'))
                print('Pause retained: another control choice changed')
            return
        if receipt.exists():
            assert current == read('pause.json')['pausedState'], 'Runner choices changed; inspect before continuing'
            print('Deployment pause already in place')
            return
        after = {**current, 'paused': True}
        save('pause.json', dict(before=current, pausedState=after))
        control.write(runs, after)
    print('Runner paused for approved deployment; individual choices preserved')


def database():
    from dotenv import dotenv_values
    for key, value in dotenv_values(ROOT / 'server/.env').items():
        if value is not None:
            os.environ[key] = value
    from app.database import engine, SessionLocal
    from sqlalchemy.engine import make_url
    url = make_url(str(engine.url))
    assert url.get_backend_name() == 'postgresql' and 'supabase' in url.host
    return engine, SessionLocal


def snapshot(db):
    from sqlalchemy import MetaData, Table, inspect, select
    result = {}
    available = set(inspect(db).get_table_names())
    for name in PROTECTED:
        if name not in available:
            continue
        table = Table(name, MetaData(), autoload_with=db)
        if 'subject' not in table.c:
            continue
        rows = [dict(r) for r in db.execute(select(table).where(table.c.subject == SUBJECT)).mappings()]
        rows = json.loads(json.dumps(rows, default=str))
        result[name] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))
    return result


def schema():
    from sqlalchemy import inspect, text
    engine, _ = database()
    with engine.begin() as db:
        present = 'preview_source' in {c['name'] for c in inspect(db).get_columns('lecture')}
        if not present:
            db.execute(text('ALTER TABLE public.lecture ADD COLUMN preview_source JSON NULL'))
        assert 'preview_source' in {c['name'] for c in inspect(db).get_columns('lecture')}
    save('schema.json', dict(column='lecture.preview_source', added=not present,
                            time=datetime.now(timezone.utc).isoformat()))
    print('Required nullable column ready; no other schema changes')


def metadata():
    from sqlalchemy import select
    engine, sessions = database()
    from app.models import Lecture
    from app.preview_sources import preserve_binding
    from studyez_contracts.preview_sources import validate
    operations = read('approved-operations.json')
    if (OUT / 'metadata-applied.json').exists():
        with sessions() as db:
            for op in operations:
                lecture = db.get(Lecture, (SUBJECT, op['runId']))
                assert (lecture.preview_source or {}).get('fingerprint') == op['source']['fingerprint']
        print('Metadata already applied; original rollback snapshot retained')
        return
    with engine.connect() as db:
        save('retention-before.json', snapshot(db))
    with sessions.begin() as db:
        rows = {r.run_id: r for r in db.scalars(select(Lecture).where(Lecture.subject == SUBJECT).with_for_update())}
        assert set(rows) == {r['runId'] for r in operations}
        before = {}
        for op in operations:
            lecture = rows[op['runId']]
            values = json.loads(json.dumps({k: getattr(lecture, k) for k in IMMUTABLE}, default=str))
            assert values == op['before'], 'Lecture changed since preflight: ' + op['runId']
            before[op['runId']] = lecture.preview_source
            lecture.preview_source = preserve_binding(db, lecture, validate(op['source']))
        save('metadata-before.json', before)
    save('metadata-applied.json', dict(count=len(operations), fieldsChanged=['preview_source', 'updated_at']))
    print('Applied metadata only:', len(operations), 'existing lecture IDs; all identity fields preserved')


def upload(revision):
    from runner.cycle import runner_token
    from runner.transport import Client, Upload, DEFAULT_API_BASE, lecture_path
    from urllib.request import urlopen
    client = Client(DEFAULT_API_BASE, runner_token(None))
    health = client.call('GET', '/api/health')
    assert health.get('revision') == revision, 'Production API revision mismatch'
    assert client.call('GET', '/api/admin/previews').get('previewSourceVersion') == 1
    old = read('preflight.json')['assets']
    old = {(r['run_id'], canonical(r['filename']), r['size_bytes']) for r in old if r['kind'] == 'notes_prev'}
    result = []
    for op in read('approved-operations.json'):
        selected = op['source']['selected']
        if not selected or not op['files']:
            continue
        if (op['runId'], selected['filename'], selected['sizeBytes']) in old:
            result.append(dict(runId=op['runId'], filename=selected['filename'], retained=True))
            continue
        path = Path(op['files'][0]['path'])
        assert sha(path) == selected['sha256'], 'Local input changed before upload'
        item = Upload('notes_prev', path)
        base = lecture_path(SUBJECT, op['runId'])
        signed = client.call('POST', base + '/uploads', [item.payload()])
        checked = client.call('POST', base + '/uploads/complete', [item.payload()])
        if checked['missing']:
            client.put_file(signed['files'][0]['uploadUrl'], path)
            checked = client.call('POST', base + '/uploads/complete', [item.payload()])
            assert not checked['missing']
        result.append(dict(runId=op['runId'], filename=selected['filename'], retained=False,
                           sha256=selected['sha256'], objectKey=signed['files'][0]['objectKey']))
        save('uploaded.json', result)
        print('Attached', op['runId'], selected['year'], selected['filename'], flush=True)
    save('uploaded.json', result)
    print('Changed attachments:', sum(not r['retained'] for r in result))


def verify():
    from sqlalchemy import select
    engine, sessions = database()
    from app.models import Lecture, Asset, TimetableEvent
    from app.preview_sources import public_source
    from app.storage import ObjectStorage
    from studyez_contracts.preview_sources import validate
    operations = read('approved-operations.json')
    storage = ObjectStorage()
    results = []
    with sessions() as db:
        lectures = {r.run_id: r for r in db.scalars(select(Lecture).where(Lecture.subject == SUBJECT))}
        for op in operations:
            lecture = lectures[op['runId']]
            values = json.loads(json.dumps({k: getattr(lecture, k) for k in IMMUTABLE}, default=str))
            assert values == op['before'], 'Identity fields changed: ' + op['runId']
            assets = list(db.scalars(select(Asset).where(Asset.subject == SUBJECT, Asset.run_id == op['runId'])))
            event = db.get(TimetableEvent, lecture.timetable_event_id)
            summary = public_source(lecture, event, assets)
            assert summary and not summary['attachmentNeedsReview'], op['runId']
            assert summary['fingerprint'] == op['source']['fingerprint']
            selected = op['source']['selected']
            if selected:
                active = next(a for a in assets if a.kind == 'notes_prev' and a.filename == selected['filename'])
                source = storage.open_stream(active.object_key)
                assert source is not None
                digest = hashlib.sha256()
                for chunk in source[0]:
                    digest.update(chunk)
                assert digest.hexdigest() == selected['sha256'], 'Stored PDF bytes mismatch: ' + op['runId']
            for old in (lecture.preview_source or {}).get('_previousAttachments', []):
                assert storage.head(old['objectKey']) is not None, 'Archived PDF missing'
            results.append(dict(runId=op['runId'], changed=summary['changed'], newProfessor=summary['newProfessor'],
                                status=summary['status'], year=selected['year'] if selected else None,
                                conversationNeedsReview=summary['conversationNeedsReview'], identityPreserved=True,
                                attachmentBytesVerified=bool(selected)))
        protected_after = snapshot(db.connection())
    before = read('retention-before.json')
    # User activity may add/update state; this rollout never calls learning/preview mutation routes.
    unchanged = {name: json.loads(json.dumps(rows, default=str)) == protected_after.get(name)
                 for name, rows in before.items()}
    save('retention-after.json', protected_after)
    save('verified.json', dict(lectures=results, protectedTablesUnchanged=unchanged))
    assert all(unchanged.values()), 'Protected table changed; inspect snapshots before resuming'
    print(json.dumps(dict(lectures=len(results), verifiedPdfBytes=sum(r['attachmentBytesVerified'] for r in results),
                          protectedTables=len(unchanged), protectedTablesUnchanged=all(unchanged.values())), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'pause', 'resume', 'schema', 'metadata', 'upload', 'verify'])
    parser.add_argument('--revision')
    args = parser.parse_args()
    actions = {'prepare': prepare, 'pause': pause, 'resume': lambda: pause(True), 'schema': schema,
               'metadata': metadata, 'upload': lambda: upload(args.revision), 'verify': verify}
    actions[args.action]()
