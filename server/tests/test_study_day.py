"""학습은 자정을 지나도 이어지고 한국 새벽 4시에 다음 학습일로 넘어간다(2026-11-11 사용자 지시)."""

import copy
from datetime import datetime

from app.study_engine import days_until, empty_state, record_review
from app.study_engine.daily_queue import lecture_goal
from app.study_engine.ordering import study_history
from app.study_engine.planning import daily_plan
from app.study_engine.study_day import KOREA, day_start
from tests.bank_fixtures import example_bank


def at(day, hour, minute=0):
    return int(datetime(2026, 10, day, hour, minute, tzinfo=KOREA).timestamp() * 1000)


def main():
    evening, midnight, before, boundary = at(18, 23, 59), at(19, 0), at(19, 3, 59), at(19, 4)
    assert day_start(evening) == day_start(midnight) == day_start(before) == at(18, 4)
    assert day_start(boundary - 1) == at(18, 4)
    assert day_start(boundary) == boundary
    assert day_start(at(20, 0)) == boundary
    assert day_start(at(19, 9)) == boundary
    assert day_start(at(19, 4, 1)) == boundary
    # 월 경계도 같은 규칙을 사용한다.
    month_start = int(datetime(2026, 11, 1, 0, tzinfo=KOREA).timestamp() * 1000)
    assert day_start(month_start) == int(datetime(2026, 10, 31, 4, tzinfo=KOREA).timestamp() * 1000)
    bank = example_bank()
    bank['questions'] = bank['questions'][:1]
    state = record_review(bank, empty_state(), 'Q1', 'Again', evening)
    saved = copy.deepcopy(state)
    assert state['items']['Q1']['due_at'] == boundary
    for now in (evening, midnight, before, boundary - 1):
        goal = lecture_goal(bank, state, 'test', now)
        assert goal['met'] and goal['reviewedToday'] == 1 and goal['remaining'] == 0
        assert len(study_history(bank, state, now)) == 1
    goal = lecture_goal(bank, state, 'test', boundary)
    assert not goal['met'] and goal['reviewedToday'] == 0 and goal['reviewRemaining'] == 1
    assert study_history(bank, state, boundary) == []
    assert state == saved
    units = [{'progress': lambda until, when: .5, 'reviewsToday': 0, 'date': datetime(2026, 10, 18).date()}]
    deadline = at(25, 9)
    plans = [daily_plan(units, 90, now, deadline) for now in (evening, midnight, before)]
    assert all(plan['dayStart'] == at(18, 4) for plan in plans)
    assert len({plan['endTarget'] for plan in plans}) == 1
    tomorrow = daily_plan(units, 90, boundary, deadline)
    assert tomorrow['dayStart'] == boundary
    # 시험까지 남은 날도 학습일로 센다. 새벽 4시 전은 전날이다.
    assert days_until('2026-10-19', evening) == 1
    assert days_until('2026-10-19', midnight) == 1
    assert days_until('2026-10-19', before) == 1
    assert days_until('2026-10-19', boundary) == 0
    print('PASS: KST 04:00 rollover, midnight continuity, next-day review, history spacing, exam days by study day')


if __name__ == '__main__':
    main()
