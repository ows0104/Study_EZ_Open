import json
import os
import hashlib
from pathlib import Path

import pytest
from runner import filenames, readiness, prequeue, publish


def pdf(folder, name):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b'fixture PDF')
    return path


def test_nested_year_folders_keep_versions_and_skip_archives(tmp_path):
    folder = tmp_path / '2025'
    pdf(folder / '1차', '[251103_02] 감염병의 병인론(최은화)_가나다v1.pdf')
    latest = pdf(folder / '2차', '[251103_02] 감염병의 병인론(최은화)_가나다v2.pdf')
    pdf(folder / '1차', '[251103_02] 감염병의 병인론(최은화)_가나다v1 (1).pdf')
    pdf(folder / 'archive', '[251103_03] 보관본(최은화)_가나다v1.pdf')
    pdf(folder / '.hidden', '[251103_04] 숨김(최은화)_가나다v1.pdf')
    pdf(folder / '1차', '[261103_05] 연도혼입(최은화)_가나다v1.pdf')
    scan = filenames.scan(folder, '2025')
    assert len(scan.files) == 2 and len(scan.conflicts) == 1 and len(scan.misfiled) == 1
    assert filenames.latest_versions(scan.files)[0].path == latest


def test_duplicate_detection_stays_in_its_own_directory(tmp_path):
    pdf(tmp_path / '1차', '[251103_02] 병인론(최은화)_가나다v1.pdf')
    copy = pdf(tmp_path / '2차', '[251103_02] 병인론(최은화)_가나다v1 (1).pdf')
    scan = filenames.scan(tmp_path, '2025')
    assert copy not in scan.conflicts and len(scan.files) == 2


def test_directory_links_are_not_followed(tmp_path):
    external = tmp_path / 'external'
    pdf(external, '[251103_02] 외부(최은화)_가나다v1.pdf')
    folder = tmp_path / 'year'
    folder.mkdir()
    try:
        (folder / 'link').symlink_to(external, target_is_directory=True)
    except OSError:
        pytest.skip('symlink privilege unavailable')
    assert filenames.scan(folder, '2025').files == []


def test_readiness_and_real_prequeue_agree_on_nested_notes(tmp_path, monkeypatch):
    subject = '감염과 면역'
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    pdf(root / subject / '필기/2026', '[261102_02] 감염병의 병인론(최은화)_가나다v1.pdf')
    previous = pdf(root / subject / '필기/2025/1차', '[251103_02] 감염병의 병인론(최은화)_가나다v1.pdf')
    table = tmp_path / 'table.json'
    table.write_text('[]', encoding='utf-8')
    before = sorted(tmp_path.rglob('*'))
    rows = readiness.preview_sources(root, subject, '2026', '2025', runs, table)
    assert rows['261102_02']['ready'] and rows['261102_02']['prevPdf'] == str(previous)
    assert sorted(tmp_path.rglob('*')) == before  # readiness is strictly read-only
    monkeypatch.setattr(publish.bank_sources, 'jokbo_slices', lambda *a: {})
    targets, _ = prequeue.resolve([prequeue.Link(subject, '261102_02', '2026-11-02', '병인론', 'https://example.test')],
                                 root, '2026', '2025', runs, table)
    assert targets[0].prev_pdf == str(previous) and targets[0].state != prequeue.BLOCKED


def test_unmatched_sources_cannot_be_ready(tmp_path):
    root = tmp_path / 'notes'
    pdf(root / '과목/필기/2026', '[261102_02] 병인론(최은화)_가나다v1.pdf')
    table = tmp_path / 'table.json'
    table.write_text('[]', encoding='utf-8')
    rows = readiness.preview_sources(root, '과목', '2026', '2025', tmp_path / 'runs', table)
    assert not rows['261102_02']['ready'] and '작년' in rows['261102_02']['reason']


def test_packet_hash_change_fails_closed(tmp_path):
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    source = pdf(root / '과목/필기/2025/1차', '[251103_02] 병인론(최은화)_가나다v1.pdf')
    folder = runs / '_materials/과목/prequiz-inputs'
    merged = pdf(folder, '[251104_01] 합본(최은화)_가나다v1.pdf')
    pairs = runs / '_pairs'
    pairs.mkdir()
    (pairs / '과목.json').write_text(json.dumps({'261103_01': '251104_01'}), encoding='utf-8')
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    (folder / '261103_01.json').write_text(json.dumps(dict(purpose='approved-prequiz-input', subject='과목',
        run_id='261103_01', input_id='251104_01', pdf=str(merged), sha256=digest(merged),
        sources=[dict(path=str(source), sha256=digest(source))])), encoding='utf-8')
    assert readiness.packet_sources(root, '과목', '2025', runs)[0].key == '251104_01'
    source.write_bytes(b'changed source')
    with pytest.raises(ValueError, match='변경'):
        readiness.packet_sources(root, '과목', '2025', runs)
