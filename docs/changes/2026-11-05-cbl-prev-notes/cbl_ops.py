"""Approved three-CBL data rollout; original PDFs and learner state stay intact."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unicodedata

CODE = Path(__file__).resolve().parents[3]
LIVE = CODE.parent.parent if CODE.parent.name == '.worktrees' else CODE
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(CODE / 'server'))
OUT = CODE / 'runs/_development/2026-11-05-cbl-prev-notes'
RUNS = LIVE / 'runs'
SUBJECT = '감염과 면역'
NOTE_ROOT = Path.home() / 'SynologyDrive'
TIMETABLE = CODE / 'data/timetable/2026_본1_2학기_시간표.json'
REL = Path('_materials') / SUBJECT / 'prequiz-inputs'
PAIRS = Path('_pairs') / (SUBJECT + '.json')
APPROVAL = '2026-11-05 사용자: 작년 자료 연결이 미정인 CBL 3개도 확인해서 맞는 작년 필기로 연결해줘.'
TARGETS = {
    '261118_03': ('251119_02', '251119_15', '방어기전손상환자의 감염 CBL예습참고(최평균)_신은주v1', 39, [1, 3, 38]),
    '261125_07': ('251126_06', '251126_15', '암면역 CBL예습참고(성승용)_이준호v1', 49, [1, 2, 45]),
    '261126_07': ('251124_05', '251124_15', '류마티스 관절염 CBL예습참고(이은봉)_주현빈v1', 46, [1, 3, 35, 36]),
}


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')


def read(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def legacy():
    spec = importlib.util.spec_from_file_location('prior_rollout', CODE / 'docs/changes/2026-11-05-professor-aware-preview/deploy_ops.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def database():
    from dotenv import dotenv_values
    for key, value in dotenv_values(LIVE / 'server/.env').items():
        if value is not None:
            os.environ[key] = value
    from app.database import engine, SessionLocal
    assert engine.url.get_backend_name() == 'postgresql' and 'supabase' in engine.url.host
    return engine, SessionLocal


def plans(runs):
    from runner.publish import plan_subject
    return {p.run_id: p for p in plan_subject(NOTE_ROOT, SUBJECT, '2026', '2025', runs,
                                            notes_only=True, timetable=TIMETABLE)[0]}


def prepare():
    from runner.filenames import parse
    old_pairs = json.loads((RUNS / PAIRS).read_text(encoding='utf-8'))
    assert not set(TARGETS) & set(old_pairs), 'Existing manual choices need review'
    save('pairs-before.json', old_pairs)
    shutil.copy2(RUNS / PAIRS, OUT / 'pairs-before.bin')
    stage = OUT / 'staged-runs'
    (stage / REL).mkdir(parents=True, exist_ok=True)
    (stage / PAIRS).parent.mkdir(parents=True, exist_ok=True)
    for path in (RUNS / REL).iterdir():
        if path.suffix == '.json':
            value = json.loads(path.read_text(encoding='utf-8'))
            value['pdf'] = str((stage / REL / Path(value['pdf']).name).resolve())
            (stage / REL / path.name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        elif path.suffix == '.pdf':
            shutil.copy2(path, stage / REL / path.name)
    reviewed = {r['key']: r for r in read('source-scan.json')}
    specs = []
    new_pairs = dict(old_pairs)
    for rid, (source_key, input_id, name, count, pages) in TARGETS.items():
        source = reviewed[source_key]
        path = Path(source['path'])
        assert digest(path) == source['sha256'] and source['pages'] == count
        pdf = stage / REL / f'[{input_id}] {name}.pdf'
        shutil.copy2(path, pdf)
        assert digest(pdf) == source['sha256']
        item = parse(pdf)
        assert item and item.key == input_id and item.year == 2025
        manifest = dict(purpose='approved-prequiz-input', subject=SUBJECT, run_id=rid,
                        input_id=input_id, synthetic_input_id=True, pdf=str(pdf.resolve()),
                        sha256=source['sha256'], approval=APPROVAL, pages=count,
                        kind='unchanged-topic-reference-copy', reviewed_pages=pages,
                        note='2025 일반 강의 필기와 해당 CBL 관련 기출을 예습 참고자료로 사용. CBL 전용 필기 아님. 15 슬롯은 파생 입력 식별자이며 실제 수업 시간이 아님.',
                        sources=[dict(path=str(path.resolve()), sha256=source['sha256'], pages=count)])
        (stage / REL / (rid + '.json')).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        new_pairs[rid] = input_id
        specs.append(dict(runId=rid, inputId=input_id, filename=pdf.name,
                          source=str(path.resolve()), sha256=source['sha256'], pages=count))
    (stage / PAIRS).write_text(json.dumps(new_pairs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # This tracked mapping is the complete durable data change, not another task's edits.
    (CODE / 'runs' / PAIRS).write_text((stage / PAIRS).read_text(encoding='utf-8'), encoding='utf-8')
    before, after = plans(RUNS), plans(stage)
    assert set(before) == set(after)
    changed = [rid for rid in before if before[rid].preview_source != after[rid].preview_source]
    assert set(changed) == set(TARGETS), changed
    for spec in specs:
        p = after[spec['runId']]
        s = p.preview_source
        assert s['selected']['year'] == 2025 and s['selected']['sha256'] == spec['sha256']
        assert s['selected']['filename'] == spec['filename']
        spec['metadata'] = s
    save('approved-plan.json', specs)
    save('selection-baseline.json', {rid: p.preview_source for rid, p in before.items()})
    print('Prepared 3 byte-identical reference copies; only 3 selections change')


def source_review():
    import pymupdf
    for op in read('approved-plan.json'):
        source = Path(op['source'])
        staged = OUT / 'staged-runs' / REL / op['filename']
        assert digest(source) == digest(staged) == op['sha256']
        doc = pymupdf.open(source)
        assert len(doc) == op['pages'] and any('CBL' in p.get_text() for p in doc)
    assert (CODE / 'docs/changes/2026-11-05-cbl-prev-notes/source-review.md').is_file()
    print('3 reviewed original PDFs and 3 identical copies verified; CBL references present')


def selection(live=False):
    from runner.readiness import preview_sources
    runs = RUNS if live else OUT / 'staged-runs'
    choices = plans(runs)
    ready = preview_sources(NOTE_ROOT, SUBJECT, '2026', '2025', runs, TIMETABLE)
    expected = read('approved-plan.json')
    for op in expected:
        rid = op['runId']
        assert choices[rid].preview_source == op['metadata']
        assert ready[rid]['ready'] and ready[rid]['previewSource'] == op['metadata']
        assert ready[rid]['prevRunId'] == op['inputId']
    baseline = read('selection-baseline.json')
    assert all(choices[rid].preview_source == value for rid, value in baseline.items() if rid not in TARGETS)
    pairs = json.loads((runs / PAIRS).read_text(encoding='utf-8'))
    before = read('pairs-before.json')
    assert all(pairs[k] == v for k, v in before.items()) and set(pairs) - set(before) == set(TARGETS)
    print('Publish/readiness agree on all 3 year-2025 inputs; all other selections and mappings unchanged')


def pause(resume=False):
    from runner import desktop_control as control
    with control.locked(RUNS):
        current = control.read(RUNS)
        if resume:
            receipt = read('pause.json')
            assert current == receipt['during'], 'Control choices changed; do not overwrite'
            control.write(RUNS, receipt['before'])
            save('resumed.json', dict(restored=True, state=receipt['before']))
            print('Original runner choices restored')
        elif (OUT / 'pause.json').exists():
            assert current == read('pause.json')['during']
        else:
            after = {**current, 'paused': True}
            save('pause.json', dict(before=current, during=after))
            control.write(RUNS, after)
            print('Runner paused; original choices preserved')


def preflight():
    from sqlalchemy import select, text
    engine, sessions = database()
    from app.models import Lecture, Asset
    old = legacy()
    with sessions() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        lectures = list(db.scalars(select(Lecture).where(Lecture.subject == SUBJECT)))
        values = {l.run_id: dict(identity={k: getattr(l, k) for k in old.IMMUTABLE}, metadata=l.preview_source) for l in lectures}
        for rid in TARGETS:
            assert rid in values and values[rid]['metadata']['selected'] is None
        assets = [dict(id=a.id, runId=a.run_id, kind=a.kind, filename=a.filename,
                       objectKey=a.object_key, size=a.size_bytes) for a in db.scalars(select(Asset).where(Asset.subject == SUBJECT))]
        assert not any(a['runId'] in TARGETS and a['kind'] == 'notes_prev' for a in assets)
        save('production-before.json', dict(lectures=values, assets=assets))
        save('retention-before.json', old.snapshot(db.connection()))
    print('Read-only baseline captured; 3 target attachments absent, all existing data retained')


def install():
    assert digest(RUNS / PAIRS) == digest(OUT / 'pairs-before.bin'), 'Manual choices changed since review'
    from runner import desktop_control as control
    assert control.read(RUNS) == read('pause.json')['during']
    for op in read('approved-plan.json'):
        source = OUT / 'staged-runs' / REL / op['filename']
        dest = RUNS / REL / op['filename']
        manifest_path = RUNS / REL / (op['runId'] + '.json')
        assert not dest.exists() and not manifest_path.exists()
        assert digest(source) == digest(op['source']) == op['sha256']
        shutil.copy2(source, dest)
        manifest = json.loads((OUT / 'staged-runs' / REL / manifest_path.name).read_text(encoding='utf-8'))
        manifest['pdf'] = str(dest.resolve())
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp = (RUNS / PAIRS).with_suffix('.json.cbl-new')
    temp.write_bytes((CODE / 'runs' / PAIRS).read_bytes())
    os.replace(temp, RUNS / PAIRS)
    selection(True)
    save('installed.json', dict(targets=list(TARGETS), pairsSha256=digest(RUNS / PAIRS)))


def metadata():
    from sqlalchemy import select
    _, sessions = database()
    from app.models import Lecture
    from app.preview_sources import preserve_binding
    from studyez_contracts.preview_sources import validate
    old = legacy()
    before = read('production-before.json')['lectures']
    with sessions.begin() as db:
        for op in read('approved-plan.json'):
            l = db.scalar(select(Lecture).where(Lecture.subject == SUBJECT, Lecture.run_id == op['runId']).with_for_update())
            identity = json.loads(json.dumps({k: getattr(l, k) for k in old.IMMUTABLE}, default=str))
            assert identity == before[l.run_id]['identity'] and l.preview_source == before[l.run_id]['metadata']
            l.preview_source = preserve_binding(db, l, validate(op['metadata']))
    save('metadata-applied.json', dict(targets=list(TARGETS), fields=['preview_source', 'updated_at']))
    print('3 metadata choices applied; lecture identities preserved')


def upload():
    from runner.transport import Client, Upload, DEFAULT_API_BASE, lecture_path
    from runner.cycle import runner_token
    token = runner_token(None)
    if not token:
        for line in (LIVE / 'server/.env').read_text(encoding='utf-8').splitlines():
            if line.startswith('RUNNER_TOKEN='):
                token = line.split('=', 1)[1].strip().strip('"').strip("'")
                break
    assert token, 'Existing runner credential unavailable'
    client = Client(DEFAULT_API_BASE, token)
    assert client.call('GET', '/api/admin/previews').get('previewSourceVersion') == 1
    receipts = []
    for op in read('approved-plan.json'):
        path = RUNS / REL / op['filename']
        assert digest(path) == op['sha256']
        item = Upload('notes_prev', path)
        base = lecture_path(SUBJECT, op['runId'])
        signed = client.call('POST', base + '/uploads', [item.payload()])
        checked = client.call('POST', base + '/uploads/complete', [item.payload()])
        if checked['missing']:
            client.put_file(signed['files'][0]['uploadUrl'], path)
            checked = client.call('POST', base + '/uploads/complete', [item.payload()])
        assert not checked['missing']
        receipts.append(dict(runId=op['runId'], filename=op['filename'], sha256=op['sha256']))
        save('uploaded.json', receipts)
        print('Attached', op['runId'], '2025', flush=True)


def preservation(after=False):
    from sqlalchemy import select, text
    _, sessions = database()
    from app.models import Lecture, Asset, TimetableEvent
    from app.preview_sources import public_source
    from app.storage import ObjectStorage
    old = legacy()
    before = read('production-before.json')
    concurrent = read('concurrent-reviewed.json') if after and (OUT / 'concurrent-reviewed.json').exists() else {}
    history_appends = []
    with sessions() as db:
        db.execute(text('SET TRANSACTION READ ONLY'))
        rows = {l.run_id:l for l in db.scalars(select(Lecture).where(Lecture.subject == SUBJECT))}
        assert set(rows) == set(before['lectures'])
        for rid, l in rows.items():
            identity = json.loads(json.dumps({k: getattr(l, k) for k in old.IMMUTABLE}, default=str))
            reviewed = concurrent.get('identities', {}).get(rid)
            assert identity == (reviewed['after'] if reviewed else before['lectures'][rid]['identity'])
            if reviewed:
                assert before['lectures'][rid]['identity'] == reviewed['before']
            if not after or rid not in TARGETS:
                prior = before['lectures'][rid]['metadata'] or {}
                current = l.preview_source or {}
                if current != prior:
                    assert after and rid not in TARGETS
                    assert {k:v for k,v in current.items() if k != '_selectionHistory'} == {k:v for k,v in prior.items() if k != '_selectionHistory'}
                    old_history = prior.get('_selectionHistory', [])
                    assert current.get('_selectionHistory', [])[:len(old_history)] == old_history
                    history_appends.append(rid)
        assets = list(db.scalars(select(Asset).where(Asset.subject == SUBJECT)))
        active = {a.id:a for a in assets}
        for a in before['assets']:
            if a in concurrent.get('removedAssets', []):
                assert a['id'] not in active
                continue
            actual = active[a['id']]
            assert actual.object_key == a['objectKey'] and actual.filename == a['filename'] and actual.size_bytes == a['size']
        for a in concurrent.get('addedAssets', []):
            actual = active[a['id']]
            assert actual.object_key == a['objectKey'] and actual.filename == a['filename'] and actual.size_bytes == a['size']
        results = []
        if after:
            storage = ObjectStorage()
            for op in read('approved-plan.json'):
                l = rows[op['runId']]
                own = [a for a in assets if a.run_id == l.run_id]
                event = db.get(TimetableEvent,l.timetable_event_id) if l.timetable_event_id else None
                summary = public_source(l,event,own)
                assert summary['selected']['year'] == 2025 and not summary['attachmentNeedsReview']
                assert summary['fingerprint'] == op['metadata']['fingerprint']
                a = next(a for a in own if a.kind == 'notes_prev' and a.filename == op['filename'])
                stream = storage.open_stream(a.object_key)
                assert stream is not None
                h=hashlib.sha256()
                for chunk in stream[0]:h.update(chunk)
                assert h.hexdigest() == op['sha256']
                results.append(dict(runId=l.run_id, year=2025, bytesVerified=True, fingerprint=summary['fingerprint']))
        protected = old.snapshot(db.connection())
        assert protected == read('retention-before.json'), 'Inspect legitimate user activity before drawing retention conclusions'
    if after:
        save('verified.json', dict(targets=results, existingLecturesPreserved=len(rows),
                                   existingAssetsPreserved=len(before['assets'])-len(concurrent.get('removedAssets', [])),
                                   concurrentReviewed=concurrent, preservedConcurrentHistoryAppends=history_appends,
                                   protectedTablesUnchanged=list(protected)))
    print(json.dumps(dict(targetsVerified=len(results), existingLecturesPreserved=len(rows),
                          existingAssetsPreserved=len(before['assets']), protectedTablesUnchanged=len(protected))))


def preservation_check():
    env = dict(os.environ)
    env.pop('PYTHONHOME', None)
    result = subprocess.run([str(LIVE / 'server/.venv/Scripts/python.exe'), str(Path(__file__)), 'preservation'],
                            cwd=CODE, env=env)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','source-review','selection','preflight','preservation','preservation-check','pause','install','metadata','upload','verify','resume','live-selection'])
    args=parser.parse_args()
    actions={'prepare':prepare,'source-review':source_review,'selection':selection,'preflight':preflight,
             'preservation':preservation,'preservation-check':preservation_check,'pause':pause,'install':install,'metadata':metadata,'upload':upload,
             'verify':lambda:preservation(True),'resume':lambda:pause(True),'live-selection':lambda:selection(True)}
    actions[args.action]()
