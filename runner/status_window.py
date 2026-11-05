"""Compact desktop monitor for running jobs and the server queue."""
from __future__ import annotations

import argparse
import queue
import threading
import time
import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import ttk

from .status import JobStatus, Snapshot, collect
from .status_queue import QueueReader, duration
from .status_eta import estimate, range_text
from .status_batch import overview

BG, PANEL, LINE = '#101722', '#1a2433', '#2b394b'
TEXT, MUTED, GREEN, AMBER = '#edf2f7', '#9daabd', '#76d4b0', '#e9bf79'
FONT = '맑은 고딕'


def progress(stage: str, row: dict, kind: str) -> tuple[int, int, int]:
    """Reported steps, or broad bank milestones; never animate or invent elapsed percent."""
    total, index = row.get('stageTotal', 0), row.get('stageIndex', 0)
    if total:
        return index, total, min(index, total)
    if kind not in ('퀴즈 생성 · 검수', 'bank'):
        return 0, 0, 0
    groups = (
        (7, ('업로드',)),
        (6, ('슬라이드', '핵심 근거', '족보 지면')),
        (5, ('개념도', '회상 계획', '학습 구조')),
        (4, ('검증', '검수', '검토', '정답 확인', '문항 수정', '보강')),
        (3, ('정리', '보기 풀', '포인트')),
        (2, ('출제',)),
        (1, ('응답 받기', '동기화',)),
    )
    for index, words in groups:
        if any(word in stage for word in words):
            return index, 7, index - 1
    return 0, 0, 0


def waiting_text(value: dict) -> str:
    rows = value.get('waiting', [])
    return '\n'.join(f"{i}. {row.get('title', row['runId'])}" for i, row in enumerate(rows, 1)) or '대기 중인 강의가 없습니다.'


class StatusWindow:
    def __init__(self, root: tk.Tk, runs: Path, interval: int):
        self.root, self.runs, self.interval = root, runs, interval
        self.results: queue.Queue[Snapshot] = queue.Queue()
        self.fetching, self.next_check = False, 0.0
        self.snapshot: Snapshot | None = None
        self.job_keys = None
        self.cards, self.bars = [], []
        self.queue_reader = QueueReader(runs.resolve().parent)
        root.title('Study EZ · 로컬 러너')
        root.geometry('780x780')
        root.minsize(620, 620)
        root.configure(bg=BG)
        header = tk.Frame(root, bg=BG)
        header.pack(fill='x', padx=24, pady=(22, 12))
        tk.Label(header, text='퀴즈 생성', fg=TEXT, bg=BG, font=(FONT, 20, 'bold')).pack(side='left')
        self.refresh = tk.Button(header, text='새로고침', command=self.refresh_now, bg=PANEL, fg=MUTED,
                                 activebackground=LINE, activeforeground=TEXT, relief='flat', padx=12, pady=6)
        self.refresh.pack(side='right')
        tk.Button(header, text='상세 기록', command=self.toggle_details, bg=BG, fg=MUTED,
                  activebackground=BG, activeforeground=TEXT, relief='flat', padx=12, pady=6).pack(side='right')
        self.state = tk.Label(root, text='작업 확인 중…', bg=BG, fg=GREEN, font=(FONT, 11), anchor='w')
        self.state.pack(fill='x', padx=26, pady=(0, 14))
        self.eta_label = tk.Label(root, text='', bg=BG, fg=MUTED, font=(FONT, 10), anchor='w')
        self.eta_label.pack(fill='x', padx=26, pady=(0, 10))
        self.build_controls(root)
        # Kept for diagnostics, shown only through the details panel.
        self.heartbeat = tk.Label(root, bg=BG, fg=MUTED)
        body = tk.Frame(root, bg=BG)
        body.pack(fill='both', expand=True, padx=24)
        self.job_canvas = tk.Canvas(body, bg=BG, highlightthickness=0, height=310)
        self.job_canvas.pack(fill='both', expand=True)
        self.jobs_frame = tk.Frame(self.job_canvas, bg=BG)
        self.job_canvas_item = self.job_canvas.create_window((0, 0), window=self.jobs_frame, anchor='nw')
        self.jobs_frame.bind('<Configure>', lambda _: self.job_canvas.configure(scrollregion=self.job_canvas.bbox('all')))
        self.job_canvas.bind('<Configure>', self.resize_cards)
        self.job_canvas.bind('<MouseWheel>', lambda e: self.job_canvas.yview_scroll(-int(e.delta / 120), 'units'))
        self.waiting_label = tk.Label(body, text='전체 작업', bg=BG, fg=MUTED, anchor='w', font=(FONT, 11, 'bold'))
        self.waiting_label.pack(fill='x', pady=(12, 7))
        self.overview_tabs = ttk.Notebook(body)
        self.overview_tabs.pack(fill='x')
        self.overview_views = {}
        for key, caption in [('active', '하는 거'), ('done', '한 거'), ('pending', '할 거'), ('attention', '확인 필요'), ('other', '별도 러너 보류')]:
            pane = tk.Frame(self.overview_tabs, bg=BG)
            self.overview_tabs.add(pane, text=caption)
            widget = tk.Text(pane, bg=BG, fg=TEXT, relief='flat', borderwidth=0,
                             font=(FONT, 10), wrap='word', height=9, state='disabled', cursor='arrow', padx=8, pady=8)
            scroll = ttk.Scrollbar(pane, command=widget.yview)
            scroll.pack(side='right', fill='y')
            widget.configure(yscrollcommand=scroll.set)
            widget.pack(fill='both', expand=True)
            self.overview_views[key] = widget
        self.queue_view = self.overview_views['pending']
        self.log_frame = tk.Frame(body, bg=PANEL)
        self.log = tk.Text(self.log_frame, bg=PANEL, fg=MUTED, relief='flat', font=(FONT, 9),
                           wrap='word', height=8, state='disabled', padx=10, pady=10)
        self.log.pack(fill='both', expand=True)
        self.clock = tk.Label(root, bg=BG, fg=MUTED, font=(FONT, 9), anchor='w')
        self.clock.pack(fill='x', padx=26, pady=(12, 18))
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('Runner.Horizontal.TProgressbar', troughcolor=LINE, background=GREEN,
                        bordercolor=PANEL, lightcolor=GREEN, darkcolor=GREEN, thickness=8)
        self.request()
        self.tick()

    def build_controls(self, root):
        """Optional desktop controls; the existing monitor stays read-only."""

    def toggle_details(self):
        if self.log_frame.winfo_manager():
            self.log_frame.pack_forget()
        else:
            self.log_frame.pack(fill='x', pady=(12, 0))

    def resize_cards(self, event):
        self.job_canvas.itemconfigure(self.job_canvas_item, width=event.width)
        for labels in self.cards:
            for label in labels:
                label.configure(wraplength=max(180, event.width - 40))

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
            self.results.put(replace(result, queue=value, queue_checked_at=checked, queue_error=error))
        threading.Thread(target=read, daemon=True, name='runner-status-reader').start()

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

    def render(self, snapshot: Snapshot):
        server_jobs = (snapshot.queue or {}).get('running', [])
        by_run = {r['runId']: r for r in server_jobs if r['kind'] == 'bank'}
        jobs = [replace(j, title=by_run[j.run_id].get('title', j.title))
                if j.run_id in by_run and j.owner == '로컬 러너' else j for j in snapshot.jobs]
        known = {j.run_id for j in jobs}
        for row in server_jobs:
            if row['runId'] not in known:
                kind = {'bank': '퀴즈 생성 · 검수', 'pre': '예습', 'points': '출제 포인트 준비'}.get(row['kind'], row['kind'])
                jobs.append(JobStatus(row['runId'], row.get('title', row['runId']), 0, kind,
                                      (row.get('stage') or '러너 작업 중',), (), None, '서버 러너'))
        snapshot = replace(snapshot, jobs=tuple(jobs))
        self.snapshot = snapshot
        waiting = (snapshot.queue or {}).get('waiting', [])
        timing_estimates = estimate(snapshot.queue or {}, snapshot.checked_at, snapshot.queue_checked_at)
        full = timing_estimates['total']
        if full:
            from datetime import datetime
            start = time.strftime('%H:%M', time.localtime(snapshot.checked_at + full[0]))
            end = time.strftime('%H:%M', time.localtime(snapshot.checked_at + full[1]))
            tomorrow = (datetime.fromtimestamp(snapshot.checked_at + full[0]).date() >
                        datetime.fromtimestamp(snapshot.checked_at).date())
            self.eta_label.configure(text=f'전체 완료까지 {range_text(full)}  ·  ' + ('내일 ' if tomorrow else '') + f'{start}~{end} 예상')
        else:
            self.eta_label.configure(text='전체 예상 시간: 표본 부족 또는 처리 지연으로 계산 대기' if jobs or waiting else '')
        groups = overview(snapshot)
        self.state.configure(text=f"완료 {len(groups['done'])}개   ·   실행 중 {len(jobs)}개   ·   대기 {len(groups['pending'])}개   ·   확인 필요 {len(groups['attention'])}개")
        self.heartbeat.configure(text=snapshot.error or ('러너 연결됨' if snapshot.agent_pid else '로컬 프로세스 미연결'))
        for index, (key, caption) in enumerate([('active', '하는 거'), ('done', '한 거'), ('pending', '할 거'), ('attention', '확인 필요'), ('other', '별도 러너 보류')]):
            rows = groups[key]
            self.overview_tabs.tab(index, text=f'{caption} {len(rows)}')
            self.set_text(self.overview_views[key], '\n'.join(f'{i}. {text}' for i, text in enumerate(rows, 1)) or '해당 강의가 없습니다.')
        keys = tuple((j.run_id, j.pid) for j in jobs)
        if keys != self.job_keys:
            for widget in self.jobs_frame.winfo_children():
                widget.destroy()
            self.cards, self.bars, self.job_keys = [], [], keys
            if not keys:
                tk.Label(self.jobs_frame, text='현재 실행 중인 작업이 없습니다.', bg=PANEL, fg=MUTED,
                         padx=18, pady=24, font=(FONT, 12)).pack(fill='x')
            for job in jobs:
                card = tk.Frame(self.jobs_frame, bg=PANEL, padx=18, pady=16)
                card.pack(fill='x', pady=(0, 10))
                title = tk.Label(card, bg=PANEL, fg=TEXT, font=(FONT, 13, 'bold'), anchor='w', wraplength=650)
                title.pack(fill='x')
                stage = tk.Label(card, bg=PANEL, fg=GREEN, font=(FONT, 10), anchor='w', wraplength=650)
                stage.pack(fill='x', pady=(7, 10))
                bar = ttk.Progressbar(card, mode='determinate', maximum=100, value=0,
                                      style='Runner.Horizontal.TProgressbar')
                bar.pack(fill='x')
                detail = tk.Label(card, bg=PANEL, fg=MUTED, font=(FONT, 9), anchor='w', wraplength=650)
                detail.pack(fill='x', pady=(9, 0))
                self.cards.append((title, stage, detail))
                self.bars.append(bar)
        for job, (title, stage, detail), bar in zip(jobs, self.cards, self.bars):
            row = next((r for r in server_jobs if r['runId'] == job.run_id and
                        job.owner in ('로컬 러너', '서버 러너')), {})
            current = job.stages[-1] if job.stages else row.get('stage') or job.kind
            # Artifact observations describe activity, not a later pipeline milestone.
            index, total, value = progress(current, row, job.kind)
            if not total:
                for previous in reversed(job.stages):
                    index, total, value = progress(previous, row, job.kind)
                    if total:
                        break
            title.configure(text=job.title)
            stage.configure(text=(f'단계 {index}/{total}  ·  ' if total else '') + current)
            bar.configure(maximum=total or 100, value=value)
            timing = ''
            if row:
                elapsed = row.get('elapsedSeconds', 0) + max(0, int(snapshot.checked_at - snapshot.queue_checked_at))
                timing = f'경과 {duration(elapsed)}'
                if row.get('etaSeconds'):
                    timing += f"   ·   약 {duration(row['etaSeconds'])} 남음"
                elif row.get('id') in timing_estimates['running']:
                    empirical = timing_estimates['running'][row['id']]
                    if empirical['range']:
                        timing += f"   ·   {range_text(empirical['range'])} 남음"
                    elif empirical.get('overrun'):
                        timing += '   ·   평소보다 오래 걸리는 중'
            detail.configure(text=timing or '진행 단계 확인 중')
        lines = [self.heartbeat.cget('text'), *snapshot.events]
        for job in jobs:
            lines += [f'\n[{job.title} · {job.run_id}]', *job.lines]
        self.set_text(self.log, '\n'.join(lines))
        stamp = time.strftime('%H:%M:%S', time.localtime(snapshot.checked_at))
        notice = snapshot.queue_error or ('최근 2일 실측 기준 예상 · 검수·재시도에 따라 변동' if jobs else '')
        self.clock.configure(text=f'업데이트 {stamp}' + (f'   ·   {notice}' if notice else ''))

    def tick(self):
        try:
            result = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.fetching = False
            self.next_check = time.monotonic() + self.interval
            self.refresh.configure(state='normal')
            self.render(result)
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
