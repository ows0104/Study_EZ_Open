from copy import deepcopy
from dataclasses import asdict
import json

from runner import history
from runner.status import JobStatus, Snapshot


def example():
    current = dict(subject='감염과 면역', runId='261103_01', title='내일 예습', kind='pre', state='running', id=50)
    old = dict(subject='약리학', runId='261002_01', title='옛 약리학', kind='bank', state='failed', id=1, message='상한 도달')
    # The same run ID in a different subject must not leak into the default view.
    other = dict(current, subject='다른 과목', id=4, title='다른 과목')
    value = dict(tasks=[dict(current, date='2026-11-03')], jobs=[current, old, other],
                 running=[current, other], waiting=[old], held=[old],
                 scopeInfo=dict(subjects=['감염과 면역'], since='2026-11-02', until='2026-11-26'))
    batch = dict(label='지난 일괄 작업', done=[dict(runId='261002_02', title='옛 완료', stage='반영 완료')],
                 attention=[dict(runId='261002_01', title='옛 오류', stage='상한', error='검수 상한')])
    jobs = (JobStatus('261103_01', '내일 예습', 1, '예습', ('생성 중',), (), 1),
            JobStatus('batch/261002_01', '옛 약리학', 2, '복습', ('검수',), (), 1),
            JobStatus('261103_01', '같은 ID 다른 과목', 3, '복습', ('검수',), (), 1, subject='다른 과목'))
    return Snapshot(1, 10, 1, jobs, ('261002_01 옛 기록', '261103_01 생성 중'), queue=value, batches=(batch,))


def test_default_scope_filters_cards_counts_and_subjects_without_changing_records():
    original = example()
    before = deepcopy(asdict(original))
    current, old = history.split(original)
    assert [job.title for job in current.jobs] == ['내일 예습']
    assert current.batches == ()
    assert len(current.queue['running']) == len(current.queue['jobs']) == 1
    assert current.queue['waiting'] == current.queue['held'] == []
    assert current.events == ('261103_01 생성 중',)
    assert len(old['server']) == 2 and len(old['jobs']) == 2
    assert old['batches'][0]['attention'][0]['error'] == '검수 상한'
    assert asdict(original) == before


def test_unknown_current_scope_does_not_fall_back_to_old_work():
    source = example()
    from dataclasses import replace
    source = replace(source, queue={})
    current, old = history.split(source)
    assert not current.jobs and not current.batches and not current.events
    assert len(old['jobs']) == 3


def test_additive_history_is_complete_idempotent_and_preserves_originals(tmp_path):
    runs = tmp_path / 'runs'
    runs.mkdir()
    original = runs / 'agent.log'
    original.write_text('원본 기록', encoding='utf-8')
    source = example()
    server = dict(records=[dict(id=i, runId='261002_01', subject='약리학', state='failed', message='실패 원문') for i in range(80)])
    data = history.document(source, server, runs)
    first = history.save(runs, data)
    assert history.save(runs, data) == first
    assert original.read_text(encoding='utf-8') == '원본 기록'
    restored = json.loads(first.read_text(encoding='utf-8'))['data']
    assert len(restored['server']) == 80
    assert restored['batches'][0]['done'][0]['title'] == '옛 완료'
    changed = deepcopy(data)
    changed['server'][0]['message'] = '후속 결과'
    second = history.save(runs, changed)
    assert second != first and first.is_file()
    assert len(list(first.parent.glob('history-*.json'))) == 2


def test_history_rows_preserve_failed_and_incomplete_states():
    _, old = history.split(example())
    entries = history.rows(old)
    assert any('실패' in row for row in entries)
    assert any('확인 필요' in row for row in entries)
    assert any('옛 완료' in row for row in entries)


def test_history_export_uses_current_scope_from_the_same_server_query(tmp_path):
    source = example()
    from dataclasses import replace
    source = replace(source, queue={})
    data = history.document(source, dict(records=[], scopeKeys=[dict(subject='감염과 면역', runId='261103_01')]), tmp_path)
    assert all(row['title'] != '내일 예습' for row in data['jobs'])


def test_default_counts_use_latest_current_task_status_only():
    from runner.status_batch import overview
    source = example()
    source.queue['tasks'][0].update(state='failed', message='현재 작업 실패')
    visible, _ = history.split(source)
    assert overview(visible)['done'] == []
    assert overview(visible)['attention'] == ['내일 예습 · pre · 현재 작업 실패']
    source.queue['tasks'][0].update(state='done', message='완료')
    visible, _ = history.split(source)
    assert len(overview(visible)['done']) == 1 and overview(visible)['attention'] == []
