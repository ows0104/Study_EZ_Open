"""Compact desktop monitor for running jobs and the server queue.

One card per running lecture, all visible. A Main-Quiz card shows where it is in six
plain phases and a bar filled by time (elapsed / (elapsed + usual remaining)).
When there is no estimate there is no bar and no number. Lists and raw logs fold away.
"""
from __future__ import annotations

import argparse
import queue
import threading
import time
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import ttk

from . import status_phases as phases
from .status import JobStatus, Snapshot, collect
from .status_queue import QueueReader, duration
from .status_eta import estimate
from .status_batch import overview

BG, PANEL, LINE = '#0f1620', '#18212d', '#273444'
TEXT, MUTED, GREEN, AMBER = '#eef2f6', '#8d9aab', '#6fd3a8', '#e9bf79'
DIM = '#56657a'
FONT = '맑은 고딕'
LISTS = [('active', '하는 거'), ('done', '한 거'), ('pending', '할 거'), ('attention', '확인 필요'), ('other', '별도 러너 보류')]
TYPICAL_TTL = 600


def step_text(stage: str, row: dict) -> str:
    """Reported step counts stay as text; they never drive the bar."""
    total, index = row.get('stageTotal', 0), row.get('stageIndex', 0)
    return (f'단계 {index}/{total}  ·  ' if total else '') + stage


def minutes(seconds: float) -> str:
    value = max(1, round(seconds / 60))
    hours, rest = divmod(value, 60)
    return f'{hours}시간 {rest}분' if hours else f'{value}분'


def clock(at: float, now: float) -> str:
    from datetime import datetime
    day = '내일 ' if datetime.fromtimestamp(at).date() > datetime.fromtimestamp(now).date() else ''
    return day + time.strftime('%H:%M', time.localtime(at))


def waiting_text(value: dict) -> str:
    rows = value.get('waiting', [])
    return '\n'.join(f"{i}. {row.get('title', row['runId'])}" for i, row in enumerate(rows, 1)) or '대기 중인 강의가 없습니다.'


class StatusWindow:
    def __init__(self, root: tk.Tk, runs: Path, interval: int):
        self.root, self.runs, self.interval = root, runs, interval
        self.results: queue.Queue = queue.Queue()
        self.fetching, self.next_check = False, 0.0
        self.snapshot: Snapshot | None = None
        self.phase_info: dict = {}
        self.typical: dict = {}
        self.typical_at = 0.0
        self.job_keys = None
        self.cards, self.bars, self.extras, self.chips = [], [], [], []
        self.queue_reader = QueueReader(runs.resolve().parent)
        root.title('Study EZ · 로컬 러너')
        root.geometry('760x620')
        root.minsize(560, 420)
        root.configure(bg=BG)

        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=24, pady=(20, 4))
        tk.Label(header, text='Study EZ 러너', fg=TEXT, bg=BG, font=(FONT, 18, 'bold')).pack(side='left')
        self.refresh = self._link(header, '새로고침', self.refresh_now)
        self.refresh.pack(side='right')
        self._link(header, '상세 기록', self.toggle_details).pack(side='right')
        self.heartbeat = tk.Label(header, bg=BG, fg=MUTED, font=(FONT, 9))
        self.heartbeat.pack(side='right', padx=(0, 10))

        summary = tk.Frame(root, bg=BG)
        summary.pack(fill='x', padx=24, pady=(2, 14))
        self.state = tk.Label(summary, text='작업 확인 중…', bg=BG, fg=MUTED, font=(FONT, 10), anchor='w')
        self.state.pack(side='left')
        self.list_button = self._link(summary, '목록 ▸', self.toggle_lists)
        self.list_button.pack(side='left', padx=(8, 0))
        self.eta_label = tk.Label(summary, text='', bg=BG, fg=MUTED, font=(FONT, 10), anchor='e')
        self.eta_label.pack(side='right')

        self.build_before_jobs(root)
        self.jobs_frame = tk.Frame(root, bg=BG)
        self.jobs_frame.pack(fill='x', padx=24)
        self.jobs_frame.bind('<Configure>', self.resize_cards)

        self.build_controls(root)

        self.body = tk.Frame(root, bg=BG)
        self.body.pack(fill='both', expand=True, padx=24)
        self.lists_frame = tk.Frame(self.body, bg=BG)
        self.waiting_label = tk.Label(self.lists_frame, text='전체 작업', bg=BG, fg=MUTED, anchor='w', font=(FONT, 10, 'bold'))
        self.waiting_label.pack(fill='x', pady=(10, 6))
        self.overview_tabs = ttk.Notebook(self.lists_frame)
        self.overview_tabs.pack(fill='both', expand=True)
        self.overview_views = {}
        for key, caption in LISTS:
            pane = tk.Frame(self.overview_tabs, bg=BG)
            self.overview_tabs.add(pane, text=caption)
            widget = tk.Text(pane, bg=BG, fg=TEXT, relief='flat', borderwidth=0,
                             font=(FONT, 10), wrap='word', height=8, state='disabled', cursor='arrow', padx=8, pady=8)
            scroll = ttk.Scrollbar(pane, command=widget.yview)
            scroll.pack(side='right', fill='y')
            widget.configure(yscrollcommand=scroll.set)
            widget.pack(fill='both', expand=True)
            self.overview_views[key] = widget
        self.queue_view = self.overview_views['pending']
        self.log_frame = tk.Frame(self.body, bg=PANEL)
        self.log = tk.Text(self.log_frame, bg=PANEL, fg=MUTED, relief='flat', font=(FONT, 9),
                           wrap='word', height=10, state='disabled', padx=10, pady=10)
        self.log.pack(fill='both', expand=True)

        self.clock = tk.Label(root, bg=BG, fg=DIM, font=(FONT, 9), anchor='w')
        self.clock.pack(fill='x', side='bottom', padx=26, pady=(8, 14))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Runner.Horizontal.TProgressbar', troughcolor=LINE, background=GREEN,
                        bordercolor=PANEL, lightcolor=GREEN, darkcolor=GREEN, thickness=6)
        style.configure('Late.Horizontal.TProgressbar', troughcolor=LINE, background=AMBER,
                        bordercolor=PANEL, lightcolor=AMBER, darkcolor=AMBER, thickness=6)
        self.request()
        self.tick()

    @staticmethod
    def _link(parent, text, command):
        return tk.Button(parent, text=text, command=command, bg=parent.cget('bg'), fg=MUTED,
                         activebackground=parent.cget('bg'), activeforeground=TEXT, relief='flat',
                         borderwidth=0, padx=8, pady=2, font=(FONT, 9), cursor='hand2')

    def build_before_jobs(self, root):
        """Optional desktop sections above the running cards; the monitor has none."""

    def build_controls(self, root):
        """Optional desktop controls; the existing monitor stays read-only."""

    def card_controls(self, top, job):
        """Optional per-card controls; the monitor's cards stay read-only."""

    def toggle_details(self):
        if self.log_frame.winfo_manager():
            self.log_frame.pack_forget()
        else:
            self.log_frame.pack(fill='both', expand=True, pady=(10, 0))

    def toggle_lists(self):
        if self.lists_frame.winfo_manager():
            self.lists_frame.pack_forget()
            self.list_button.configure(text='목록 ▸')
        else:
            self.lists_frame.pack(fill='both', expand=True, before=self.log_frame if self.log_frame.winfo_manager() else None)
            self.list_button.configure(text='목록 ▾')

    def resize_cards(self, event):
        for labels in self.cards:
            for label in labels:
                label.configure(wraplength=max(200, event.width - 48))

    def request(self):
        if self.fetching:
            return
        self.fetching = True
        self.refresh.configure(state='disabled')
        def read():
            try:
                result = collect(self.runs)
            except Exception as error:
                result = Snapshot(time.time(), None, None, (), (), f'상태 확인 오류 ({type(error).__name__})')
            value, checked, error = self.queue_reader.read()
            result = replace(result, queue=value, queue_checked_at=checked, queue_error=error)
            self.results.put((result, self.read_phases(result)))
        threading.Thread(target=read, daemon=True, name='runner-status-reader').start()

    def read_phases(self, snapshot: Snapshot) -> dict:
        """File scans run on the reader thread, never on the window thread."""
        found = {j.run_id: j.generation for j in snapshot.jobs if j.generation}
        if not found:
            return {}
        root = self.runs / '_root-generation'
        try:
            if time.monotonic() >= self.typical_at:
                self.typical = phases.durations(root, exclude=set(found.values()))
                self.typical_at = time.monotonic() + TYPICAL_TTL
            rows = {r['runId']: r for r in (snapshot.queue or {}).get('running', [])}
            info = {}
            for run_id, gid in found.items():
                row = rows.get(run_id)
                if not row:
                    # The server marks the job done at publish; evidence work can still be running.
                    if (root / gid / 'published.json').is_file():
                        info[run_id] = 'published'
                    continue
                started = (snapshot.queue_checked_at or snapshot.checked_at) - row.get('elapsedSeconds', 0)
                result = phases.progress(root / gid, started, snapshot.checked_at, self.typical)
                if result:
                    info[run_id] = (result, snapshot.checked_at - started)
            return info
        except OSError:
            return {}

    def refresh_now(self):
        self.queue_reader.next_read = 0
        self.request()

    @staticmethod
    def set_text(widget, content):
        if widget.get('1.0', 'end-1c') != content:
            position = widget.yview()[0]
            widget.configure(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('1.0', content)
            widget.yview_moveto(position)
            widget.configure(state='disabled')

    def build_cards(self, jobs):
        for widget in self.jobs_frame.winfo_children():
            widget.destroy()
        self.cards, self.bars, self.extras, self.chips = [], [], [], []
        if not jobs:
            tk.Label(self.jobs_frame, text='지금 실행 중인 작업이 없습니다.', bg=PANEL, fg=MUTED,
                     padx=18, pady=20, font=(FONT, 11), anchor='w').pack(fill='x')
        for job in jobs:
            card = tk.Frame(self.jobs_frame, bg=PANEL, padx=18, pady=14)
            card.pack(fill='x', pady=(0, 10))
            top = tk.Frame(card, bg=PANEL)
            top.pack(fill='x')
            self.card_controls(top, job)
            elapsed = tk.Label(top, bg=PANEL, fg=MUTED, font=(FONT, 10))
            elapsed.pack(side='right')
            title = tk.Label(top, bg=PANEL, fg=TEXT, font=(FONT, 13, 'bold'), anchor='w', justify='left')
            title.pack(side='left', fill='x', expand=True)
            bar = ttk.Progressbar(card, mode='determinate', maximum=1000, value=0,
                                  style='Runner.Horizontal.TProgressbar')
            detail = tk.Label(card, bg=PANEL, fg=TEXT, font=(FONT, 10), anchor='w', justify='left')
            detail.pack(fill='x', pady=(8, 0))
            stage = tk.Label(card, bg=PANEL, fg=MUTED, font=(FONT, 9), anchor='w', justify='left')
            stage.pack(fill='x', pady=(4, 0))
            chips = tk.Frame(card, bg=PANEL)
            labels = []
            for name in phases.PHASES:
                label = tk.Label(chips, text=name, bg=PANEL, fg=DIM, font=(FONT, 9), padx=0)
                label.pack(side='left', padx=(0, 14))
                labels.append(label)
            self.chips.append((chips, stage, labels))
            self.cards.append((title, stage, detail))
            self.bars.append(bar)
            self.extras.append((elapsed, detail))

    def show_bar(self, bar, value, late=False):
        if value is None:
            bar.pack_forget()
            return
        bar.configure(value=round(value * 1000),
                      style='Late.Horizontal.TProgressbar' if late else 'Runner.Horizontal.TProgressbar')
        if not bar.winfo_manager():
            bar.pack(fill='x', pady=(10, 0), before=self.extras[self.bars.index(bar)][1])

    def show_phases(self, index, current):
        chips, stage, labels = self.chips[index]
        if current is None:
            chips.pack_forget()
            if not stage.winfo_manager():
                stage.pack(fill='x', pady=(4, 0))
            return
        stage.pack_forget()
        if not chips.winfo_manager():
            chips.pack(fill='x', pady=(8, 0))
        for number, (label, name) in enumerate(zip(labels, phases.PHASES)):
            done, now = number < current, number == current
            label.configure(text=('✓ ' if done else '● ' if now else '') + name,
                            fg=GREEN if now else MUTED if done else DIM,
                            font=(FONT, 9, 'bold') if now else (FONT, 9))

    def render(self, snapshot: Snapshot, phase_info: dict | None = None):
        if phase_info is not None:
            self.phase_info = phase_info
        server_jobs = (snapshot.queue or {}).get('running', [])
        by_run = {r['runId']: r for r in server_jobs if r['kind'] == 'bank'}
        jobs = [replace(j, title=by_run[j.run_id].get('title', j.title))
                if j.run_id in by_run and j.owner == '로컬 러너' else j for j in snapshot.jobs]
        # Desktop queue rows carry no title; its lecture list does.
        names = {r['runId']: r['title'] for key in ('tasks', 'jobs') for r in (snapshot.queue or {}).get(key, [])
                 if r.get('title') and r['title'] != r.get('runId')}
        jobs = [replace(j, title=names[j.run_id]) if j.title == j.run_id and j.run_id in names else j for j in jobs]
        known = {j.run_id for j in jobs}
        for row in server_jobs:
            if row['runId'] not in known:
                kind = {'bank': '퀴즈 생성 · 검수', 'pre': '예습', 'points': '출제 포인트 준비'}.get(row['kind'], row['kind'])
                jobs.append(JobStatus(row['runId'], row.get('title', row['runId']), 0, kind,
                                      (row.get('stage') or '러너 작업 중',), (), None, '서버 러너'))
        snapshot = replace(snapshot, jobs=tuple(jobs))
        self.snapshot = snapshot
        now = snapshot.checked_at
        lag = max(0, int(now - snapshot.queue_checked_at)) if snapshot.queue_checked_at else 0
        timing = estimate(snapshot.queue or {}, now, snapshot.queue_checked_at)
        groups = overview(snapshot)
        self.state.configure(text=f"실행 중 {len(jobs)}개  ·  대기 {len(groups['pending'])}개  ·  "
                                  f"완료 {len(groups['done'])}개  ·  확인 필요 {len(groups['attention'])}개",
                             fg=AMBER if groups['attention'] else MUTED)
        self.heartbeat.configure(text=snapshot.error or ('● 러너 연결됨' if snapshot.agent_pid else '○ 러너 꺼짐'),
                                 fg=GREEN if snapshot.agent_pid and not snapshot.error else AMBER)
        for index, (key, caption) in enumerate(LISTS):
            rows = groups[key]
            self.overview_tabs.tab(index, text=f'{caption} {len(rows)}')
            self.set_text(self.overview_views[key], '\n'.join(f'{i}. {text}' for i, text in enumerate(rows, 1)) or '해당 강의가 없습니다.')
        keys = tuple((j.run_id, j.pid) for j in jobs)
        if keys != self.job_keys:
            self.build_cards(jobs)
            self.job_keys = keys
        finishes = []
        for job, (title, stage, detail), bar, (elapsed_label, _) in zip(jobs, self.cards, self.bars, self.extras):
            row = next((r for r in server_jobs if r['runId'] == job.run_id and
                        job.owner in ('로컬 러너', '서버 러너')), {})
            current = job.stages[-1] if job.stages else row.get('stage') or job.kind
            title.configure(text=job.title)
            elapsed = row.get('elapsedSeconds', 0) + lag if row else None
            elapsed_label.configure(text=f'{minutes(elapsed)} 경과' if elapsed is not None else '')
            found = self.phase_info.get(job.run_id)
            if found == 'published':
                stage.configure(text=phases.phase_line(len(phases.PHASES)))
                self.show_phases(self.cards.index((title, stage, detail)), len(phases.PHASES))
                detail.configure(text='게시 완료  ·  근거 보강 중 (문항은 이미 올라감)')
                self.show_bar(bar, None)
                continue
            if found:
                result, _ = found
                stage.configure(text=phases.phase_line(result.phase))
                self.show_phases(self.cards.index((title, stage, detail)), result.phase)
                remaining = result.remaining
                if remaining is None:
                    detail.configure(text=f'{phases.PHASES[result.phase]} 중  ·  예상 시간은 지난 기록이 더 쌓이면 표시')
                    self.show_bar(bar, None)
                    finishes.append(None)
                    continue
                if result.overrun:
                    detail.configure(text=f'{phases.PHASES[result.phase]} 평소보다 길어지는 중  ·  '
                                          f'이 단계 {minutes(result.in_phase)}째 (평소 {minutes(self.typical.get(result.phase, 0))})')
                else:
                    detail.configure(text=f'약 {minutes(remaining)} 남음  ·  {clock(now + remaining, now)} 완료 예상')
                self.show_bar(bar, phases.fraction(elapsed or 0, remaining, result.overrun), result.overrun)
                finishes.append(now + remaining)
                continue
            stage.configure(text=step_text(current, row))
            self.show_phases(self.cards.index((title, stage, detail)), None)
            remaining = None
            if row.get('etaSeconds'):
                remaining = row['etaSeconds']
            elif row.get('id') in timing['running'] and timing['running'][row['id']]['range']:
                low, high = timing['running'][row['id']]['range']
                remaining = (low + high) / 2
            if remaining is not None and elapsed is not None:
                detail.configure(text=f'약 {minutes(remaining)} 남음  ·  {clock(now + remaining, now)} 완료 예상')
                self.show_bar(bar, phases.fraction(elapsed, remaining, False))
                finishes.append(now + remaining)
            else:
                late = row.get('id') in timing['running'] and timing['running'][row['id']].get('overrun')
                detail.configure(text='평소보다 오래 걸리는 중' if late else '')
                self.show_bar(bar, None)
                finishes.append(None)
        waiting = (snapshot.queue or {}).get('waiting', [])
        if finishes and all(finishes) and not waiting:
            self.eta_label.configure(text=f'모두 {clock(max(finishes), now)}쯤 끝남' if len(finishes) > 1 else '')
        else:
            self.eta_label.configure(text='')
        lines = [self.heartbeat.cget('text'), *snapshot.events]
        for job in jobs:
            lines += [f'\n[{job.title} · {job.run_id}]', *job.stages, *job.lines]
        self.set_text(self.log, '\n'.join(lines))
        stamp = time.strftime('%H:%M:%S', time.localtime(now))
        self.clock.configure(text=f'업데이트 {stamp}' + (f'   ·   {snapshot.queue_error}' if snapshot.queue_error else ''))

    def tick(self):
        try:
            result, phase_info = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.fetching = False
            self.next_check = time.monotonic() + self.interval
            self.refresh.configure(state='normal')
            self.render(result, phase_info)
        if not self.fetching and time.monotonic() >= self.next_check:
            self.request()
        self.root.after(500, self.tick)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=Path(__file__).resolve().parents[1] / 'runs')
    parser.add_argument('--interval', type=int, default=5)
    args = parser.parse_args()
    root = tk.Tk()
    StatusWindow(root, args.runs, max(1, args.interval))
    root.mainloop()


if __name__ == '__main__':
    main()
