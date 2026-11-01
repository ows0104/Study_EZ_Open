import tkinter as tk
import pytest

from runner.status import JobStatus, Snapshot
from runner.status_window import StatusWindow


@pytest.fixture(scope="module")
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def test_other_session_cards_remain_visible_when_generator_is_disconnected(tmp_path, monkeypatch, tk_root):
    # No CIM, subprocess, worker or visible window is needed for this UI contract.
    monkeypatch.setattr(StatusWindow, "request", lambda self: None)
    root = tk_root
    try:
        view = StatusWindow(root, tmp_path, 5)
        jobs = tuple(JobStatus(f"audit/{i}", title, i, "원본 추가 대조",
                               ("CLI 대조 중",), (), 20, "검수 세션")
                     for i, title in [(10, "항생제 원리"), (20, "유전자 표적 항암")])
        view.render(Snapshot(1000, None, None, jobs, ()))
        assert "실행 중 2개" in view.state.cget("text")
        assert "미연결" in view.heartbeat.cget("text")
        assert [card[0].cget("text") for card in view.cards] == ["항생제 원리", "유전자 표적 항암"]
        assert all("CLI 대조 중" in card[1].cget("text") for card in view.cards)
        view.render(Snapshot(1010, 30, 1, jobs[1:], ()))
        assert len(view.cards) == 1 and view.cards[0][0].cget("text") == "유전자 표적 항암"
    finally:
        for child in root.winfo_children():
            child.destroy()


def test_server_queue_shows_lecture_stage_and_progress_without_cim(tmp_path, monkeypatch, tk_root):
    monkeypatch.setattr(StatusWindow, "request", lambda self: None)
    root = tk_root
    try:
        view = StatusWindow(root, tmp_path, 5)
        running = dict(id=1, runId="261016_01", title="신호전달 표적항암제", kind="bank", subject="약리학",
                       state="running", stage="원본 대조", stageIndex=3, stageTotal=10,
                       elapsedSeconds=120, etaSeconds=300)
        waiting = dict(runId="261016_03", title="스테로이드", kind="bank", subject="약리학", state="queued")
        value = dict(running=[running], waiting=[waiting], held=[], jobs=[running, waiting])
        view.render(Snapshot(1010, None, None, (), (), queue=value, queue_checked_at=1000))
        assert view.cards[0][0].cget("text") == "신호전달 표적항암제"
        assert "단계 3/10" in view.cards[0][1].cget("text")
        assert "2분 10초" in view.cards[0][2].cget("text")
        assert str(view.bars[0].cget("mode")) == "determinate"
        assert view.bars[0].cget("value") == 3
        assert "1. 스테로이드" in view.queue_view.get("1.0", "end")
        assert not view.log_frame.winfo_manager()
        assert all(str(bar.cget('mode')) == 'determinate' for bar in view.bars)
        # Bank jobs currently report zero total; show completed milestones, not a busy animation.
        running.update(stage='출제', stageIndex=0, stageTotal=0)
        view.render(Snapshot(1010, None, None, (), (), queue=value, queue_checked_at=1000))
        assert '단계 2/7' in view.cards[0][1].cget('text')
        assert view.bars[0].cget('value') == 1
        view.toggle_details()
        assert view.log_frame.winfo_manager() == 'pack'
        view.toggle_details()
        assert not view.log_frame.winfo_manager()
    finally:
        for child in root.winfo_children():
            child.destroy()
