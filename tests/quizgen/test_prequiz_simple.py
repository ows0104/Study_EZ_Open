"""독립 묶음 검수의 누락·허위 합격을 막는다."""
import pytest

from quizgen.prequiz.simple import check_review, fingerprint
from quizgen.runbase import Failed


CARDS = [{"id": "p01", "q": "첫 질문"}, {"id": "p02", "q": "둘째 질문"}]


def row(id, ok=True, issues=None):
    return {"id": id, "ok": ok, "issues": issues or []}


@pytest.mark.parametrize("rows", [
    [row("p01")], [row("p01"), row("p01")],
    [row("p01"), row("unknown")],
    [row("p01"), row("p02", True, ["답 근거가 없다"])],
    [row("p01"), row("p02", False)],
    [row("p01"), row("p02", "true")],
])
def test_incomplete_or_contradictory_review_fails(rows):
    with pytest.raises(Failed):
        check_review({"cards": rows}, CARDS)


def test_complete_review_and_actionable_failure():
    assert check_review({"cards": [row("p02"), row("p01")]}, CARDS) == []
    bad = row("p02", False, ["설명본에 답의 근거가 없다"])
    assert check_review({"cards": [row("p01"), bad]}, CARDS) == [bad]


def test_review_fingerprint_changes_with_question():
    assert fingerprint(CARDS) != fingerprint([CARDS[0], {**CARDS[1], "q": "수정 질문"}])


def test_review_rejects_missing_input_ids():
    with pytest.raises(Failed, match="id"):
        check_review({"cards": [row("p01"), row("p02")]}, [{"id": None}, {"id": None}])


def test_failed_machine_check_never_builds(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from quizgen.prequiz import simple
    from quizgen import reproduce

    simple.dump(tmp_path / "items.raw.json", {"cards": []})
    simple.dump(tmp_path / "items.checked.json", {"cards": []})
    simple.dump(tmp_path / "suspects.json", {"coverage": {}})
    simple.dump(tmp_path / "items.reproduced.json", {"cards": [{"q": "낡은 재현 결과"}]})
    (tmp_path / "note.md").write_text("예습 설명 " * 100, encoding="utf-8")
    built = []
    runner = SimpleNamespace(
        out=tmp_path, args=SimpleNamespace(note="note.md", repair_rounds=0),
        step=lambda name, output, fn: None,
        prep=lambda: None, note=lambda: None, approve=lambda: None,
        validate=lambda: None, violations=lambda: ["문항 부족"], build=lambda: built.append(True))
    monkeypatch.setattr(reproduce, "hard_leaks", lambda _: [])
    with pytest.raises(Failed, match="검수에 문제가 남았다"):
        simple.run(runner)
    assert not built
    assert not (tmp_path / "items.reproduced.json").exists()
