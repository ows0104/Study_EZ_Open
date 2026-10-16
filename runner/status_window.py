"""A local-only, detachable window for already running Study EZ workers."""
from __future__ import annotations

import argparse
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .status import Snapshot, collect

BG, PANEL, LINE = "#0c1322", "#151f32", "#28364f"
TEXT, MUTED, GREEN, AMBER = "#ecf2ff", "#9aaecb", "#63e3ba", "#ffd089"
FONT = "맑은 고딕"


def age(seconds: int | None) -> str:
    if seconds is None:
        return "기록 없음"
    if seconds < 60:
        return f"{seconds}초 전"
    return f"{seconds // 60}분 {seconds % 60}초 전"


class StatusWindow:
    def __init__(self, root: tk.Tk, runs: Path, interval: int):
        self.root, self.runs, self.interval = root, runs, interval
        self.results: queue.Queue[Snapshot] = queue.Queue()
        self.fetching = False
        self.next_check = 0.0
        self.snapshot: Snapshot | None = None
        self.job_keys = None
        self.cards: list[tuple] = []
        root.title("Study EZ · 로컬 러너")
        root.geometry("1050x820")
        root.minsize(850, 700)
        root.configure(bg=BG)
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=30, pady=(24, 16))
        tk.Label(header, text="STUDY EZ  /  LOCAL RUNNER", fg=GREEN, bg=BG,
                 font=(FONT, 10, "bold")).pack(anchor="w")
        tk.Label(header, text="공부할 문제를 만드는 중", fg=TEXT, bg=BG,
                 font=(FONT, 24, "bold")).pack(anchor="w", pady=(7, 4))
        tk.Label(header, text="현재 강의와 처리 단계를 이곳에서 확인하세요.", fg=MUTED,
                 bg=BG, font=(FONT, 11)).pack(anchor="w")
        metrics = tk.Frame(root, bg=PANEL, padx=20, pady=14)
        metrics.pack(fill="x", padx=30)
        self.state = tk.Label(metrics, text="●  로컬 러너 확인 중…", fg=GREEN, bg=PANEL,
                              font=(FONT, 13, "bold"))
        self.state.pack(side="left")
        self.clock = tk.Label(metrics, fg=MUTED, bg=PANEL, font=(FONT, 10))
        self.clock.pack(side="right")
        self.heartbeat = tk.Label(root, text="기존 작업을 연결하고 있습니다…", fg=MUTED,
                                  bg=BG, font=(FONT, 10), anchor="w")
        self.heartbeat.pack(fill="x", padx=32, pady=(9, 10))
        self.jobs_frame = tk.Frame(root, bg=BG)
        self.jobs_frame.pack(fill="x", padx=30)
        log_header = tk.Frame(root, bg=BG)
        log_header.pack(fill="x", padx=30, pady=(17, 8))
        tk.Label(log_header, text="최근 작업 소식", fg=TEXT, bg=BG,
                 font=(FONT, 12, "bold")).pack(side="left")
        self.refresh = tk.Button(log_header, text="지금 확인 ↻", command=self.request,
                                 bg=PANEL, fg=GREEN, activebackground=LINE, activeforeground=TEXT,
                                 relief="flat", padx=14, pady=5, font=(FONT, 10))
        self.refresh.pack(side="right")
        log_frame = tk.Frame(root, bg=PANEL)
        log_frame.pack(fill="both", expand=True, padx=30)
        self.log = tk.Text(log_frame, bg=PANEL, fg=MUTED, relief="flat", borderwidth=0,
                           font=(FONT, 10), wrap="word", padx=15, pady=12,
                           height=10, state="disabled", selectbackground=LINE)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)
        tk.Label(root, text="로컬 기록만 5초마다 확인 · 서버 조회 없음 · 이 창을 닫아도 작업은 계속됩니다"
                 .replace("5초", f"{interval}초"), fg=MUTED, bg=BG, font=(FONT, 10),
                 anchor="w").pack(fill="x", padx=32, pady=(13, 20))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Runner.Horizontal.TProgressbar", troughcolor=LINE, background=GREEN,
                        bordercolor=PANEL, lightcolor=GREEN, darkcolor=GREEN)
        self.request()
        self.tick()

    def request(self):
        if self.fetching:
            return
        self.fetching = True
        self.refresh.configure(state="disabled")

        def read():
            try:
                result = collect(self.runs)
            except Exception as error:
                result = Snapshot(time.time(), None, None, (), (),
                                  f"상태 표시 오류 ({type(error).__name__}) · 작업은 계속됩니다")
            self.results.put(result)

        threading.Thread(target=read, daemon=True, name="runner-status-reader").start()

    def render(self, snapshot: Snapshot):
        self.snapshot = snapshot
        alive = bool(snapshot.agent_pid)
        stale = snapshot.heartbeat_age is None or snapshot.heartbeat_age > 90
        status = (snapshot.error or (f"●  실행 중 · {len(snapshot.jobs)}개 작업" if snapshot.jobs else
                  "●  대기 · 새 작업 또는 자료 확인 중")) if alive or snapshot.error else "○  실행 중인 러너를 찾지 못했습니다"
        self.state.configure(text=status, fg=GREEN if alive and not stale else AMBER)
        if alive:
            detail = f"러너 PID {snapshot.agent_pid}  ·  생존 신호 {age(snapshot.heartbeat_age)}"
            if stale:
                detail += "  ·  생존 신호 지연: 러너 확인이 필요합니다"
        else:
            detail = snapshot.error or "이 창은 작업을 시작하거나 종료하지 않습니다."
        self.heartbeat.configure(text=detail)
        keys = tuple(job.run_id for job in snapshot.jobs)
        if keys != self.job_keys:
            for widget in self.jobs_frame.winfo_children():
                widget.destroy()
            self.cards = []
            self.job_keys = keys
            if not keys:
                tk.Label(self.jobs_frame, text="현재 실행 중인 퀴즈 작업이 없습니다.", bg=PANEL,
                         fg=MUTED, padx=20, pady=22, font=(FONT, 12)).pack(fill="x")
            for _ in snapshot.jobs:
                card = tk.Frame(self.jobs_frame, bg=PANEL, padx=20, pady=14)
                card.pack(fill="x", pady=(0, 10))
                title = tk.Label(card, bg=PANEL, fg=TEXT, font=(FONT, 15, "bold"), anchor="w")
                title.pack(fill="x")
                stage = tk.Label(card, bg=PANEL, fg=GREEN, font=(FONT, 12), anchor="w", wraplength=900)
                stage.pack(fill="x", pady=(8, 10))
                bar = ttk.Progressbar(card, mode="indeterminate", style="Runner.Horizontal.TProgressbar")
                bar.pack(fill="x")
                bar.start(16)
                detail = tk.Label(card, bg=PANEL, fg=MUTED, font=(FONT, 9), anchor="w", wraplength=900)
                detail.pack(fill="x", pady=(9, 0))
                self.cards.append((title, stage, detail))
        for job, (title, stage, detail) in zip(snapshot.jobs, self.cards):
            title.configure(text=job.title)
            stage.configure(text="진행 중  /  " + (job.stages[-1] if job.stages else job.kind))
            history = " → ".join(job.stages[-3:-1])
            detail.configure(text=f"{job.run_id} · PID {job.pid} · 로그 {age(job.log_age)}"
                             + (f"\n이전 단계  {history}" if history else "")
                             + "\n한 단계가 수 분 걸릴 수 있습니다. 움직이는 막대는 실행 표시입니다.")
        lines = list(snapshot.events)
        for job in snapshot.jobs:
            lines += [f"\n[{job.title} · 최근 상세 로그]", *job.lines]
        content = "\n".join(lines) or "아직 로컬 로그가 없습니다."
        if self.log.get("1.0", "end-1c") != content:
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.insert("1.0", content)
            self.log.see("end")
            self.log.configure(state="disabled")

    def tick(self):
        try:
            result = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.fetching = False
            self.next_check = time.monotonic() + self.interval
            self.refresh.configure(state="normal")
            self.render(result)
        remaining = max(0, int(self.next_check - time.monotonic()) + 1)
        timestamp = time.strftime("%H:%M:%S", time.localtime(self.snapshot.checked_at)) if self.snapshot else "—"
        self.clock.configure(text=f"확인 {timestamp}  ·  " + ("읽는 중" if self.fetching else f"{remaining}초 후 확인"))
        if not self.fetching and time.monotonic() >= self.next_check:
            self.request()
        self.root.after(250, self.tick)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=Path(__file__).resolve().parents[1] / "runs")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    root = tk.Tk()
    StatusWindow(root, args.runs, max(1, args.interval))
    root.mainloop()


if __name__ == "__main__":
    main()
