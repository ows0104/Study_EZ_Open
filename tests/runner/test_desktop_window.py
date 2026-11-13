import queue
import time
import tkinter as tk

import pytest

from runner import desktop, desktop_control as control
from runner.status import Snapshot, JobStatus
from runner.status_window import StatusWindow


class Client:
    next_read = 0

    def __init__(self):
        self.calls = []

    def call(self, action, row=None):
        self.calls.append((action, row))
        return {}


@pytest.fixture(scope='module')
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def window(tmp_path, monkeypatch, tk_root):
    root = tk_root
    monkeypatch.setattr(root, 'after', lambda *args: None)
    monkeypatch.setattr(StatusWindow, 'request', lambda self: None)
    client, starts = Client(), []
    view = desktop.DesktopWindow(root, tmp_path, client=client, start_agent=lambda: starts.append(True))
    yield view, client, starts
    for child in root.winfo_children():
        child.destroy()


def snapshot():
    rows = [dict(subject='감염과 면역', runId='261102_01', title='항원과 항체', date='2026-11-02',
                 kind=kind, label=label, state='ready', ready=True, reason='', stage='', choice='', jobId=None)
            for kind, label in [('pre', '예습'), ('bank', '복습')]]
    return Snapshot(time.time(), 10, 1, (), (), queue={'tasks': rows}, queue_checked_at=time.time())


def finish(view):
    message = view.actions.get(timeout=3)
    view.actions.put(message)
    view.desktop_tick()


def test_selected_lecture_kind_is_the_only_action_target(window):
    view, client, starts = window
    value = snapshot()
    view.render(value)
    row = value.queue['tasks'][1]
    view.tables['choose'].selection_set(view.row_id(row))
    view.on_select('choose')
    view.section_buttons['choose']['start'].invoke()
    finish(view)
    assert client.calls == [('start', row)]
    assert starts == [True]
    assert not view.auto.pending


def test_no_input_starts_once_at_60_seconds(window, monkeypatch):
    view, client, starts = window
    view.render(snapshot())
    deadline = view.auto.deadline
    monkeypatch.setattr(desktop.time, 'monotonic', lambda: deadline - .001)
    view.desktop_tick()
    assert client.calls == []
    monkeypatch.setattr(desktop.time, 'monotonic', lambda: deadline)
    view.desktop_tick()
    finish(view)
    view.desktop_tick()
    assert client.calls == [('auto', None)]
    assert starts == [True]


def test_cancel_at_deadline_prevents_all_auto_work(window, monkeypatch):
    view, client, starts = window
    view.render(snapshot())
    view.cancel_auto.invoke()
    monkeypatch.setattr(desktop.time, 'monotonic', lambda: view.auto.deadline + 1000)
    view.desktop_tick()
    assert client.calls == starts == []


def test_unknown_server_state_never_autostarts(window, monkeypatch):
    view, client, _ = window
    monkeypatch.setattr(desktop.time, 'monotonic', lambda: view.auto.deadline + 1)
    view.desktop_tick()
    assert not view.auto.pending
    assert client.calls == []
    assert '보류' in view.status_message


def test_close_cancels_countdown_without_stopping_runner(window, monkeypatch):
    view, client, starts = window
    monkeypatch.setattr(view.root, 'destroy', lambda: None)
    view.close()
    assert not view.auto.pending
    assert client.calls == starts == []


def test_global_pause_disables_start_and_survives_reopen(window):
    view, client, starts = window
    with control.locked(view.runs):
        control.write(view.runs, dict(paused=True, jobs={}))
    view.render(snapshot())
    view.tables['choose'].selection_set(view.tables['choose'].get_children()[0])
    view.desktop_tick()
    assert not view.auto.pending
    assert view.pause_button.cget('text') == '전체 러너 재개'
    assert view.section_buttons['choose']['start'].cget('state') == 'disabled'


def test_stop_is_not_shown_as_acknowledged_while_worker_is_running(window):
    view, _, _ = window
    value = snapshot()
    row = value.queue['tasks'][0]
    row.update(state='running', choice='stopped')
    view.render(value)
    assert desktop.state_label(row) == '중지 확인 중'
    assert view.section_rows['running'] == [row]


def test_client_failure_is_visible_without_automatic_retry(window):
    view, client, starts = window
    def fail(*args):
        raise ValueError('필수 자료가 없습니다.')
    client.call = fail
    view.perform('auto')
    finish(view)
    assert '필수 자료' in view.status_message
    assert not view.auto.pending
    assert starts == []


def test_previous_block_never_appears_on_first_screen(window):
    from dataclasses import replace
    view, _, _ = window
    value = snapshot()
    old = dict(subject='약리학', runId='261002_01', title='옛 약리학', state='held', kind='bank', message='기존 보류')
    value.queue.update(jobs=[old], running=[], held=[old], waiting=[old])
    value = replace(value, jobs=(JobStatus('batch/261002_01', '옛 약리학', 2, '복습', ('보류',), (), 1),),
                    batches=(dict(label='옛 기록', done=[dict(runId='261002_01', title='옛 완료', stage='완료')]),))
    view.render(value)
    assert len(view.task_rows) == 2
    assert '완료 0개' in view.state.cget('text') and '실행 중 0개' in view.state.cget('text')
    assert '옛' not in view.overview_views['done'].get('1.0', 'end')
    assert '옛' not in view.overview_views['other'].get('1.0', 'end')
    assert view.full_snapshot.batches  # retained for history, never removed


def test_history_button_saves_a_copy_without_starting_work(window, monkeypatch):
    view, client, starts = window
    view.render(snapshot())
    captured = []
    def open_window(root, load):
        captured.append(load())
        return None
    monkeypatch.setattr(desktop.history, 'open_window', open_window)
    view.history_button.invoke()
    assert client.calls == [('history', None)] and starts == []
    assert captured[0][1].is_file()
    assert not view.auto.pending


def test_maintenance_reopen_does_not_rearm_auto_start(window):
    view, client, _ = window
    # A new maintenance window uses this option without touching the worker.
    view.close = lambda: None
    other = desktop.DesktopWindow(view.root, view.runs, client=client, start_agent=lambda: None, auto_start=False)
    assert not other.auto.pending and client.calls == []


def test_history_window_has_no_execution_or_edit_controls(window):
    from runner import history
    view, client, starts = window
    top = history.open_window(view.root, lambda: ({}, view.runs / 'saved.json'))
    top.withdraw()
    def descendants(widget):
        return [child for item in widget.winfo_children() for child in [item, *descendants(item)]]
    widgets = descendants(top)
    assert top.title() == 'Study EZ · 이전 블럭 기록'
    assert not any(isinstance(widget, tk.Button) for widget in widgets)
    assert all(widget.cget('state') == 'disabled' for widget in widgets if isinstance(widget, tk.Text))
    assert client.calls == starts == []
    top.destroy()


def flow_rows():
    def row(run_id, state, date, kind='bank', **extra):
        return dict(subject='감염과 면역', runId=run_id, title=f'강의 {run_id}', date=date, kind=kind,
                    label='복습' if kind == 'bank' else '예습', state=state, ready=state != 'unavailable',
                    reason='', stage='', jobId=None, **{'choice': '', **extra})
    return [row('261101_01', 'ready', '2026-11-01'), row('261101_02', 'unavailable', '2026-11-01'),
            row('261102_01', 'queued', '2026-11-02'), row('261102_02', 'queued', '2026-11-02'),
            row('261103_01', 'running', '2026-11-03'),
            row('261104_01', 'done', '2026-11-04'), row('261105_01', 'failed', '2026-11-05', message='검수 실패'),
            row('261103_02', 'failed', '2026-11-03'), row('261106_01', 'held', '2026-11-06', choice='stopped')]


def test_rows_split_into_flow_sections_in_display_order():
    rows = flow_rows()
    waiting = [dict(runId='261102_02', kind='bank'), dict(runId='261102_01', kind='bank')]
    found = desktop.sections(rows, waiting)
    ids = {key: [r['runId'] for r in value] for key, value in found.items()}
    assert ids['choose'] == ['261101_01', '261101_02', '261106_01']
    assert ids['queue'] == ['261102_02', '261102_01']  # server order, not date
    assert ids['running'] == ['261103_01']
    assert ids['finished'] == ['261105_01', '261103_02', '261104_01']  # failures first, newest first


def flow_snapshot():
    rows = flow_rows()
    return Snapshot(time.time(), 10, 1, (), (), queue={'tasks': rows, 'waiting': []}, queue_checked_at=time.time())


def test_choose_section_starts_folded_and_each_section_offers_only_its_actions(window):
    view, client, _ = window
    view.render(flow_snapshot())
    assert not view.choose_frame.winfo_manager()
    assert view.headers['choose'].cget('text').startswith('▸')
    assert '시작 가능 1' in view.headers['choose'].cget('text')
    assert view.headers['queue'].cget('text').endswith('2')
    assert set(view.section_buttons['queue']) == {'stop', 'cancel'}
    assert set(view.section_buttons['finished']) == {'start'}
    view.toggle_choose()
    assert view.choose_frame.winfo_manager() and view.headers['choose'].cget('text').startswith('▾')
    queued = view.section_rows['queue'][0]
    view.tables['queue'].selection_set(view.row_id(queued))
    view.on_select('queue')
    assert view.section_buttons['queue']['stop'].cget('state') == 'normal'
    assert view.section_buttons['choose']['start'].cget('state') == 'disabled'
    view.section_buttons['queue']['stop'].invoke()
    finish(view)
    assert client.calls == [('stop', queued)]


def test_selecting_in_one_section_clears_the_others(window):
    view, _, _ = window
    view.render(flow_snapshot())
    view.toggle_choose()
    view.tables['choose'].selection_set(view.tables['choose'].get_children()[0])
    view.on_select('choose')
    view.tables['queue'].selection_set(view.tables['queue'].get_children()[0])
    view.on_select('queue')
    assert not view.tables['choose'].selection()
    assert view.selected()['state'] == 'queued'


def test_finished_row_shows_its_log_tail_and_failed_can_restart(window):
    view, client, _ = window
    (view.runs / 'agent.261105_01.log').write_text('── 검수\n마지막 오류 줄\n', encoding='utf-8')
    view.render(flow_snapshot())
    failed = view.section_rows['finished'][0]
    view.tables['finished'].selection_set(view.row_id(failed))
    view.on_select('finished')
    text = view.result_log.get('1.0', 'end')
    assert '마지막 오류 줄' in text and '검수 실패' in text
    assert view.section_buttons['finished']['start'].cget('state') == 'normal'
    done = view.section_rows['finished'][-1]
    view.tables['finished'].selection_set(view.row_id(done))
    view.on_select('finished')
    assert '로컬 로그가 없습니다' in view.result_log.get('1.0', 'end')
    assert view.section_buttons['finished']['start'].cget('state') == 'disabled'


def test_running_card_offers_stop_for_its_lecture(window):
    view, client, _ = window
    value = flow_snapshot()
    from dataclasses import replace
    value = replace(value, jobs=(JobStatus('261103_01', '강의 261103_01', 5, '복습', ('검토',), (), 1),))
    view.render(value)
    run_id, buttons = view.card_buttons[0]
    assert run_id == '261103_01' and buttons['stop'].cget('state') == 'normal'
    buttons['stop'].invoke()
    finish(view)
    assert client.calls == [('stop', view.section_rows['running'][0])]
