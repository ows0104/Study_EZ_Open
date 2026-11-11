"""핵심 근거 재선택 묶음(docs/changes/2026-11-11-evidence-from-citations R4): 대상이 많으면 40개씩 나눠 동시에 부른다."""
import json
import threading

import fitz
import pytest

from quizbank import slide_focus
from quizbank.session import SessionError


def _notes(path):
    doc = fitz.open()
    for i in range(3):
        doc.new_page().insert_text((40, 60), f"slide {i + 1}")
    doc.save(path)
    return path


def _bank(n):
    return {"questions": [{"question_id": f"Q{i:03d}", "question": f"Q{i}?", "answer": "A", "answer_units": ["A"], "format": "basic",
                           "source_refs": [{"source_id": "S1", "locator": "PDF 물리 1쪽"}], "options": [], "correct_option_ids": []}
                          for i in range(1, n + 1)]}


class Model:
    def __init__(self, fail_batch=None, foreign=False):
        self.works, self.lock, self.fail_batch, self.foreign = [], threading.Lock(), fail_batch, foreign

    def __call__(self, prompt, schema, work, model, label):
        targets = json.loads((work / "targets.json").read_text(encoding="utf-8"))
        with self.lock:
            self.works.append((work.name, len(targets), sorted(p.name for p in work.iterdir())))
        if self.fail_batch and work.name == self.fail_batch:
            raise SessionError("synthetic failure")
        ids = [t["question_id"] for t in targets]
        if self.foreign and work.name == "batch-1":
            ids[0] = "Q001"
        return {"selections": [{"question_id": q, "pool_id": "", "candidate_id": "", "mode": "single", "reason": "r",
                                "slides": [{"page": 1, "evidence": "e"}], "unresolved_cause": "", "searched_sources": [],
                                "exam_pages": []} for q in ids]}, {"seconds": 1, "input_tokens": len(ids)}


def test_대상이_많으면_묶음으로_나눠_합친다(tmp_path, monkeypatch):
    model = Model()
    monkeypatch.setattr(slide_focus, "_call", model)
    report, usage = slide_focus.select(_bank(85), _notes(tmp_path / "notes.pdf"), tmp_path / "focus")
    assert sorted((w, n) for w, n, _ in model.works) == [("batch-0", 40), ("batch-1", 40), ("batch-2", 5)]
    # 묶음마다 같은 자료와 자기 대상만 있다.
    assert all({"sources.json", "jokbo.md", "source-pages.json", "source-text.md", "source-pages", "targets.json"} <= set(files)
               for _, _, files in model.works)
    assert sorted(report["questions"]) == [f"Q{i:03d}" for i in range(1, 86)]
    assert report["reselectedCount"] == 85 and [u["input_tokens"] for u in usage] == [40, 40, 5]


def test_대상이_묶음_하나면_지금처럼_한_번(tmp_path, monkeypatch):
    model = Model()
    monkeypatch.setattr(slide_focus, "_call", model)
    slide_focus.select(_bank(40), _notes(tmp_path / "notes.pdf"), tmp_path / "focus")
    assert [(w, n) for w, n, _ in model.works] == [("focus", 40)]


def test_한_묶음이_실패하면_전체가_실패한다(tmp_path, monkeypatch):
    monkeypatch.setattr(slide_focus, "_call", Model(fail_batch="batch-1"))
    with pytest.raises(SessionError):
        slide_focus.select(_bank(85), _notes(tmp_path / "notes.pdf"), tmp_path / "focus")
    assert not (tmp_path / "focus" / "slide-focus.json").exists()


def test_다른_묶음의_대상을_고르면_멈춘다(tmp_path, monkeypatch):
    monkeypatch.setattr(slide_focus, "_call", Model(foreign=True))
    with pytest.raises(SessionError, match="다른 묶음"):
        slide_focus.select(_bank(85), _notes(tmp_path / "notes.pdf"), tmp_path / "focus")
