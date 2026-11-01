import json

from runner.status import collect, Snapshot
from runner.status_batch import overview


def test_batch_displays_all_workers_history_and_queue_without_false_completion(tmp_path):
    registry = tmp_path / 'runs/status-jobs'
    registry.mkdir(parents=True)
    marker = tmp_path / 'work/state.json'
    marker.parent.mkdir()
    (registry / 'batch.json').write_text(json.dumps(dict(
        id='batch', label='연결 보완', script='work/engine.py', state_file='work/state.json',
        outputs='work', log='work/log', targets={}, activity='metadata', overview=True,
        stages={'author': '보완 중', 'review': '검수 중', 'applied': '반영 완료'})), encoding='utf-8')
    marker.write_text(json.dumps(dict(pid=50, run_id='a', states={
        'a': dict(title='강의1', stage='author'),
        'b': dict(title='강의2', stage='review'),
        'c': dict(title='강의3', stage='applied', added=['LNK1'], removed=[]),
        'd': dict(title='강의4', stage='queued'),
        'e': dict(title='강의5', stage='held-limit')})), encoding='utf-8')
    processes = [dict(ProcessId=50, ParentProcessId=1, CommandLine='python work/engine.py')]
    snapshot = collect(tmp_path / 'runs', processes)
    groups = overview(snapshot)
    assert [job.title for job in snapshot.jobs] == ['강의1', '강의2']
    assert len(groups['done']) == len(groups['pending']) == len(groups['attention']) == 1
    assert '추가 1 / 제외 0' in groups['done'][0]
    stopped = overview(collect(tmp_path / 'runs', []))
    assert not stopped['active'] and len(stopped['attention']) == 3
    assert len(stopped['done']) == 1  # Historical completion survives process exit.


def test_unrelated_server_holds_are_separate_from_batch_errors():
    groups = overview(Snapshot(1, None, None, (), (), queue={
        'held':[{'runId':'elsewhere', 'title':'별도 강의', 'message':'하루 상한'}]}))
    assert groups['attention'] == []
    assert groups['other'] == ['별도 강의 · 하루 상한']
