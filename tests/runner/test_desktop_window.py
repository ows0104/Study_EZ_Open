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
    view.table.selection_set(view.row_id(row))
    view.update_buttons()
    view.job_buttons['start'].invoke()
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
    view.table.selection_set(view.table.get_children()[0])
    view.desktop_tick()
    assert not view.auto.pending
    assert view.pause_button.cget('text') == '전체 러너 재개'
    assert view.job_buttons['start'].cget('state') == 'disabled'


def test_stop_is_not_shown_as_acknowledged_while_worker_is_running(window):
    view, _, _ = window
    value = snapshot()
    row = value.queue['tasks'][0]
    row.update(state='running', choice='stopped')
    view.render(value)
    assert view.table.item(view.row_id(row), 'values')[3] == '중지 확인 중'


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
