from runner import console, status


def test_existing_runner_shows_current_stage_and_details():
    job = status.JobStatus('261001_03', '자율신경계 기초', 42, 'bank',
                           ('정리', '원본 검수'), ('검수 25/80문항',), 2)
    snapshot = status.Snapshot(0, 10, 1, (job,), ())
    output = '\n'.join(console.render(snapshot))
    assert '자율신경계 기초' in output
    assert '원본 검수' in output
    assert '검수 25/80문항' in output


def test_console_follows_new_events_without_repeating_old_ones(monkeypatch, capsys, tmp_path):
    snapshots = iter([
        status.Snapshot(0, 10, 0, (), ('first',)),
        status.Snapshot(1, 10, 0, (), ('first', 'second')),
        status.Snapshot(2, None, 100, (), ('first', 'second')),
    ])
    monkeypatch.setattr(console.status, 'collect', lambda _: next(snapshots))
    monkeypatch.setattr(console.time, 'sleep', lambda _: None)
    assert console.follow(tmp_path) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines.count('first') == 1
    assert lines.count('second') == 1


def test_console_reports_read_failure_without_claiming_runner_stopped():
    snapshot = status.Snapshot(0, None, 0, (), (), error='조회 실패')
    assert console.render(snapshot) == ['조회 실패']
