import json

from runner import agent_state, prequeue, publish


SUBJECT = '감염과 면역'
RUN_ID = '261105_02'


def link(run_id=RUN_ID):
    return prequeue.Link(SUBJECT, run_id, '2026-11-05', '장내세균의 일반적 특성', 'https://example.test')


def fixture(tmp_path, monkeypatch):
    root, runs = tmp_path / 'notes', tmp_path / 'runs'
    folder = root / SUBJECT / '필기'
    for year, name in [
        ('2026', '[261105_01] 사슬알균(김현제)_가나다v1.pdf'),
        ('2025/1차', '[251106_02] 장내세균의 일반적 특성(김동현)_최용준v2.pdf'),
    ]:
        (folder / year).mkdir(parents=True)
        (folder / year / name).write_bytes(b'fixture')
    table = tmp_path / 'table.json'
    table.write_text(json.dumps([
        dict(date='2026-11-05', startTime='09:00', title='감염과 면역 9',
             details='미생물학) 사슬알균', professor='김현제', category='lecture'),
        dict(date='2026-11-05', startTime='10:00', title='감염과 면역 10',
             details='미생물학) 장내세균의\n일반적 특성', professor='김동현', category='lecture'),
    ], ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(publish.bank_sources, 'jokbo_slices', lambda *a: {})
    return root, runs, table


def test_folded_title_reports_match_failure_and_confirmed_pair_restores_target(tmp_path, monkeypatch):
    root, runs, table = fixture(tmp_path, monkeypatch)
    targets, _ = prequeue.resolve([link()], root, '2026', '2025', runs, table)
    target = targets[0]
    assert target.state == prequeue.BLOCKED
    assert '작년 짝이 확정이 아니다' in target.reason and '0.57' in target.reason
    assert '시간표 칸도 없다' not in target.reason
    lines = [f'2026-11-05 ✋ {RUN_ID} 장내세균', f'    {target.reason}']
    assert agent_state.blocked_reason(lines, RUN_ID) == target.reason
    pairs = runs / '_pairs'
    pairs.mkdir(parents=True)
    (pairs / f'{SUBJECT}.json').write_text(json.dumps({RUN_ID: '251106_02'}), encoding='utf-8')
    targets, _ = prequeue.resolve([link()], root, '2026', '2025', runs, table)
    assert targets[0].state == prequeue.READY
    assert targets[0].prev_run_id == '251106_02'
    assert targets[0].this_title == '미생물학) 장내세균의 일반적 특성'


def test_missing_timetable_reports_read_failure(tmp_path, monkeypatch):
    root, runs, _ = fixture(tmp_path, monkeypatch)
    targets, _ = prequeue.resolve([link()], root, '2026', '2025', runs, tmp_path / 'missing.json')
    assert '시간표를 읽지 못했다' in targets[0].reason


def test_unknown_target_does_not_borrow_other_lecture_warning(tmp_path, monkeypatch):
    root, runs, table = fixture(tmp_path, monkeypatch)
    targets, warnings = prequeue.resolve([link('261105_03')], root, '2026', '2025', runs, table)
    assert any(RUN_ID in w for w in warnings)
    assert targets[0].state == prequeue.BLOCKED
    assert '계획을 세우지 못했다' in targets[0].reason
    assert '시간표 칸도 없다' not in targets[0].reason
    assert '0.57' not in targets[0].reason


def test_subject_failure_is_preserved(tmp_path, monkeypatch):
    root, runs, table = fixture(tmp_path, monkeypatch)
    table.write_text('[]', encoding='utf-8')
    targets, _ = prequeue.resolve([link()], root, '2026', '2025', runs, table)
    assert '시간표에서 이 과목을 못 찾는다' in targets[0].reason


def test_warning_selection_uses_exact_subject_and_run():
    target = f'{SUBJECT}/{RUN_ID} 장내세균 — 작년 짝을 못 찾았다'
    warnings = ['다른 과목/261105_02 다른 강의 — 작년 짝을 못 찾았다',
                f'{SUBJECT}/261105_020 다른 강의 — 작년 짝을 못 찾았다', target]
    assert prequeue._unplanned_reason(SUBJECT, RUN_ID, warnings) == target
    confirmed = f'{SUBJECT}: 확인해 준 짝을 못 찾았다 — {RUN_ID} → 251106_02 (그런 작년 필기가 없다)'
    assert prequeue._unplanned_reason(SUBJECT, RUN_ID, [confirmed]) == confirmed


def test_confirmed_practice_is_found_without_widening_automatic_subject_scope(tmp_path, monkeypatch):
    from runner import ahead, filenames
    root, runs, table = fixture(tmp_path, monkeypatch)
    rows = json.loads(table.read_text(encoding='utf-8'))
    rows[1].update(title='미생물학)', details='실습: 세균의 분리 1', category='practice')
    rows.append(dict(rows[1], date='2026-11-06'))
    table.write_text(json.dumps(rows), encoding='utf-8')
    previous = root / SUBJECT / '필기/2025/1차/[251112_05] 미생물학 실습 세균의 분리1(방예지)_가나다v1.pdf'
    previous.write_bytes(b'fixture')
    current = list(filenames.scan(root / SUBJECT / '필기/2026').files)
    prev = list(filenames.scan(root / SUBJECT / '필기/2025').files)
    seats, _ = ahead.plan(SUBJECT, current, prev, table, runs)
    assert RUN_ID not in {s.cell.key for s in seats}
    pairs = runs / '_pairs'
    pairs.mkdir(parents=True)
    pair_file = pairs / f'{SUBJECT}.json'
    pair_file.write_text(json.dumps({RUN_ID: '251112_05'}), encoding='utf-8')
    seats, _ = ahead.plan(SUBJECT, current, prev, table, runs)
    assert [(s.cell.key, s.prev.key) for s in seats] == [(RUN_ID, '251112_05')]
    # A confirmed slot does not add every other slot with this course label.
    assert '261106_02' not in {s.cell.key for s in seats}
    pair_file.write_text(json.dumps({RUN_ID: '251112_05', '_block_until': '2026-11-04'}), encoding='utf-8')
    seats, _ = ahead.plan(SUBJECT, current, prev, table, runs)
    assert not seats
