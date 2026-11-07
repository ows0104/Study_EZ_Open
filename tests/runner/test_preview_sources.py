import json
import os
from pathlib import Path

import pytest

from runner import filenames, publish, prequeue, readiness
from runner.preview_sources import History

SUBJECT = '감염과 면역'


def note(root, year, *, professor='김범준', topic='포도알균', version=1, slot='01', date=None):
    folder = root / SUBJECT / '필기' / str(year)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'[{date or str(year)[2:] + "1101"}_{slot}] {topic}({professor})_가나다v{version}.pdf'
    path.write_bytes(f'{year} {topic} {professor} {version}'.encode())
    value = filenames.parse(path)
    assert value
    return value


def history(root, runs, baseline):
    return History(root, SUBJECT, '2026', '2025', [baseline] if baseline else [], runs)


def test_latest_same_professor_overrides_last_year_and_readiness_agrees(tmp_path, monkeypatch):
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    target = note(root, 2026)
    baseline = note(root, 2025, professor='방예지')
    note(root, 2022)
    chosen = note(root, 2023, version=2)
    note(root, 2023, version=1)
    decision = history(root, runs, baseline).select(target, baseline)
    assert decision.item.path == chosen.path
    assert decision.metadata['changed'] is True
    assert decision.metadata['newProfessor'] is False
    assert decision.metadata['selected']['year'] == 2023
    assert decision.metadata['coverage']['missing'] == [2024, 2021]
    monkeypatch.setattr(publish.bank_sources, 'jokbo_slices', lambda *args: {})
    plans, _ = publish.plan_subject(root, SUBJECT, '2026', '2025', runs, gated=False)
    ready = readiness.preview_sources(root, SUBJECT, '2026', '2025', runs, tmp_path / 'no-table.json')
    assert plans[0].prev_run_id == chosen.key == ready[target.key]['prevRunId']
    assert next(u.path for u in plans[0].uploads if u.kind == 'notes_prev') == chosen.path
    assert plans[0].payload['previewSource'] == ready[target.key]['previewSource']


@pytest.mark.parametrize('year,expected', [(2024, 2024), (2021, 2021), (2020, 2025)])
def test_five_year_boundary_and_last_year_fallback(tmp_path, year, expected):
    target = note(tmp_path, 2026)
    baseline = note(tmp_path, 2025, professor='방예지')
    note(tmp_path, year)
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.item.year == expected
    assert result.metadata['newProfessor'] == (expected == 2025)


def test_last_year_same_professor_wins_over_older(tmp_path):
    target = note(tmp_path, 2026)
    baseline = note(tmp_path, 2025)
    note(tmp_path, 2023)
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.item == baseline
    assert result.metadata['changed'] is False


def test_sequence_and_other_topics_cannot_supply_same_professor(tmp_path):
    target = note(tmp_path, 2026, topic='포도알균(1)')
    baseline = note(tmp_path, 2025, topic='포도알균(1)', professor='방예지')
    note(tmp_path, 2023, topic='포도알균(2)')
    note(tmp_path, 2022, topic='사슬알균')
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.item == baseline
    assert result.metadata['newProfessor'] is True


def test_full_confirmed_title_anchors_folded_timetable_heading(tmp_path):
    target = note(tmp_path, 2026, topic='감염병의', professor='박수경')
    baseline = note(tmp_path, 2025, topic='감염병의 집단발병 역학조사', professor='송진수')
    older = note(tmp_path, 2023, topic='감염병의 집단발병 역학조사', professor='박수경')
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline, source='timetable')
    assert result.item == older
    assert result.metadata['currentSource'] == 'timetable'


def test_unknown_professor_is_not_new_and_uses_baseline(tmp_path):
    target = note(tmp_path, 2026)
    from dataclasses import replace
    target = replace(target, professors=())
    baseline = note(tmp_path, 2025)
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.item == baseline
    assert result.metadata['newProfessor'] is None
    assert result.metadata['changed'] is None
    assert result.metadata['status'] == 'needs_review'


def test_partial_team_match_keeps_baseline_without_calling_everyone_new(tmp_path):
    target = note(tmp_path, 2026, professor='김범준,방예지')
    baseline = note(tmp_path, 2025, professor='김현제')
    note(tmp_path, 2023)
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.item == baseline
    assert result.metadata['newProfessor'] is False
    assert result.metadata['status'] == 'needs_review'


def test_tied_distinct_same_professor_candidates_require_review(tmp_path):
    target = note(tmp_path, 2026)
    baseline = note(tmp_path, 2025, professor='방예지')
    note(tmp_path, 2023, slot='01')
    note(tmp_path, 2023, slot='02')
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.item == baseline
    assert result.metadata['newProfessor'] is None


def test_failed_scan_and_relevant_unparsed_do_not_prove_absence(tmp_path, monkeypatch):
    target, baseline = note(tmp_path, 2026), note(tmp_path, 2025, professor='방예지')
    folder = tmp_path / SUBJECT / '필기/2023'
    folder.mkdir()
    (folder / '포도알균_김범준.pdf').write_bytes(b'unparsed')
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.metadata['newProfessor'] is None
    original = filenames.scan
    def fail(path, *args, **kwargs):
        if Path(path).name == '2023':
            raise PermissionError('unreadable')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(filenames, 'scan', fail)
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert result.metadata['coverage']['failed'] == [2023]
    assert result.metadata['newProfessor'] is None


def test_scope_confirmed_packet_is_preserved(tmp_path):
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    target = note(root, 2026)
    packet = note(runs, 2025, professor='방예지')
    note(root, 2023)
    result = history(root, runs, packet).select(target, packet)
    assert result.item == packet
    assert result.metadata['status'] == 'needs_review'
    assert result.metadata['newProfessor'] is None


def test_new_source_does_not_reuse_old_shared_conversation(tmp_path, monkeypatch):
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    target, baseline = note(root, 2026), note(root, 2025, professor='방예지')
    chosen = note(root, 2023)
    monkeypatch.setattr(publish.bank_sources, 'jokbo_slices', lambda *a: {})
    link = prequeue.Link(SUBJECT, target.key, target.date, target.title, 'https://example.test')
    results, _ = prequeue.resolve([link], root, '2026', '2025', runs)
    assert results[0].state == prequeue.BLOCKED
    assert '원본이 변경' in results[0].reason
    from dataclasses import replace
    link = replace(link, source_filename=chosen.path.name)
    results, _ = prequeue.resolve([link], root, '2026', '2025', runs)
    assert results[0].state == prequeue.READY
    assert results[0].prev_pdf == str(chosen.path)


def test_unmatched_future_cell_still_gets_metadata_and_old_matching_policy_survives(tmp_path, monkeypatch):
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    folder = runs / '_pairs'
    folder.mkdir(parents=True)
    (folder / f'{SUBJECT}.json').write_text(json.dumps({'_block': SUBJECT}), encoding='utf-8')
    table = tmp_path / 'table.json'
    table.write_text(json.dumps([dict(date='2026-11-05', startTime='09:00', title=SUBJECT+' 1',
                     details='새로운 주제', professor='김범준', category='lecture')]), encoding='utf-8')
    monkeypatch.setattr(publish.bank_sources, 'jokbo_slices', lambda *a: {})
    plans, _ = publish.plan_subject(root, SUBJECT, '2026', '2025', runs, timetable=table)
    assert len(plans) == 1
    assert plans[0].preview_source['selected'] is None
    assert plans[0].preview_source['newProfessor'] is None
    assert plans[0].preview_source['currentSource'] == 'timetable'


def test_selection_hash_changes_when_source_bytes_change(tmp_path):
    target, baseline = note(tmp_path, 2026), note(tmp_path, 2025)
    first = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    before = baseline.path.stat()
    replacement = b'new revision with new content'
    assert len(replacement) == before.st_size  # same size: only mtime separates the cache key
    baseline.path.write_bytes(replacement)
    # Windows can stamp two quick writes with the same mtime; advance it so the test
    # checks a real edit instead of racing the filesystem clock.
    os.utime(baseline.path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    second = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    assert first.metadata['selected']['sha256'] != second.metadata['selected']['sha256']
    assert first.metadata['fingerprint'] != second.metadata['fingerprint']


def test_conflicting_current_notes_do_not_create_false_new_professor_tag(tmp_path):
    first, second = note(tmp_path, 2026), note(tmp_path, 2026, professor='방예지')
    baseline = note(tmp_path, 2025, professor='방예지')
    result = History(tmp_path, SUBJECT, '2026', '2025', [baseline], tmp_path / 'runs',
                     current_files=[first, second]).select(first, baseline)
    assert result.metadata['changed'] is None
    assert result.metadata['newProfessor'] is None
    assert result.metadata['status'] == 'needs_review'
    assert '충돌' in result.metadata['reason']


def test_older_server_cannot_receive_new_materials_without_retention_support(tmp_path):
    target, baseline = note(tmp_path, 2026), note(tmp_path, 2025, professor='방예지')
    source = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    plan = publish.LecturePlan(SUBJECT, target.key, target, preview_source=source.metadata)
    class OldServer:
        def __init__(self):
            self.calls = []
        def call(self, method, path, body=None):
            self.calls.append((method, path))
            return {'previews': []}
    client = OldServer()
    report = publish.publish([plan], client, tmp_path / 'runs', log=lambda *a: None)
    assert report.failures
    assert client.calls == [('GET', '/api/admin/previews')]


def test_synology_nfd_filename_matches_the_servers_nfc_attachment_identity(tmp_path):
    import unicodedata
    from dataclasses import replace
    from studyez_contracts.preview_sources import conversation_matches
    target, baseline = note(tmp_path, 2026), note(tmp_path, 2025)
    decomposed = baseline.path.with_name(unicodedata.normalize('NFD', baseline.path.name))
    baseline.path.rename(decomposed)
    baseline = replace(baseline, path=decomposed)
    result = history(tmp_path, tmp_path / 'runs', baseline).select(target, baseline)
    filename = unicodedata.normalize('NFC', decomposed.name)
    assert result.metadata['selected']['filename'] == filename
    assert result.metadata['baselineFilename'] == filename
    assert conversation_matches(result.metadata, filename)
