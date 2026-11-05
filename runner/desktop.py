"""Study EZ desktop: lecture-level preview/review controls without a console."""
from __future__ import annotations

import argparse
import json
import math
import os
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import desktop_control as control
from . import history
from .background import launch
from .status import collect, process_list, option
from .status_window import StatusWindow, BG, PANEL, TEXT, MUTED, GREEN, AMBER, FONT

ROOT = Path(__file__).resolve().parents[1]


class JobClient:
    def __init__(self, root: Path):
        self.root, self.next_read = root, 0
        self.value, self.checked_at, self.error = {}, 0, ''

    def call(self, action, row=None):
        env = os.environ.copy()
        for key in ('PYTHONHOME', 'UV_INTERNAL__PYTHONHOME'):
            env.pop(key, None)
        result = subprocess.run(
            [str(self.root / 'server/.venv/Scripts/python.exe'), str(self.root / 'scripts/runner_desktop_jobs.py')],
            input=json.dumps({'action': action, **({k: row[k] for k in ('subject', 'runId', 'kind')} if row else {})}),
            cwd=self.root, env=env, encoding='utf-8', errors='replace', capture_output=True, timeout=45,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=True)
        value = json.loads(result.stdout)
        if not value.get('ok'):
            raise ValueError(value.get('error') or '작업을 처리하지 못했습니다.')
        return value.get('value', {})

    def read(self):
        if time.monotonic() >= self.next_read:
            try:
                self.value, self.checked_at, self.error = self.call('read'), time.time(), ''
            except (OSError, ValueError, subprocess.SubprocessError):
                self.error = '강의 작업 조회 실패 · 이전 상태 유지 · 다시 확인합니다.'
            self.next_read = time.monotonic() + 5
        return self.value, self.checked_at, self.error


def ensure_agent(root: Path):
    """Serialize launches across windows; never guess that a failed query means idle."""
    runs = root / 'runs'
    with control.locked(runs):
        processes = process_list()
        snapshot = collect(runs, processes=processes)
        if snapshot.agent_pid:
            return
        # Also recognize a just-launched interpreter before it writes agent.lock.
        for process in processes:
            command = process.get('CommandLine') or ''
            if re.search(r'-m\s+runner\s+agent\b', command) and option(command, '--runs'):
                if Path(option(command, '--runs')).resolve() == runs.resolve():
                    return
        lock = runs / 'agent.lock'
        if lock.exists() and time.time() - lock.stat().st_mtime < 90:
            raise ValueError('기존 러너 종료를 확인 중입니다. 잠시 뒤 시작해 주세요.')
        # Match scripts/agent.ps1. A uv proxy can run here but fail when the
        # authoring worker launches the same executable to inspect a PDF.
        runtime = next((path for path in (Path.home() / 'anaconda3/python.exe',
                                         Path.home() / 'miniconda3/python.exe',
                                         root / '.venv/Scripts/python.exe') if path.is_file()),
                       root / '.venv/Scripts/python.exe')
        if not runtime.is_file():
            raise ValueError('러너 실행 환경을 찾지 못했습니다.')
        process = launch([str(runtime), '-u', '-m', 'runner', 'agent', '--runs', str(runs)],
                         cwd=root, log=runs / 'agent.log')
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if lock.exists() and time.time() - lock.stat().st_mtime < 5:
                return
            if process.poll() is not None:
                raise ValueError('러너를 시작하지 못했습니다. 상세 기록에서 시간표·자료 상태를 확인해 주세요.')
            time.sleep(0.25)
        raise ValueError('러너 시작 확인이 지연되고 있습니다. 다시 조회한 뒤 확인해 주세요.')


class DesktopWindow(StatusWindow):
    def __init__(self, root, runs, interval=5, *, client=None, start_agent=None, auto_start=True):
        self.client = client or JobClient(runs.resolve().parent)
        self.start_agent = start_agent or (lambda: ensure_agent(runs.resolve().parent))
        self.auto = control.AutoStart(time.monotonic())
        if not auto_start:
            self.auto.cancel()
        self.full_snapshot = None
        self.history_window = None
        self.actions = queue.Queue()
        self.busy, self.closed = False, False
        self.task_rows, self.task_keys = [], ()
        self.status_message = ''
        super().__init__(root, runs, interval)
        self.queue_reader = self.client
        root.title('Study EZ 러너')
        root.geometry('1080x940')
        root.minsize(900, 780)
        self.job_canvas.configure(height=130)
        for widget in self.overview_views.values():
            widget.configure(height=5)
        style = ttk.Style(root)
        style.configure('Desktop.Treeview', background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        font=(FONT, 10), rowheight=27)
        style.configure('Desktop.Treeview.Heading', background=BG, foreground=MUTED, font=(FONT, 9, 'bold'))
        style.map('Desktop.Treeview', background=[('selected', '#304a60')], foreground=[('selected', TEXT)])
        self.table.configure(style='Desktop.Treeview')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.desktop_tick()

    def build_controls(self, root):
        frame = tk.Frame(root, bg=PANEL, padx=14, pady=12)
        frame.pack(fill='x', padx=24, pady=(0, 10))
        toolbar = tk.Frame(frame, bg=PANEL)
        toolbar.pack(fill='x')
        self.auto_label = tk.Label(toolbar, bg=PANEL, fg=GREEN, font=(FONT, 10), anchor='w')
        self.auto_label.pack(side='left', fill='x', expand=True)
        self.cancel_auto = tk.Button(toolbar, text='자동 시작 취소', command=self.cancel_countdown,
                                     bg=PANEL, fg=TEXT, relief='flat', padx=12)
        self.cancel_auto.pack(side='right')
        self.history_button = tk.Button(toolbar, text='이전 블럭 기록', command=self.open_history,
                                        bg=PANEL, fg=TEXT, relief='flat', padx=12)
        self.history_button.pack(side='right')
        self.pause_button = tk.Button(toolbar, text='전체 러너 일시정지', command=self.toggle_pause,
                                      bg=PANEL, fg=AMBER, relief='flat', padx=12)
        self.pause_button.pack(side='right')
        tk.Label(frame, text='강의와 예습·복습을 선택하세요. 중지는 자료를 보존하며, 취소한 작업은 자동으로 시작하지 않습니다.',
                 bg=PANEL, fg=MUTED, font=(FONT, 9), anchor='w').pack(fill='x', pady=(8, 6))
        table = tk.Frame(frame, bg=PANEL)
        table.pack(fill='x')
        self.table = ttk.Treeview(table, columns=('date', 'title', 'kind', 'state', 'detail'), show='headings', height=7)
        for name, label, width in [('date', '날짜', 85), ('title', '강의', 300), ('kind', '구분', 55),
                                   ('state', '상태', 100), ('detail', '진행 / 필요한 자료', 260)]:
            self.table.heading(name, text=label)
            self.table.column(name, width=width, minwidth=45, stretch=name in ('title', 'detail'))
        scroll = ttk.Scrollbar(table, command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.table.pack(fill='both', expand=True)
        self.table.bind('<<TreeviewSelect>>', lambda _: self.update_buttons())
        buttons = tk.Frame(frame, bg=PANEL)
        buttons.pack(fill='x', pady=(8, 0))
        self.selection_label = tk.Label(buttons, text='강의를 선택하세요', bg=PANEL, fg=MUTED, font=(FONT, 9), anchor='w')
        self.selection_label.pack(side='left', fill='x', expand=True)
        self.job_buttons = {}
        for action, caption in [('cancel', '취소'), ('stop', '중지'), ('start', '시작 / 재개')]:
            button = tk.Button(buttons, text=caption, command=lambda a=action: self.job_action(a),
                               bg=PANEL, fg=GREEN if action == 'start' else TEXT, relief='flat', padx=15, state='disabled')
            button.pack(side='right')
            self.job_buttons[action] = button

    def request(self):
        # StatusWindow starts its first read during construction.
        if hasattr(self, 'queue_reader'):
            self.queue_reader = self.client
        super().request()

    def selected(self):
        selected = self.table.selection()
        return next((r for r in self.task_rows if self.row_id(r) in selected), None)

    @staticmethod
    def row_id(row):
        return control.job_key(row['subject'], row['runId'], row['kind'])

    def update_buttons(self):
        row = self.selected()
        paused = bool(control.read(self.runs).get('paused'))
        fresh = bool(self.snapshot and self.snapshot.queue_checked_at and not self.snapshot.queue_error)
        self.selection_label.configure(text=f"{row['subject']} · {row['title']} · {row['label']}" if row else '강의를 선택하세요')
        for action, button in self.job_buttons.items():
            enabled = bool(row and fresh and not self.busy)
            if row:
                if action == 'start':
                    enabled &= row['ready'] and not paused and row['state'] not in ('running', 'queued', 'done') and not row.get('cancelRequested')
                elif action == 'stop':
                    enabled &= row['state'] in ('queued', 'running') and not row.get('choice') and not row.get('cancelRequested')
                else:
                    enabled &= row['state'] != 'done' and row.get('choice') != 'canceled' and not row.get('cancelRequested')
            button.configure(state='normal' if enabled else 'disabled')

    def cancel_countdown(self):
        self.auto.cancel()
        self.status_message = '자동 시작을 취소했습니다. 원하는 강의에서 시작을 누르세요.'

    def close(self):
        self.auto.cancel()
        self.closed = True
        self.root.destroy()

    def job_action(self, action):
        row = self.selected()
        if row:
            self.perform(action, row)

    def toggle_pause(self):
        self.perform('resume' if control.read(self.runs).get('paused') else 'pause')

    def open_history(self):
        self.auto.cancel()
        if self.history_window is not None and self.history_window.winfo_exists():
            self.history_window.lift()
            return
        def load():
            server = self.client.call('history')
            snapshot = self.full_snapshot or collect(self.runs)
            data = history.document(snapshot, server, self.runs)
            return data, history.save(self.runs, data)
        self.history_window = history.open_window(self.root, load)

    def perform(self, action, row=None):
        self.auto.cancel()
        if self.busy:
            return
        self.busy = True
        self.status_message = '작업 요청을 처리 중입니다…'
        self.update_buttons()
        def run():
            try:
                self.client.call(action, row)
                if action in ('start', 'auto', 'resume'):
                    self.start_agent()
                messages = {'start': '선택한 작업을 시작합니다.', 'stop': '선택한 작업의 중지를 요청했습니다.',
                            'cancel': '선택한 작업을 취소했습니다.', 'pause': '전체 일시정지 요청 · 실행 작업이 멈추는 것을 확인 중입니다.',
                            'resume': '전체 러너를 재개합니다.', 'auto': '준비된 신규 작업을 자동 대기열에 등록했습니다.'}
                self.actions.put(messages[action])
            except ValueError as error:
                self.actions.put(str(error))
            except Exception:
                self.actions.put('작업 요청 실패 · 연결 상태를 확인한 뒤 다시 시도해 주세요.')
        threading.Thread(target=run, daemon=True, name='runner-desktop-action').start()

    def render(self, snapshot):
        self.full_snapshot = snapshot
        snapshot, _ = history.split(snapshot)
        super().render(snapshot)
        self.waiting_label.configure(text='이번 블럭 작업')
        self.task_rows = (snapshot.queue or {}).get('tasks', [])
        selected = self.table.selection()
        ids = tuple(self.row_id(row) for row in self.task_rows)
        if ids != self.task_keys:
            self.table.delete(*self.table.get_children())
            for row_id in ids:
                self.table.insert('', 'end', iid=row_id)
            self.task_keys = ids
            if selected and selected[0] in ids:
                self.table.selection_set(selected[0])
        labels = {'queued': '차례 대기', 'running': '실행 중', 'held': '보류', 'done': '완료',
                  'failed': '실패 · 확인 필요', 'canceled': '취소', 'ready': '시작 가능', 'unavailable': '자료 대기'}
        for row in self.task_rows:
            label = labels.get(row['state'], row['state'])
            if row.get('cancelRequested'):
                label = '취소 확인 중'
            elif row.get('choice') and row['state'] == 'running':
                label = '중지 확인 중' if row['choice'] == 'stopped' else '취소 확인 중'
            elif row.get('choice') == 'stopped' and row['state'] != 'done':
                label = '중지됨' if row['state'] != 'running' else label
            elif row.get('choice') == 'canceled' and row['state'] != 'done':
                label = '취소 확인 중' if row['state'] in ('queued', 'held') else '취소'
            self.table.item(self.row_id(row), values=(row['date'][5:], row['title'], row['label'], label,
                            row.get('stage') or row.get('reason') or row.get('message') or ('수동 시작만 가능' if row.get('manualOnly') else '')))
        self.update_buttons()

    def desktop_tick(self):
        if self.closed:
            return
        try:
            self.status_message = self.actions.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.client.next_read = 0
            self.refresh_now()
        state = control.read(self.runs)
        paused = bool(state.get('paused'))
        if paused:
            self.auto.cancel()
        self.pause_button.configure(text='전체 러너 재개' if paused else '전체 러너 일시정지', state='disabled' if self.busy else 'normal')
        self.cancel_auto.configure(state='normal' if self.auto.pending else 'disabled')
        if self.auto.pending:
            remaining = max(0, math.ceil(self.auto.deadline - time.monotonic()))
            self.auto_label.configure(text=f'선택이 없으면 {remaining}초 뒤 준비된 신규 작업을 시작합니다.')
            if self.auto.due(time.monotonic()):
                if self.snapshot and self.snapshot.queue_checked_at and not self.snapshot.queue_error:
                    self.perform('auto')
                else:
                    self.status_message = '강의 상태를 확인하지 못해 자동 시작을 보류했습니다. 새로고침 후 선택해 주세요.'
        else:
            self.auto_label.configure(text=self.status_message or ('전체 일시정지 중 · 재개하면 보존한 단계부터 이어 갑니다.' if paused else '강의별로 시작·중지·취소할 수 있습니다.'))
        self.update_buttons()
        self.root.after(250, self.desktop_tick)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=ROOT / 'runs')
    parser.add_argument('--no-auto-start', action='store_true', help='화면만 갱신하며 자동 시작 대기를 다시 켜지 않는다')
    args = parser.parse_args()
    root = tk.Tk()
    DesktopWindow(root, args.runs, auto_start=not args.no_auto_start)
    root.mainloop()


if __name__ == '__main__':
    main()
