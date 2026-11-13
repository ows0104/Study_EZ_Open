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
from .status import collect, process_list, option, tail
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


LABELS = {'queued': '차례 대기', 'running': '실행 중', 'held': '보류', 'done': '완료',
          'failed': '실패 · 확인 필요', 'canceled': '취소', 'ready': '시작 가능', 'unavailable': '자료 대기'}
# Flow order on screen: what can start → waiting → running → finished.
SECTIONS = ('choose', 'queue', 'running', 'finished')
FINISHED_ORDER = {'failed': 0, 'canceled': 1, 'done': 2}
# Section buttons: (action sent to the server, caption).
SECTION_BUTTONS = {
    'choose': [('cancel', '취소'), ('start', '시작 / 재개')],
    'queue': [('cancel', '취소'), ('stop', '중지')],
    'finished': [('start', '다시 시작')],
}
LOG_LINES = 40


def state_label(row):
    label = LABELS.get(row['state'], row['state'])
    if row.get('cancelRequested'):
        return '취소 확인 중'
    if row.get('choice') and row['state'] == 'running':
        return '중지 확인 중' if row['choice'] == 'stopped' else '취소 확인 중'
    if row.get('choice') == 'stopped' and row['state'] != 'done':
        return '중지됨' if row['state'] != 'running' else label
    if row.get('choice') == 'canceled' and row['state'] != 'done':
        return '취소 확인 중' if row['state'] in ('queued', 'held') else '취소'
    return label


def section_of(row):
    state = row['state']
    if state == 'running':
        return 'running'
    if state == 'queued':
        return 'queue'
    if state in FINISHED_ORDER:
        return 'finished'
    return 'choose'


def sections(rows, waiting=()):
    """Split desktop task rows into the four on-screen sections, each in display order."""
    found = {key: [] for key in SECTIONS}
    for row in rows:
        found[section_of(row)].append(row)
    order = {(w.get('runId'), w.get('kind')): i for i, w in enumerate(waiting)}
    by_run = {}
    for i, w in enumerate(waiting):
        by_run.setdefault(w.get('runId'), i)
    def place(row):
        return order.get((row['runId'], row['kind']), by_run.get(row['runId'], len(order)))
    found['queue'].sort(key=lambda r: (place(r), r.get('date', ''), r['runId']))
    found['finished'].sort(key=lambda r: r.get('date', ''), reverse=True)
    found['finished'].sort(key=lambda r: FINISHED_ORDER[r['state']])
    return found


def detail_text(row):
    return (row.get('stage') or row.get('reason') or row.get('message') or
            ('수동 시작만 가능' if row.get('manualOnly') else ''))


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
        self.task_rows, self.section_rows = [], {key: [] for key in SECTIONS}
        self.section_keys = {key: () for key in SECTIONS}
        self.card_buttons = []
        self.log_target = None
        self.status_message = ''
        super().__init__(root, runs, interval)
        self.queue_reader = self.client
        root.title('Study EZ 러너')
        root.geometry('1080x1000')
        root.minsize(900, 780)
        for widget in self.overview_views.values():
            widget.configure(height=5)
        style = ttk.Style(root)
        style.configure('Desktop.Treeview', background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        font=(FONT, 10), rowheight=27)
        style.configure('Desktop.Treeview.Heading', background=BG, foreground=MUTED, font=(FONT, 9, 'bold'))
        style.map('Desktop.Treeview', background=[('selected', '#304a60')], foreground=[('selected', TEXT)])
        for table in self.tables.values():
            table.configure(style='Desktop.Treeview')
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.desktop_tick()

    # ── layout ──────────────────────────────────────────────────────────
    def build_before_jobs(self, root):
        toolbar = tk.Frame(root, bg=BG)
        toolbar.pack(fill='x', padx=24, pady=(0, 10))
        self.auto_label = tk.Label(toolbar, bg=BG, fg=GREEN, font=(FONT, 10), anchor='w')
        self.auto_label.pack(side='left', fill='x', expand=True)
        self.cancel_auto = tk.Button(toolbar, text='자동 시작 취소', command=self.cancel_countdown,
                                     bg=PANEL, fg=TEXT, relief='flat', padx=12)
        self.cancel_auto.pack(side='right')
        self.history_button = tk.Button(toolbar, text='이전 블럭 기록', command=self.open_history,
                                        bg=PANEL, fg=TEXT, relief='flat', padx=12)
        self.history_button.pack(side='right', padx=(0, 6))
        self.pause_button = tk.Button(toolbar, text='전체 러너 일시정지', command=self.toggle_pause,
                                      bg=PANEL, fg=AMBER, relief='flat', padx=12)
        self.pause_button.pack(side='right', padx=(0, 6))
        self.tables, self.headers, self.section_buttons = {}, {}, {}
        # ① folded by default: the list of every lecture is long and rarely needed.
        self.choose_open = False
        self.choose_frame = self.section(root, 'choose', [('date', '날짜', 85), ('title', '강의', 300), ('kind', '구분', 70),
                                                          ('state', '상태', 130), ('detail', '필요한 자료 / 메모', 260)],
                                         height=6, toggle=self.toggle_choose)
        self.choose_frame.pack_forget()
        self.queue_frame = self.section(root, 'queue', [('order', '차례', 45), ('date', '날짜', 85), ('title', '강의', 320),
                                                        ('kind', '구분', 70), ('detail', '메모', 300)], height=3)
        self.headers['running'] = self.header(root, 'running')

    def build_controls(self, root):
        self.finished_frame = self.section(root, 'finished', [('date', '날짜', 85), ('title', '강의', 300), ('kind', '구분', 70),
                                                              ('state', '결과', 130), ('detail', '메시지', 260)], height=4)
        self.result_log = tk.Text(self.finished_frame, bg=BG, fg=MUTED, relief='flat', font=(FONT, 9), wrap='word',
                                  height=7, state='disabled', padx=10, pady=8)
        self.result_log.pack(fill='x', pady=(8, 0))
        self.set_text(self.result_log, '완료·실패한 강의를 고르면 그 강의의 마지막 로그가 여기에 보입니다.')

    def header(self, root, key, toggle=None):
        frame = tk.Frame(root, bg=BG)
        frame.pack(fill='x', padx=24, pady=(4, 6))
        if toggle:
            label = tk.Button(frame, command=toggle, bg=BG, fg=TEXT, activebackground=BG, activeforeground=TEXT,
                              relief='flat', borderwidth=0, padx=0, font=(FONT, 11, 'bold'), anchor='w', cursor='hand2')
        else:
            label = tk.Label(frame, bg=BG, fg=TEXT, font=(FONT, 11, 'bold'), anchor='w')
        label.pack(side='left')
        return label

    def section(self, root, key, columns, *, height, toggle=None):
        self.headers[key] = self.header(root, key, toggle)
        frame = tk.Frame(root, bg=PANEL, padx=14, pady=10)
        frame.pack(fill='x', padx=24, pady=(0, 10))
        body = tk.Frame(frame, bg=PANEL)
        body.pack(fill='x')
        holder = tk.Frame(body, bg=PANEL)
        holder.pack(fill='x')
        table = ttk.Treeview(holder, columns=[c[0] for c in columns], show='headings', height=height,
                             selectmode='browse')
        for name, caption, width in columns:
            table.heading(name, text=caption)
            table.column(name, width=width, minwidth=width if name in ('kind', 'state') else 40,
                         stretch=name in ('title', 'detail'))
        scroll = ttk.Scrollbar(holder, command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        table.pack(fill='x', expand=True)
        table.bind('<<TreeviewSelect>>', lambda _, k=key: self.on_select(k))
        self.tables[key] = table
        buttons = tk.Frame(body, bg=PANEL)
        buttons.pack(fill='x', pady=(8, 0))
        self.section_buttons[key] = {}
        for action, caption in SECTION_BUTTONS[key]:
            button = tk.Button(buttons, text=caption, command=lambda a=action, k=key: self.job_action(a, k),
                               bg=PANEL, fg=GREEN if action == 'start' else TEXT, relief='flat', padx=15, state='disabled')
            button.pack(side='right')
            self.section_buttons[key][action] = button
        if key == 'choose':
            self.selection_label = tk.Label(buttons, text='강의를 선택하세요', bg=PANEL, fg=MUTED, font=(FONT, 9), anchor='w')
            self.selection_label.pack(side='left', fill='x', expand=True)
        return frame

    def toggle_choose(self):
        self.choose_open = not self.choose_open
        if self.choose_open:
            # Hide the whole panel: Tk keeps a frame's old size once its last child is unpacked.
            self.choose_frame.pack(fill='x', padx=24, pady=(0, 10), before=self.headers['queue'].master)
        else:
            self.choose_frame.pack_forget()
            self.tables['choose'].selection_remove(*self.tables['choose'].selection())
        self.update_headers()

    def build_cards(self, jobs):
        self.card_buttons = []
        super().build_cards(jobs)

    def card_controls(self, top, job):
        buttons = {}
        for action, caption in [('stop', '중지'), ('cancel', '취소')]:
            button = tk.Button(top, text=caption, command=lambda a=action, r=job.run_id: self.card_action(a, r),
                               bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=TEXT, relief='flat',
                               borderwidth=0, padx=8, font=(FONT, 9), cursor='hand2', state='disabled')
            buttons[action] = button
        buttons['cancel'].pack(side='right')
        buttons['stop'].pack(side='right')
        self.card_buttons.append((job.run_id, buttons))

    # ── selection and actions ───────────────────────────────────────────
    def on_select(self, key):
        if not self.tables[key].selection():
            return
        for other, table in self.tables.items():
            if other != key and table.selection():
                table.selection_remove(*table.selection())
        if key == 'finished':
            self.show_result_log(self.selected())
        self.update_buttons()

    def request(self):
        # StatusWindow starts its first read during construction.
        if hasattr(self, 'queue_reader'):
            self.queue_reader = self.client
        super().request()

    def selected_with_section(self):
        for key, table in getattr(self, 'tables', {}).items():
            chosen = table.selection()
            if chosen:
                row = next((r for r in self.section_rows[key] if self.row_id(r) == chosen[0]), None)
                if row:
                    return row, key
        return None, None

    def selected(self):
        return self.selected_with_section()[0]

    @staticmethod
    def row_id(row):
        return control.job_key(row['subject'], row['runId'], row['kind'])

    def allowed(self, action, row, paused, fresh):
        if not (row and fresh and not self.busy):
            return False
        if action == 'start':
            return (row['ready'] and not paused and row['state'] not in ('running', 'queued', 'done')
                    and not row.get('cancelRequested'))
        if action == 'stop':
            return row['state'] in ('queued', 'running') and not row.get('choice') and not row.get('cancelRequested')
        return row['state'] != 'done' and row.get('choice') != 'canceled' and not row.get('cancelRequested')

    def running_row(self, run_id):
        rows = [r for r in self.section_rows['running'] if r['runId'] == run_id]
        return rows[0] if len(rows) == 1 else None

    def update_buttons(self):
        if not hasattr(self, 'section_buttons'):
            return
        row, key = self.selected_with_section()
        paused = bool(control.read(self.runs).get('paused'))
        fresh = bool(self.snapshot and self.snapshot.queue_checked_at and not self.snapshot.queue_error)
        self.selection_label.configure(text=f"{row['subject']} · {row['title']} · {row['label']}"
                                       if row and key == 'choose' else '강의를 선택하세요')
        for section, buttons in self.section_buttons.items():
            for action, button in buttons.items():
                enabled = section == key and self.allowed(action, row, paused, fresh)
                button.configure(state='normal' if enabled else 'disabled')
        for run_id, buttons in self.card_buttons:
            found = self.running_row(run_id)
            for action, button in buttons.items():
                button.configure(state='normal' if self.allowed(action, found, paused, fresh) else 'disabled')

    def cancel_countdown(self):
        self.auto.cancel()
        self.status_message = '자동 시작을 취소했습니다. 원하는 강의에서 시작을 누르세요.'

    def close(self):
        self.auto.cancel()
        self.closed = True
        self.root.destroy()

    def job_action(self, action, key=None):
        row, section = self.selected_with_section()
        if row and (key is None or key == section):
            self.perform(action, row)

    def card_action(self, action, run_id):
        row = self.running_row(run_id)
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

    def show_result_log(self, row, scroll=True):
        if not row:
            return
        self.log_target = self.row_id(row)
        lines = tail(self.runs / f"agent.{row['runId']}.log", LOG_LINES)
        head = f"{row['title']} · {row['label']} · {state_label(row)}"
        note = row.get('message') or row.get('reason') or ''
        body = '\n'.join(lines) if lines else '이 강의의 로컬 로그가 없습니다.'
        self.set_text(self.result_log, '\n'.join(x for x in (head, note, '', body) if x is not None))
        if scroll:
            self.result_log.see('end')

    # ── render ──────────────────────────────────────────────────────────
    def update_headers(self):
        rows = self.section_rows
        ready = sum(1 for r in rows['choose'] if r['state'] == 'ready')
        waiting = sum(1 for r in rows['choose'] if r['state'] == 'unavailable')
        others = len(rows['choose']) - ready - waiting
        parts = [f'시작 가능 {ready}'] + ([f'자료 대기 {waiting}'] if waiting else []) + ([f'보류·중지 {others}'] if others else [])
        self.headers['choose'].configure(text=f"{'▾' if self.choose_open else '▸'}  시작할 수 있는 강의   " + ' · '.join(parts))
        self.headers['queue'].configure(text=f"대기열   {len(rows['queue'])}")
        self.headers['running'].configure(text=f'실행 중   {len(self.snapshot.jobs) if self.snapshot else 0}')
        failed = sum(1 for r in rows['finished'] if r['state'] == 'failed')
        done = sum(1 for r in rows['finished'] if r['state'] == 'done')
        self.headers['finished'].configure(text=f'완료 · 실패   완료 {done} · 실패 {failed}' +
                                           (f" · 취소 {len(rows['finished']) - done - failed}" if len(rows['finished']) - done - failed else ''),
                                           fg=AMBER if failed else TEXT)

    def fill(self, key, rows):
        table = self.tables[key]
        selected = table.selection()
        ids = tuple(self.row_id(row) for row in rows)
        if ids != self.section_keys[key]:
            table.delete(*table.get_children())
            for row_id in ids:
                table.insert('', 'end', iid=row_id)
            self.section_keys[key] = ids
            if selected and selected[0] in ids:
                table.selection_set(selected[0])
        table.configure(height=max(3, min(len(rows), 8 if key == 'choose' else 5)))
        for number, row in enumerate(rows, 1):
            if key == 'queue':
                values = (number, row['date'][5:], row['title'], row['label'], detail_text(row))
            else:
                values = (row['date'][5:], row['title'], row['label'], state_label(row),
                          row.get('message') or detail_text(row) if key == 'finished' else detail_text(row))
            table.item(self.row_id(row), values=values)

    def render(self, snapshot, phase_info=None):
        self.full_snapshot = snapshot
        snapshot, _ = history.split(snapshot)
        value = snapshot.queue or {}
        self.task_rows = value.get('tasks', [])
        self.section_rows = sections(self.task_rows, value.get('waiting', []))
        super().render(snapshot, phase_info)
        self.waiting_label.configure(text='다른 세션 작업 · 별도 러너')
        for key in ('choose', 'queue', 'finished'):
            self.fill(key, self.section_rows[key])
        self.update_headers()
        if self.log_target and self.log_target in self.section_keys['finished']:
            row = next(r for r in self.section_rows['finished'] if self.row_id(r) == self.log_target)
            self.show_result_log(row, scroll=False)
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
