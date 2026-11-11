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
        assert "러너 꺼짐" in view.heartbeat.cget("text")
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
        assert "2분 경과" in view.extras[0][0].cget("text")  # 120 s + 10 s since the queue read
        assert "약 5분 남음" in view.cards[0][2].cget("text")
        # The bar is the share of time: 130 / (130 + 300), not 3 of 10 steps.
        assert view.bars[0].winfo_manager() == "pack"
        assert view.bars[0].cget("value") == round(130 / 430 * 1000)
        assert "1. 스테로이드" in view.queue_view.get("1.0", "end")
        assert not view.log_frame.winfo_manager()
        assert not view.lists_frame.winfo_manager()
        view.toggle_lists()
        assert view.lists_frame.winfo_manager() == "pack"
        view.toggle_lists()
        # No estimate: no bar and no invented number; step names stay as text only.
        running.update(stage='출제', stageIndex=0, stageTotal=0, etaSeconds=0)
        view.render(Snapshot(1010, None, None, (), (), queue=value, queue_checked_at=1000))
        assert view.cards[0][1].cget('text') == '출제'
        assert not view.bars[0].winfo_manager()
        assert '남음' not in view.cards[0][2].cget('text')
        view.toggle_details()
        assert view.log_frame.winfo_manager() == 'pack'
        view.toggle_details()
        assert not view.log_frame.winfo_manager()
    finally:
        for child in root.winfo_children():
            child.destroy()


def test_every_running_lecture_gets_a_card_with_its_phase_and_time(tmp_path, monkeypatch, tk_root):
    from runner.status_phases import Progress
    monkeypatch.setattr(StatusWindow, "request", lambda self: None)
    root = tk_root
    try:
        view = StatusWindow(root, tmp_path, 5)
        rows = [dict(id=i, runId=r, title=t, kind="bank", subject="감염과 면역", state="running",
                     stage="연결 파일 실행 v4-review-0-0", elapsedSeconds=e)
                for i, r, t, e in [(1, "261111_02", "피코르나바이러스", 3600), (2, "261104_03", "병리2", 1200)]]
        jobs = tuple(JobStatus(r["runId"], r["runId"], 10 + r["id"], "퀴즈 생성 · 검수", (r["stage"],), (), 5,
                               generation="a" * 31 + str(r["id"])) for r in rows)
        value = dict(running=rows, waiting=[], held=[], jobs=rows)
        info = {"261111_02": (Progress(3, 300, 600, False), 3600), "261104_03": (Progress(1, 900, None, False), 1200)}
        view.render(Snapshot(1000, 7, 1, jobs, (), queue=value, queue_checked_at=1000), info)
        assert [c[0].cget("text") for c in view.cards] == ["피코르나바이러스", "병리2"]
        assert all(c[0].winfo_manager() for c in view.cards)
        assert "● 검토·수정" in view.cards[0][1].cget("text") and "✓ 추가 출제" in view.cards[0][1].cget("text")
        assert "v4-" not in view.cards[0][1].cget("text")
        assert "약 10분 남음" in view.cards[0][2].cget("text")
        assert view.bars[0].cget("value") == round(3600 / 4200 * 1000)
        assert not view.bars[1].winfo_manager() and "남음" not in view.cards[1][2].cget("text")
        info["261111_02"] = (Progress(3, 2400, 300, True), 3600)
        view.render(Snapshot(1005, 7, 1, jobs, (), queue=value, queue_checked_at=1000), info)
        assert "평소보다 길어지는" in view.cards[0][2].cget("text")
        assert view.bars[0].cget("value") <= 970
    finally:
        for child in root.winfo_children():
            child.destroy()


def test_desktop_rows_get_lecture_titles_and_published_runs_say_so(tmp_path, monkeypatch, tk_root):
    monkeypatch.setattr(StatusWindow, "request", lambda self: None)
    root = tk_root
    try:
        view = StatusWindow(root, tmp_path, 5)
        job = JobStatus("261111_02", "261111_02", 11, "퀴즈 생성 · 검수", ("연결 자동출제 /4 medical-0",), (), 5,
                        generation="b" * 32)
        value = dict(running=[], waiting=[], held=[], jobs=[],
                     tasks=[dict(runId="261111_02", title="피코르나바이러스", subject="감염과 면역", kind="bank")])
        view.render(Snapshot(1000, 7, 1, (job,), (), queue=value, queue_checked_at=1000), {"261111_02": "published"})
        assert view.cards[0][0].cget("text") == "피코르나바이러스"
        assert "게시 완료" in view.cards[0][2].cget("text")
        assert "medical" not in view.cards[0][1].cget("text") and not view.bars[0].winfo_manager()
    finally:
        for child in root.winfo_children():
            child.destroy()
