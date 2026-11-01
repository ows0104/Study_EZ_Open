"""Read-only server queue for the desktop monitor, cached between refreshes."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path


def read_server(root: Path) -> dict:
    """Use the server runtime so the monitor itself needs only the standard library."""
    code = '''
import json,sys
from datetime import UTC,datetime,timedelta
from pathlib import Path
sys.path.insert(0, 'server')
from dotenv import load_dotenv
load_dotenv('server/.env')
from sqlalchemy import select,text
from app.database import SessionLocal
from app.jobs.views import board
from app.models import Lecture,PrequizJob
with SessionLocal() as db:
 db.execute(text('SET TRANSACTION READ ONLY'))
 db.execute(text("SET LOCAL statement_timeout = '10000'"))
 result=board(db)
 titles={(s,r):t for s,r,t in db.execute(select(Lecture.subject,Lecture.run_id,Lecture.title))}
 for row in result['jobs']+result['waiting']:
  row['title']=titles.get((row['subject'],row['runId']),row['runId'])
 cutoff=datetime.now(UTC)-timedelta(days=2)
 policy=Path('runs/processing-policy.json')
 if policy.is_file():
  cutoff=max(cutoff,datetime.fromisoformat(json.loads(policy.read_text(encoding='utf-8'))['since']))
 samples=db.execute(select(PrequizJob.subject,PrequizJob.kind,PrequizJob.force,PrequizJob.started_at,PrequizJob.finished_at).where(
  PrequizJob.state=='done',PrequizJob.started_at>=cutoff,PrequizJob.finished_at.is_not(None)
 ).order_by(PrequizJob.finished_at.desc()).limit(120)).all()
 result['timingSamples']=[{'subject':s,'kind':k,'force':f,'seconds':int((end-start).total_seconds())}
  for s,k,f,start,end in samples if 180 <= (end-start).total_seconds() <= 10800]
 print(json.dumps(result,ensure_ascii=True))
'''
    env = os.environ.copy()
    # uv's launcher sets these for its own interpreter; the server uses Anaconda.
    for key in ("PYTHONHOME", "UV_INTERNAL__PYTHONHOME"):
        env.pop(key, None)
    result = subprocess.run(
        [str(root / "server/.venv/Scripts/python.exe"), "-c", code], cwd=root,
        capture_output=True, encoding="utf-8", errors="replace", timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=True, env=env,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or not isinstance(value.get("jobs"), list):
        raise ValueError("Invalid queue snapshot")
    return value


class QueueReader:
    def __init__(self, root: Path, interval: int = 30):
        self.root, self.interval = root, interval
        self.next_read = 0.0
        self.checked_at = 0.0
        self.value: dict = {}
        self.error = ""

    def read(self) -> tuple[dict, float, str]:
        if time.monotonic() >= self.next_read:
            try:
                self.value = read_server(self.root)
                self.checked_at = time.time()
                self.error = ""
            except (OSError, subprocess.SubprocessError, ValueError):
                # Never expose connection strings or credentials in child tracebacks.
                self.error = "서버 대기열 조회 실패 · 이전 조회 결과 유지 · 30초 후 재시도"
            self.next_read = time.monotonic() + self.interval
        return self.value, self.checked_at, self.error


def duration(seconds: int) -> str:
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes // 60}시간 {minutes % 60}분" if minutes >= 60 else f"{minutes}분 {seconds}초"


def queue_text(value: dict, checked_at: float, error: str = "") -> str:
    if not value:
        return error or "서버 대기열 확인 중…"
    waiting, running, held = (value.get(key, []) for key in ("waiting", "running", "held"))
    stamp = time.strftime("%H:%M:%S", time.localtime(checked_at))
    lines = [f"서버 확인 {stamp} · 30초마다 갱신", f"실행 {len(running)} · 대기 {len(waiting)} · 보류 {len(held)}"]
    if error:
        lines.insert(0, error)
    kinds = {"bank": "퀴즈", "points": "포인트", "pre": "예습"}
    for label, rows in (("실행 중", running), ("대기 순서", waiting), ("보류", held)):
        if not rows:
            continue
        lines += ["", label]
        for index, row in enumerate(rows, 1):
            lines.append(f"{index}. {row.get('title', row['runId'])}  [{kinds.get(row['kind'], row['kind'])}]")
            lines.append(f"   {row['subject']} / {row['runId']}")
            note = row.get("stage") or row.get("message")
            if row.get("resumeAt"):
                note = (note or "대기") + f" · 재개 {row['resumeAt']}"
            if note:
                lines.append(f"   {note}")
    recent = [r for r in value.get("jobs", []) if r["state"] in ("done", "failed", "canceled")][:5]
    if recent:
        lines += ["", "최근 결과"]
        for row in recent:
            state = {"done": "완료", "failed": "실패", "canceled": "취소"}[row["state"]]
            lines.append(f"{state} · {row.get('title', row['runId'])}")
            if row.get("message"):
                lines.append(f"   {row['message']}")
    return "\n".join(lines)
