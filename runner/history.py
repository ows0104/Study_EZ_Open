"""Separate desktop views and additive history copies. Original records stay put."""
from __future__ import annotations

import hashlib
import json
import queue
import threading
import uuid
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

from .status import Snapshot

GROUPS = ('done', 'active', 'pending', 'attention', 'other')


def split(snapshot: Snapshot) -> tuple[Snapshot, dict]:
    source = snapshot.queue or {}
    keys = {(r['subject'], r['runId']) for r in source.get('tasks', [])}
    ids = {rid for _, rid in keys}

    def current(row, subject=''):
        rid = row.get('runId', '')
        subject = row.get('subject') or subject
        return (subject, rid) in keys if subject else rid in ids

    visible = dict(source)
    visible['scopeFiltered'] = True
    older = dict(server=[], batches=[], jobs=[], events=[], scope=source.get('scopeInfo', {}))
    for name in ('jobs', 'running', 'waiting', 'held'):
        visible[name] = [r for r in source.get(name, []) if current(r)]
    older['server'] = [r for r in source.get('jobs', []) if not current(r)]
    visible_batches = []
    for board in snapshot.batches:
        now, past = dict(board), dict(board)
        for name in GROUPS:
            now[name] = [r for r in board.get(name, []) if current(r, board.get('subject', ''))]
            past[name] = [r for r in board.get(name, []) if not current(r, board.get('subject', ''))]
        if any(now[name] for name in GROUPS):
            visible_batches.append(now)
        if any(past[name] for name in GROUPS):
            older['batches'].append(past)
    jobs = []
    for job in snapshot.jobs:
        rid = job.run_id.rsplit('/', 1)[-1]
        if ((job.subject, rid) in keys if job.subject else rid in ids):
            jobs.append(job)
        else:
            older['jobs'].append(asdict(job))
    events = tuple(line for line in snapshot.events if any(rid in line for rid in ids))
    older['events'] = [line for line in snapshot.events if line not in events]
    return replace(snapshot, queue=visible, batches=tuple(visible_batches), jobs=tuple(jobs), events=events), older


def document(snapshot: Snapshot, server: dict, runs: Path) -> dict:
    if 'scopeKeys' in server:
        snapshot = replace(snapshot, queue={**(snapshot.queue or {}), 'tasks': server['scopeKeys']})
    _, older = split(snapshot)
    older['server'] = server.get('records', [])
    older['scope'] = server.get('scopeInfo', older['scope'])
    older['originals'] = dict(agentLog=str((runs / 'agent.log').resolve()),
                              localRegistry=str((runs / 'status-jobs').resolve()),
                              server='PrequizJob · Lecture (원본 DB 유지)')
    older['version'] = 1
    return older


def save(runs: Path, data: dict) -> Path:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    fingerprint = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    folder = runs / '_history' / 'runner'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'history-{fingerprint[:24]}.json'
    if path.is_file():
        stored = json.loads(path.read_text(encoding='utf-8')).get('data')
        if json.dumps(stored, ensure_ascii=False, sort_keys=True, separators=(',', ':')) != canonical:
            raise ValueError('기존 보관 기록을 확인해야 합니다.')
        return path
    temporary = folder / f'.{uuid.uuid4().hex}.tmp'
    try:
        temporary.write_text(json.dumps(dict(savedAt=datetime.now(UTC).isoformat(), sha256=fingerprint, data=data),
                                        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def rows(data: dict) -> list[tuple]:
    states = {'done': '완료', 'failed': '실패', 'canceled': '취소', 'held': '보류', 'queued': '대기',
              'running': '실행 중', 'active': '실행 중', 'attention': '확인 필요', 'pending': '대기'}
    kinds = {'pre': '예습', 'bank': '복습', 'main': '이전 복습', 'points': '포인트'}
    result = []
    def day(row):
        if row.get('date'):
            return row['date']
        rid = row.get('runId', '').rsplit('/', 1)[-1]
        try:
            return datetime.strptime(rid[:6], '%y%m%d').date().isoformat()
        except ValueError:
            return ''
    for row in data.get('server', []):
        result.append((day(row), row.get('subject', ''), row.get('title') or row['runId'],
                       kinds.get(row.get('kind'), row.get('kind', '')), states.get(row.get('state'), row.get('state', '')),
                       row.get('stage') or row.get('message', ''), f"서버 작업 {row['id']}"))
    for board in data.get('batches', []):
        for group in GROUPS:
            for row in board.get(group, []):
                result.append((day(row), row.get('subject') or board.get('subject') or board.get('label', ''),
                               row.get('title') or row.get('runId', ''), '일괄 작업', states.get(group, group),
                               row.get('stage', '') + (' · ' + row['error'] if row.get('error') else ''), row.get('runId', '')))
    batch_ids = {r.get('runId') for board in data.get('batches', []) for group in GROUPS for r in board.get(group, [])}
    for job in data.get('jobs', []):
        if job['run_id'].rsplit('/', 1)[-1] not in batch_ids:
            result.append(('', job.get('owner', ''), job['title'], job['kind'], '실행 중',
                           job['stages'][-1] if job.get('stages') else '', job['run_id']))
    return result


def open_window(root, load):
    """Read-only history window. All file/network work stays off the Tk thread."""
    import tkinter as tk
    from tkinter import ttk
    from .status_window import BG, PANEL, TEXT, MUTED, FONT
    window = tk.Toplevel(root)
    window.title('Study EZ · 이전 블럭 기록')
    window.geometry('1100x650')
    window.configure(bg=BG)
    tk.Label(window, text='이전 블럭 기록', bg=BG, fg=TEXT, font=(FONT, 17, 'bold')).pack(anchor='w', padx=20, pady=(20, 8))
    status = tk.Label(window, text='기록을 조회하고 보관 중입니다…', bg=BG, fg=MUTED, font=(FONT, 10), anchor='w')
    status.pack(fill='x', padx=20, pady=(0, 10))
    frame = tk.Frame(window, bg=BG)
    frame.pack(fill='both', expand=True, padx=20)
    table = ttk.Treeview(frame, columns=('date', 'subject', 'title', 'kind', 'state', 'detail', 'id'),
                         show='headings', style='Desktop.Treeview')
    for name, caption, width in [('date', '강의일', 85), ('subject', '과목 / 작업', 140), ('title', '강의', 250),
                                 ('kind', '구분', 70), ('state', '상태', 80), ('detail', '기록', 260), ('id', '작업 ID', 95)]:
        table.heading(name, text=caption)
        table.column(name, width=width, minwidth=40)
    scroll = ttk.Scrollbar(frame, command=table.yview)
    scroll.pack(side='right', fill='y')
    table.configure(yscrollcommand=scroll.set)
    table.pack(fill='both', expand=True)
    detail = tk.Text(window, height=5, bg=PANEL, fg=TEXT, font=(FONT, 10), wrap='word', state='disabled')
    detail.pack(fill='x', padx=20, pady=(10, 16))
    def select(_):
        values = table.item(table.selection()[0], 'values') if table.selection() else ()
        detail.configure(state='normal')
        detail.delete('1.0', 'end')
        detail.insert('1.0', '\n'.join(values))
        detail.configure(state='disabled')
    table.bind('<<TreeviewSelect>>', select)
    result = queue.Queue()
    def read():
        try:
            data, path = load()
            result.put((data, path, ''))
        except Exception:
            result.put(({}, None, '기록 조회 또는 보관에 실패했습니다. 원본 기록은 유지됩니다.'))
    threading.Thread(target=read, daemon=True, name='runner-history-reader').start()
    def poll():
        if not window.winfo_exists():
            return
        try:
            data, path, error = result.get_nowait()
        except queue.Empty:
            window.after(200, poll)
            return
        if error:
            status.configure(text=error)
            return
        entries = rows(data)
        for entry in entries:
            table.insert('', 'end', values=entry)
        status.configure(text=f'{len(entries)}건 · 이 PC에 조회본을 저장했습니다. 원본과 실행 중 작업은 유지됩니다.')
        detail.configure(state='normal')
        detail.insert('1.0', f'보관 위치: {path}')
        detail.configure(state='disabled')
    window.after(200, poll)
    return window
