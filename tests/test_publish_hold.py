"""`publish.hold_pre` — 링크가 바뀐 편에서 무엇이 나가고 무엇이 남는가.

여기 있는 것이 이 함수의 존재 이유다: **덱은 붙들고 링크는 내보낸다.** 반대로
하면(`hold_artifacts`처럼 링크까지 붙들면) `publish`가 관리자가 방금 저장한
링크를 옛 것으로 되돌린다 — 막으려던 바로 그 일이다.
"""

from pathlib import Path

from studyez import publish


def a_plan(tmp_path: Path) -> publish.LecturePlan:
    plan = publish.LecturePlan(
        subject="병리학", run_id="260824_01",
        item=publish.LectureFile.__new__(publish.LectureFile),
        prev_run_id="250825_01")
    for kind in ("notes_current", "notes_prev", "main_apkg", "pre_apkg", "media", "media"):
        path = tmp_path / f"{kind}.bin"
        path.write_bytes(b"x")
        plan.uploads.append(publish.Upload(kind, path))
    plan.run_meta = {"main": tmp_path / "run.meta.json", "pre": tmp_path / "pre_run.meta.json"}
    plan.pre_items = tmp_path / "pre_items.final.json"
    plan.preview_url = "https://chatgpt.com/share/새-대화"
    return plan


def test_링크는_나가고_예습_산출물만_남는다(tmp_path):
    plan = a_plan(tmp_path)
    publish.hold_pre(plan, "링크가 바뀌었다")

    assert plan.preview_url == "https://chatgpt.com/share/새-대화"
    assert plan.pre_items is None
    assert "pre" not in plan.run_meta
    assert [u.kind for u in plan.uploads] == ["notes_current", "notes_prev", "main_apkg"]
    assert any("미룬 것" in note for note in plan.notes)


def test_미룬_것을_적는다(tmp_path):
    plan = a_plan(tmp_path)
    publish.hold_pre(plan, "링크가 바뀌었다")
    note = next(n for n in plan.notes if "미룬 것" in n)
    for held in ("pre_apkg", "media×2", "run-meta pre", "pre-items"):
        assert held in note


def test_예습이_없는_편은_그대로다(tmp_path):
    plan = publish.LecturePlan(
        subject="병리학", run_id="260824_01",
        item=publish.LectureFile.__new__(publish.LectureFile))
    path = tmp_path / "notes.pdf"
    path.write_bytes(b"x")
    plan.uploads.append(publish.Upload("notes_current", path))
    publish.hold_pre(plan, "링크가 바뀌었다")

    assert [u.kind for u in plan.uploads] == ["notes_current"]
    assert plan.notes == []
