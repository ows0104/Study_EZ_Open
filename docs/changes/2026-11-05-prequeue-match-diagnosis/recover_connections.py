"""Apply only previously verified infection-block mappings under current approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from runner import ahead, blocks, filenames, prequeue, publish, readiness

SUBJECT = '감염과 면역'
RUNS = ROOT / 'runs'
NOTES = Path.home() / 'SynologyDrive'
PRIOR = ROOT / 'docs/changes/2026-11-01-infection-materials'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(apply=False):
    verified = json.loads((PRIOR / 'upload-plan.json').read_text(encoding='utf-8'))
    inventory = json.loads((PRIOR / 'inventory.json').read_text(encoding='utf-8'))
    original = {r['key']: r for r in inventory['notes']}
    pair_file = RUNS / '_pairs' / f'{SUBJECT}.json'
    before_bytes = pair_file.read_bytes()
    before = json.loads(before_bytes)
    plans, _ = publish.plan_subject(NOTES, SUBJECT, '2026', '2025', RUNS,
                                    gated=False, timetable=blocks.DEFAULT_SOURCE)
    by_run = {p.run_id: p for p in plans}
    available_keys = {c.key for c in ahead.read_cells(blocks.DEFAULT_SOURCE)}
    folder = RUNS / '_materials' / SUBJECT / 'prequiz-inputs'
    # Byte-identical copies of already verified inputs avoid pre_target collisions.
    copies = {
        '261102_06': ('251104_02', '위장관감염 피부연조직감염 요로감염 폐렴 동영상_합본v1'),
        '261105_07': ('251106_08', '심내막염 중추신경계감염 동영상_사본v1'),
    }
    candidate = dict(before)
    added, packets = {}, []
    for row in verified['lectures']:
        run_id, keys = row['run_id'], row['previous_keys']
        plan = by_run.get(run_id)
        if run_id in copies:
            input_id, label = copies[run_id]
            pdf = folder / f'[{input_id}] {label}.pdf'
            source_pdf = Path(next(u['path'] for u in row['uploads'] if u['kind'] == 'notes_prev'))
            assert filenames.parse(pdf).key == input_id
            # Sources are verified against their preserved November 1 fingerprints.
            sources = [dict(path=original[k]['path'], sha256=original[k]['sha256']) for k in keys]
            for source in sources:
                assert sha(source['path']) == source['sha256'], source['path']
            expected_copy = sha(source_pdf)
            if len(keys) == 1:
                assert expected_copy == original[keys[0]]['sha256']
            else:
                prepared = next(f for f in verified['files'] if f['path'] == str(source_pdf))
                assert expected_copy == prepared['sha256']
            manifest = dict(purpose='approved-prequiz-input', subject=SUBJECT,
                            run_id=run_id, input_id=input_id, pdf=str(pdf),
                            sha256=expected_copy, sources=sources,
                            provenance='2026-11-01-infection-materials/upload-plan.json; 2026-11-05 current chat approval')
            packets.append((pdf, source_pdf, manifest))
            expected = input_id
        elif run_id in before:
            continue  # Preserve the existing approved TBL packet and any human choices.
        elif plan and len(keys) == 1 and plan.prev_run_id == keys[0]:
            continue  # Keep working automatic links unchanged.
        else:
            assert len(keys) == 1, row
            expected = keys[0]
            assert sha(original[expected]['path']) == original[expected]['sha256']
        assert run_id in available_keys, run_id
        assert run_id not in before or before[run_id] == expected, run_id
        candidate[run_id] = expected
        if before.get(run_id) != expected:
            added[run_id] = expected
    audit = dict(subject=SUBJECT, before=before, additions=added,
                 packets=[m for _, _, m in packets], verified_lectures=len(verified['lectures']),
                 unverified_slots=verified['not_linked'])
    write(HERE / 'connection-audit.json', audit)
    if not apply:
        print(json.dumps(dict(proposed=len(added), packets=len(packets)), ensure_ascii=False))
        return
    backup = HERE / 'pairs-before.json'
    if not backup.exists():
        backup.write_bytes(before_bytes)
    for pdf, source_pdf, manifest in packets:
        pdf.parent.mkdir(parents=True, exist_ok=True)
        manifest_path = folder / f"{manifest['run_id']}.json"
        if pdf.exists():
            assert sha(pdf) == manifest['sha256'], pdf
        else:
            shutil.copyfile(source_pdf, pdf)
        assert sha(pdf) == manifest['sha256']
        if manifest_path.exists():
            assert json.loads(manifest_path.read_text(encoding='utf-8')) == manifest
        else:
            write(manifest_path, manifest)
    assert pair_file.read_bytes() == before_bytes, 'Concurrent pairs update; stop rather than overwrite'
    temp = pair_file.with_suffix('.recovery.tmp')
    write(temp, candidate)
    temp.replace(pair_file)
    # Validate both consumers using the actual restored metadata.
    plans, warnings = publish.plan_subject(NOTES, SUBJECT, '2026', '2025', RUNS,
                                          gated=False, timetable=blocks.DEFAULT_SOURCE)
    ready = readiness.preview_sources(NOTES, SUBJECT, '2026', '2025', RUNS, blocks.DEFAULT_SOURCE)
    by_run = {p.run_id: p for p in plans}
    rows = []
    for row in verified['lectures']:
        run_id = row['run_id']
        plan = by_run[run_id]
        expected = candidate.get(run_id) or row['previous_keys'][0]
        assert plan.prev_run_id == expected, (run_id, expected, plan.prev_run_id)
        assert ready[run_id]['ready'] and ready[run_id]['prevRunId'] == expected
        targets, _ = prequeue.resolve([prequeue.Link(SUBJECT, run_id, row['lecture_payload']['date'],
                                   row['lecture_payload']['title'], 'https://example.test/diagnosis-only')],
                                      NOTES, '2026', '2025', RUNS, blocks.DEFAULT_SOURCE)
        assert targets[0].state == prequeue.READY and targets[0].prev_run_id == expected
        rows.append(dict(runId=run_id, prevRunId=expected, ready=True))
    assert len({p.prev_run_id for p in plans if p.run_id in copies}) == len(copies)
    write(HERE / 'connections-verified.json', dict(lectures=rows, warnings=warnings))
    print(json.dumps(dict(added=len(added), verified=len(rows), warnings=len(warnings)), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    main(parser.parse_args().apply)
