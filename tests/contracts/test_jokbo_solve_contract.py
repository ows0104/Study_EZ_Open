"""jokbo-solve/1 계약: 구획 순서·교수 판정·정답 상태·해설 꼴."""
import pytest

from studyez_contracts.jokbo import JokboSolveError, validate_lecture


def _doc():
    return {
        "schema": "jokbo-solve/1",
        "lecture": {"eventId": "e", "runId": "261109_01", "currentProfessors": ["갑"], "professorSource": "notes"},
        "sections": [{"kind": "same", "professors": ["갑"], "years": ["2025"], "itemIds": ["a"]},
                     {"kind": "other", "professors": ["을"], "years": ["2022"], "itemIds": ["b"]}],
        "items": [
            {"id": "a", "year": 2025, "number": 1, "stem": "s", "choices": ["1", "2"], "answers": [1],
             "answerMode": "one_of", "answerStatus": "key", "verification": "pending", "explanation": None},
            {"id": "b", "year": 2022, "number": 2, "stem": "s", "choices": ["1", "2"], "answers": [],
             "answerMode": "one_of", "answerStatus": "missing", "verification": "pending", "explanation": None},
        ],
    }


@pytest.mark.parametrize("change", [
    lambda d: d["sections"].reverse(),                                     # 다른 교수가 앞
    lambda d: d["sections"][1].update(professors=["갑"]),                   # 같은 교수를 다른 교수로
    lambda d: d["sections"][1]["itemIds"].append("a"),                      # 두 구획에
    lambda d: d["sections"].pop(),                                          # 덮지 못한 문항
    lambda d: d["items"][0].update(answers=[3]),                            # 선지 밖 답
    lambda d: d["items"][0].update(answerStatus="missing"),                 # 상태 불일치
    lambda d: d["items"][0].update(explanation={                            # 답이 있는데 추정 답
        "text": "t", "choiceNotes": ["x", "y"], "basis": {"kind": "notes"}, "answerCheck": "agree",
        "proposedAnswers": [2]}),
    lambda d: d["items"][0].update(explanation={                            # 선지 수와 다른 노트
        "text": "t", "choiceNotes": ["x"], "basis": {"kind": "notes"}, "answerCheck": "agree"}),
    lambda d: d["items"][0].update(figures=[{"file": "../x.png"}]),        # 경로 탈출
])
def test_contract_rejects(change):
    doc = _doc()
    validate_lecture(doc)
    change(doc)
    with pytest.raises(JokboSolveError):
        validate_lecture(doc)
