"""실제 남은 학습 단위, 재학습 대기, 날짜 경계, 동일 개념 변형문항 검증."""

import copy
from datetime import datetime

from app.study_engine import empty_state, record_review
from app.study_engine.daily_queue import lecture_goal, select_daily_question
from app.study_engine.planning import KOREA, day_start
from app.study_engine.memory import DAY_MS
from tests.bank_fixtures import example_bank

NOW = int(datetime(2026, 10, 6, 10, tzinfo=KOREA).timestamp() * 1000)
EXAM = "2026-10-20"


def main():
    bank = example_bank()
    # 서로 다른 두 핵심 단위, 같은 단위의 변형 한 개. 심화 문항은 별도 추가 학습이다.
    bank["questions"].append({**copy.deepcopy(bank["questions"][0]), "question_id": "Q1-variant"})
    bank["questions"][1]["tier"] = "Core"
    state = empty_state()
    original = copy.deepcopy(state)
    goal = lecture_goal(bank, state, "검증", NOW)
    assert goal["total"] == goal["remaining"] == goal["newRemaining"] == 2
    assert goal["firstPassSeen"] == 0 and not goal["met"]
    state = record_review(bank, state, "Q1", "Good", NOW)
    goal = lecture_goal(bank, state, "검증", NOW)
    assert goal["total"] == 2 and goal["completed"] == goal["remaining"] == 1
    assert goal["progressPercent"] == 50 and goal["firstPassSeen"] == 1
    assert select_daily_question(bank, state, EXAM, NOW)["question"]["question_id"] == "Q2"
    state = record_review(bank, state, "Q2", "Again", NOW + 1000)
    goal = lecture_goal(bank, state, "검증", NOW + 1000)
    assert goal["completed"] == 1 and goal["remaining"] == goal["relearningRemaining"] == 1
    assert goal["firstPassSeen"] == 2 and not goal["met"]  # 1회 확인과 오늘 완료는 다르다.
    assert select_daily_question(bank, state, EXAM, NOW + 1001)["question"] is None
    assert select_daily_question(bank, state, EXAM, NOW + 61_000)["question"]["question_id"] == "Q2"
    state = record_review(bank, state, "Q2", "Hard", NOW + 61_000)
    assert select_daily_question(bank, state, EXAM, NOW + 61_001)["question"] is None
    state = record_review(bank, state, "Q2", "Good", NOW + 361_000)
    goal = lecture_goal(bank, state, "검증", NOW + 361_000)
    assert goal["met"] and goal["remaining"] == 0 and goal["completed"] == 2
    assert goal["reviewedToday"] == 4 and goal["progressPercent"] == 100
    # 당일 다시 열어도 완료를 유지하고, 다음날은 예정된 복습 단위로 돌아온다.
    assert lecture_goal(bank, state, "검증", NOW + 7 * 3_600_000)["met"]
    tomorrow = day_start(NOW) + DAY_MS
    fresh = lecture_goal(bank, state, "검증", tomorrow)
    assert fresh["reviewRemaining"] == 2 and fresh["newRemaining"] == fresh["reviewedToday"] == 0
    assert select_daily_question(bank, state, EXAM, tomorrow)["question"] is not None
    # 완료한 뒤 추가 학습에서 틀리면 해당 단위가 다시 남는다.
    failed_extra = record_review(bank, state, "Q1", "Again", NOW + 400_000)
    assert lecture_goal(bank, failed_extra, "검증", NOW + 400_000)["remaining"] == 1
    # 미래 복습은 오늘 분량에 포함하지 않는다. 시험일/숙련도는 완료 여부를 바꾸지 않는다.
    easy = record_review(bank, empty_state(), "Q1", "Easy", NOW - DAY_MS)
    assert lecture_goal(example_bank(), easy, "검증", NOW)["total"] == 0
    assert lecture_goal(example_bank(), easy, "검증", NOW)["met"]
    # GET 계산은 원본을 바꾸지 않는다. 오래된 이력은 items의 예정일로 호환한다.
    legacy = copy.deepcopy(easy)
    legacy["history"][0].pop("next_due_at")
    before_read = copy.deepcopy(legacy)
    assert lecture_goal(example_bank(), legacy, "검증", NOW)["total"] == 0
    assert legacy == before_read and original == empty_state()
    # 선행 문항은 일감에 포함하고, 적응형 숙련도 진입 제한 때문에 학습이 막히지 않는다.
    prerequisite_bank = example_bank()
    prerequisite_bank["questions"][0]["tier"] = "Advanced"
    prerequisite_bank["questions"][2]["tier"] = "Core"
    assert lecture_goal(prerequisite_bank, empty_state(), "검증", NOW)["total"] == 2
    assert select_daily_question(prerequisite_bank, empty_state(), EXAM, NOW)["question"]["question_id"] == "Q1"
    started = record_review(prerequisite_bank, empty_state(), "Q1", "Good", NOW)
    assert select_daily_question(prerequisite_bank, started, EXAM, NOW)["question"]["question_id"] == "Q3"
    # 자정을 넘는 재학습은 완료로 오인하지 않는다.
    late = record_review(example_bank(), empty_state(), "Q1", "Again", tomorrow - 10_000)
    assert not lecture_goal(example_bank(), late, "검증", tomorrow)["met"]
    assert lecture_goal(example_bank(), late, "검증", tomorrow)["relearningRemaining"] == 1
    print("PASS: 학습 단위 집계, 변형 중복 제거, 실제 완료, 재학습 대기, 다음날 복습, 선행·옛 기록 호환")


if __name__ == "__main__":
    main()
